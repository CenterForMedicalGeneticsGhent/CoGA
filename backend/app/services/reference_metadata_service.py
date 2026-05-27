from __future__ import annotations

import csv
import gzip
import io
import json
import logging
from pathlib import Path
from typing import Iterable, Literal
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..schemas import (
    AssemblyReferenceStatusOut,
    BlacklistRegionOut,
    ClinicalCnvOut,
    ChromosomeOut,
    ChromosomeSizeOut,
    GeneOut,
    ReferenceUploadResult,
    SegmentalDuplicationOut,
)
from .data_scope import chromosome_aliases, normalize_chromosome

ReferenceDatasetType = Literal["cytobands", "genes", "blacklist", "clinical_cnvs", "segmental_duplications"]
_TRUE_TEXT_VALUES = {"1", "true", "yes", "y", "mane", "mane_select", "select", "canonical"}
logger = logging.getLogger(__name__)

REPO_CLINICAL_CNVS_PATH = Path(__file__).resolve().parents[3] / "data" / "ref-data" / "clinical_cnv_syndromes_hg38_combined.tsv"
REPO_SEGMENTAL_DUPLICATIONS_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "ref-data"
    / "clinical_cnv_syndromes_hg38_bundle"
    / "ClinGen_recurrent_CNV_V2.1-hg38.bed"
)


def _json_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _text_value(value: object) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _normalized_transcript(value: object) -> str | None:
    text_value = _text_value(value)
    if not text_value:
        return None
    return text_value.split(".", 1)[0].upper()


def _transcript_id_from_gene_row(row: dict[str, object]) -> str:
    extra = _json_dict(row.get("extra"))
    return str(extra.get("transcript_id") or row.get("gene_id") or row.get("hgnc_symbol") or "")


def _first_extra_value(*payloads: dict[str, object], keys: tuple[str, ...]) -> object | None:
    for payload in payloads:
        for key in keys:
            value = payload.get(key)
            if value is not None and value != "":
                return value
    return None


def _field_marks_transcript(value: object, transcript_id: str) -> bool:
    if isinstance(value, bool):
        return value
    text_value = _text_value(value)
    if not text_value:
        return False
    if text_value.lower() in _TRUE_TEXT_VALUES:
        return True
    normalized_value = _normalized_transcript(text_value)
    normalized_transcript = _normalized_transcript(transcript_id)
    return bool(normalized_value and normalized_transcript and normalized_value == normalized_transcript)


def _transcript_matches_reference(value: object, transcript_id: str) -> bool:
    normalized_value = _normalized_transcript(value)
    normalized_transcript = _normalized_transcript(transcript_id)
    return bool(normalized_value and normalized_transcript and normalized_value == normalized_transcript)


def _gene_transcript_priority(row: dict[str, object]) -> tuple[int, int, int, str]:
    extra = _json_dict(row.get("extra"))
    gene_info_extra = _json_dict(row.get("gene_info_extra"))
    clingen_facts = _json_dict(gene_info_extra.get("clingen_gene_facts"))
    transcript_id = _transcript_id_from_gene_row(row)
    mane_reference = _first_extra_value(
        extra,
        gene_info_extra,
        clingen_facts,
        keys=(
            "mane_select_transcript",
            "maneSelectTranscript",
            "MANE_SELECT",
            "MANE Select Transcript",
        ),
    )
    canonical_reference = _first_extra_value(
        extra,
        gene_info_extra,
        keys=(
            "ensembl_canonical_transcript",
            "canonical_transcript",
            "canonicalTranscript",
        ),
    )
    is_mane = (
        _field_marks_transcript(extra.get("mane_select"), transcript_id)
        or _field_marks_transcript(extra.get("maneSelect"), transcript_id)
        or _field_marks_transcript(extra.get("MANE_SELECT"), transcript_id)
        or _transcript_matches_reference(mane_reference, transcript_id)
    )
    is_canonical = (
        _field_marks_transcript(extra.get("canonical"), transcript_id)
        or _field_marks_transcript(extra.get("is_canonical"), transcript_id)
        or _field_marks_transcript(extra.get("CANONICAL"), transcript_id)
        or _transcript_matches_reference(canonical_reference, transcript_id)
    )
    rank = 0 if is_mane else 1 if is_canonical else 2
    length = int(row.get("end") or 0) - int(row.get("start") or 0)
    exon_count = len(row.get("exons") or [])
    return (rank, -length, -exon_count, transcript_id)


def _select_preferred_gene_rows(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    preferred_by_gene: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        gene_key = (str(row.get("chr") or ""), str(row.get("hgnc_symbol") or "").upper())
        current = preferred_by_gene.get(gene_key)
        if current is None or _gene_transcript_priority(row) < _gene_transcript_priority(current):
            preferred_by_gene[gene_key] = row
    return sorted(
        preferred_by_gene.values(),
        key=lambda row: (int(row.get("start") or 0), int(row.get("end") or 0), str(row.get("hgnc_symbol") or "")),
    )


def _require_uuid(value: str, detail: str) -> None:
    try:
        UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=detail) from exc


async def _get_assembly_by_id(
    session: AsyncSession,
    assembly_id: str,
) -> dict[str, str]:
    _require_uuid(assembly_id, "Invalid assembly id")
    result = await session.execute(
        text(
            """
            SELECT id::text AS id, assembly_name, version
            FROM assemblies
            WHERE id = CAST(:assembly_id AS uuid)
            """
        ),
        {"assembly_id": assembly_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Assembly not found")
    return dict(row)


async def _get_assembly_by_name(
    session: AsyncSession,
    assembly_name: str,
) -> dict[str, str]:
    result = await session.execute(
        text(
            """
            SELECT id::text AS id, assembly_name, version
            FROM assemblies
            WHERE assembly_name = :assembly_name
            ORDER BY release_date DESC, version DESC
            LIMIT 1
            """
        ),
        {"assembly_name": assembly_name},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Assembly not found")
    return dict(row)


async def decode_reference_upload(file: UploadFile) -> str:
    contents = await file.read()
    try:
        return contents.decode()
    except UnicodeDecodeError:
        try:
            return gzip.decompress(contents).decode()
        except OSError as exc:
            raise HTTPException(
                status_code=400,
                detail="Reference upload must be plain text or gzipped",
            ) from exc


def _reader_from_text(text_value: str) -> Iterable[list[str]]:
    return csv.reader(io.StringIO(text_value), delimiter="\t")


def _is_interval_header_row(row: list[str]) -> bool:
    return len(row) >= 3 and row[0].strip().lower() in {"chrom", "chr"} and row[1].strip().lower() == "start"


def _is_black_rgb(value: str | None) -> bool:
    if value is None:
        return False
    rgb_text = value.strip().replace(" ", "")
    return rgb_text in {"0", "0,0,0"}


def _configured_reference_path(primary: str | None, fallback: Path) -> Path | None:
    candidates: list[Path] = []
    if primary:
        candidates.append(Path(primary))
    candidates.append(fallback)
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate
    return None


def _read_reference_text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode()
    except UnicodeDecodeError:
        return gzip.decompress(raw).decode()


async def _assembly_dataset_count(
    session: AsyncSession,
    *,
    assembly_id: str,
    dataset_type: ReferenceDatasetType,
) -> int:
    count_query = {
        "cytobands": "SELECT COUNT(*) FROM chromosomes WHERE assembly_id = CAST(:assembly_id AS uuid)",
        "genes": "SELECT COUNT(*) FROM genes WHERE assembly_id = CAST(:assembly_id AS uuid)",
        "blacklist": "SELECT COUNT(*) FROM blacklist WHERE assembly_id = CAST(:assembly_id AS uuid)",
        "clinical_cnvs": "SELECT COUNT(*) FROM clinical_cnvs WHERE assembly_id = CAST(:assembly_id AS uuid)",
        "segmental_duplications": "SELECT COUNT(*) FROM segmental_duplications WHERE assembly_id = CAST(:assembly_id AS uuid)",
    }[dataset_type]
    result = await session.execute(text(count_query), {"assembly_id": assembly_id})
    return int(result.scalar_one() or 0)


async def list_reference_statuses(
    session: AsyncSession,
) -> list[AssemblyReferenceStatusOut]:
    result = await session.execute(
        text(
            """
            SELECT
                a.id::text AS assembly_id,
                a.assembly_name,
                COALESCE(chr_counts.count, 0) AS chromosomes,
                COALESCE(gene_counts.count, 0) AS genes,
                COALESCE(blacklist_counts.count, 0) AS blacklist_regions,
                COALESCE(cnv_counts.count, 0) AS clinical_cnvs,
                COALESCE(segdup_counts.count, 0) AS segmental_duplications
            FROM assemblies a
            LEFT JOIN (
                SELECT assembly_id, COUNT(*) AS count
                FROM chromosomes
                GROUP BY assembly_id
            ) AS chr_counts ON chr_counts.assembly_id = a.id
            LEFT JOIN (
                SELECT assembly_id, COUNT(*) AS count
                FROM genes
                GROUP BY assembly_id
            ) AS gene_counts ON gene_counts.assembly_id = a.id
            LEFT JOIN (
                SELECT assembly_id, COUNT(*) AS count
                FROM blacklist
                GROUP BY assembly_id
            ) AS blacklist_counts ON blacklist_counts.assembly_id = a.id
            LEFT JOIN (
                SELECT assembly_id, COUNT(*) AS count
                FROM clinical_cnvs
                GROUP BY assembly_id
            ) AS cnv_counts ON cnv_counts.assembly_id = a.id
            LEFT JOIN (
                SELECT assembly_id, COUNT(*) AS count
                FROM segmental_duplications
                GROUP BY assembly_id
            ) AS segdup_counts ON segdup_counts.assembly_id = a.id
            ORDER BY a.assembly_name, a.version
            """
        )
    )
    return [
        AssemblyReferenceStatusOut(
            assembly_id=row["assembly_id"],
            assembly_name=row["assembly_name"],
            chromosomes=int(row["chromosomes"]),
            genes=int(row["genes"]),
            blacklist_regions=int(row["blacklist_regions"]),
            clinical_cnvs=int(row["clinical_cnvs"]),
            segmental_duplications=int(row["segmental_duplications"]),
        )
        for row in result.mappings().all()
    ]


async def seed_builtin_reference_tracks(session: AsyncSession) -> None:
    if not settings.reference_bootstrap_enabled:
        return

    assembly_name = settings.reference_bootstrap_assembly_name.strip()
    if not assembly_name:
        return

    try:
        assembly = await _get_assembly_by_name(session, assembly_name)
    except HTTPException as exc:
        if exc.status_code == 404:
            logger.info("Skipping reference track bootstrap: assembly '%s' not found", assembly_name)
            return
        raise

    assembly_id = str(assembly["id"])
    bootstrap_jobs: list[tuple[ReferenceDatasetType, Path]] = []

    clinical_cnvs_path = _configured_reference_path(
        settings.reference_clinical_cnvs_path,
        REPO_CLINICAL_CNVS_PATH,
    )
    if clinical_cnvs_path is not None:
        bootstrap_jobs.append(("clinical_cnvs", clinical_cnvs_path))

    segdup_path = _configured_reference_path(
        settings.reference_segmental_duplications_path,
        REPO_SEGMENTAL_DUPLICATIONS_PATH,
    )
    if segdup_path is not None:
        bootstrap_jobs.append(("segmental_duplications", segdup_path))

    if not bootstrap_jobs:
        logger.info("Skipping reference track bootstrap: no source files found")
        return

    for dataset_type, path in bootstrap_jobs:
        existing = await _assembly_dataset_count(
            session,
            assembly_id=assembly_id,
            dataset_type=dataset_type,
        )
        if existing > 0:
            continue
        try:
            text_value = _read_reference_text(path)
            result = await apply_reference_dataset_text(
                session,
                assembly_id=assembly_id,
                dataset_type=dataset_type,
                text_value=text_value,
                overwrite=False,
                commit=False,
            )
            logger.info(
                "Bootstrapped %s for %s from %s (%d rows)",
                dataset_type,
                assembly_name,
                path,
                result.inserted,
            )
        except Exception:
            logger.exception(
                "Failed to bootstrap %s for assembly %s from %s",
                dataset_type,
                assembly_name,
                path,
            )
    await session.commit()


async def upload_reference_dataset(
    session: AsyncSession,
    *,
    assembly_id: str,
    dataset_type: ReferenceDatasetType,
    file: UploadFile,
    overwrite: bool,
) -> ReferenceUploadResult:
    text_value = await decode_reference_upload(file)
    return await apply_reference_dataset_text(
        session,
        assembly_id=assembly_id,
        dataset_type=dataset_type,
        text_value=text_value,
        overwrite=overwrite,
    )


async def apply_reference_dataset_text(
    session: AsyncSession,
    *,
    assembly_id: str,
    dataset_type: ReferenceDatasetType,
    text_value: str,
    overwrite: bool,
    commit: bool = True,
) -> ReferenceUploadResult:
    assembly = await _get_assembly_by_id(session, assembly_id)

    count_query = {
        "cytobands": "SELECT COUNT(*) FROM chromosomes WHERE assembly_id = CAST(:assembly_id AS uuid)",
        "genes": "SELECT COUNT(*) FROM genes WHERE assembly_id = CAST(:assembly_id AS uuid)",
        "blacklist": "SELECT COUNT(*) FROM blacklist WHERE assembly_id = CAST(:assembly_id AS uuid)",
        "clinical_cnvs": "SELECT COUNT(*) FROM clinical_cnvs WHERE assembly_id = CAST(:assembly_id AS uuid)",
        "segmental_duplications": "SELECT COUNT(*) FROM segmental_duplications WHERE assembly_id = CAST(:assembly_id AS uuid)",
    }[dataset_type]
    existing = await session.execute(text(count_query), {"assembly_id": assembly_id})
    existing_count = int(existing.scalar_one() or 0)
    replaced = existing_count > 0
    if replaced and not overwrite:
        raise HTTPException(
            status_code=409,
            detail=f"{dataset_type.replace('_', ' ')} already exist for this assembly",
        )

    delete_query = {
        "cytobands": "DELETE FROM chromosomes WHERE assembly_id = CAST(:assembly_id AS uuid)",
        "genes": "DELETE FROM genes WHERE assembly_id = CAST(:assembly_id AS uuid)",
        "blacklist": "DELETE FROM blacklist WHERE assembly_id = CAST(:assembly_id AS uuid)",
        "clinical_cnvs": "DELETE FROM clinical_cnvs WHERE assembly_id = CAST(:assembly_id AS uuid)",
        "segmental_duplications": "DELETE FROM segmental_duplications WHERE assembly_id = CAST(:assembly_id AS uuid)",
    }[dataset_type]
    if replaced:
        await session.execute(text(delete_query), {"assembly_id": assembly_id})

    inserted = 0

    if dataset_type == "cytobands":
        chromosomes: dict[str, dict[str, object]] = {}
        for row in _reader_from_text(text_value):
            if len(row) < 5 or row[0].startswith("#"):
                continue
            chrom, start, end, band, stain = row[:5]
            try:
                start_i = int(start)
                end_i = int(end)
            except ValueError:
                continue
            chrom = normalize_chromosome(chrom)
            entry = chromosomes.setdefault(chrom, {"size": 0, "bands": []})
            bands = entry["bands"]
            assert isinstance(bands, list)
            bands.append(
                {
                    "name": band,
                    "start": start_i,
                    "end": end_i,
                    "stain": stain,
                }
            )
            entry["size"] = max(int(entry["size"]), end_i)

        rows = [
            {
                "assembly_id": assembly_id,
                "chr": chrom,
                "size": int(data["size"]),
                "bands": json.dumps(data["bands"]),
            }
            for chrom, data in chromosomes.items()
        ]
        if not rows:
            raise HTTPException(status_code=400, detail="No valid cytoband rows found")
        await session.execute(
            text(
                """
                INSERT INTO chromosomes (assembly_id, chr, size, bands)
                VALUES (CAST(:assembly_id AS uuid), :chr, :size, CAST(:bands AS jsonb))
                """
            ),
            rows,
        )
        inserted = len(rows)

    elif dataset_type == "genes":
        rows: list[dict[str, object]] = []
        for row in _reader_from_text(text_value):
            if not row or row[0].startswith("#") or len(row) < 12:
                continue
            (
                chrom,
                start,
                end,
                gene,
                score,
                strand,
                ccds_id,
                transcript_id,
                exon_count,
                exon_intervals,
                intron_count,
                intron_intervals,
            ) = row[:12]
            try:
                start_i = int(start)
                end_i = int(end)
            except ValueError:
                continue

            exons = []
            if exon_intervals:
                for idx, interval in enumerate(filter(None, exon_intervals.split(","))):
                    try:
                        exon_start, exon_end = interval.split("-")
                        exons.append(
                            {
                                "name": f"exon{idx + 1}",
                                "start": int(exon_start),
                                "end": int(exon_end),
                            }
                        )
                    except ValueError:
                        continue

            rows.append(
                {
                    "assembly_id": assembly_id,
                    "gene_id": transcript_id or gene,
                    "hgnc_symbol": gene,
                    "chr": normalize_chromosome(chrom),
                    "start": start_i,
                    "end": end_i,
                    "exons": json.dumps(exons),
                    "strand": 1 if strand == "+" else -1,
                    "biotype": "unknown",
                    "description": "",
                    "source": "refgene",
                    "extra": json.dumps(
                        {
                            "score": score,
                            "ccds_id": ccds_id,
                            "transcript_id": transcript_id,
                            "exon_count": int(exon_count) if exon_count else 0,
                            "intron_count": int(intron_count) if intron_count else 0,
                            "intron_intervals": intron_intervals,
                        }
                    ),
                }
            )
        if not rows:
            raise HTTPException(status_code=400, detail="No valid gene rows found")
        await session.execute(
            text(
                """
                INSERT INTO genes (
                    assembly_id,
                    gene_id,
                    hgnc_symbol,
                    chr,
                    start,
                    "end",
                    exons,
                    strand,
                    biotype,
                    description,
                    source,
                    extra
                )
                VALUES (
                    CAST(:assembly_id AS uuid),
                    :gene_id,
                    :hgnc_symbol,
                    :chr,
                    :start,
                    :end,
                    CAST(:exons AS jsonb),
                    :strand,
                    :biotype,
                    :description,
                    :source,
                    CAST(:extra AS jsonb)
                )
                """
            ),
            rows,
        )
        inserted = len(rows)

    elif dataset_type == "blacklist":
        rows = []
        for row in _reader_from_text(text_value):
            if not row or row[0].startswith("#") or _is_interval_header_row(row) or len(row) < 4:
                continue
            chrom, start, end, label = row[:4]
            try:
                start_i = int(start)
                end_i = int(end)
            except ValueError:
                continue
            rows.append(
                {
                    "assembly_id": assembly_id,
                    "chr": normalize_chromosome(chrom),
                    "start": start_i,
                    "end": end_i,
                    "label": label,
                }
            )
        if not rows:
            raise HTTPException(status_code=400, detail="No valid blacklist rows found")
        await session.execute(
            text(
                """
                INSERT INTO blacklist (assembly_id, chr, start, "end", label)
                VALUES (CAST(:assembly_id AS uuid), :chr, :start, :end, :label)
                """
            ),
            rows,
        )
        inserted = len(rows)

    elif dataset_type == "clinical_cnvs":
        rows = []
        for row in _reader_from_text(text_value):
            if not row or row[0].startswith("#") or row[0].startswith("track") or _is_interval_header_row(row):
                continue

            if len(row) < 4:
                continue

            chrom, start, end, name = row[:4]
            try:
                start_i = int(start)
                end_i = int(end)
            except ValueError:
                continue

            # Support both bedDetail-like CNV inputs (11 cols) and simplified
            # tabular CNV inputs (9 cols) used in local reference bundles.
            if len(row) >= 11:
                cnv_type = name or None
                label = row[9] or name
                html = row[10] or None
            else:
                source = row[4] if len(row) > 4 else None
                source_detail = row[5] if len(row) > 5 else None
                cnv_type = source or None
                label = name
                html_parts = [part for part in [source, source_detail] if part]
                html = "<br/>".join(html_parts) if html_parts else None

            rows.append(
                {
                    "assembly_id": assembly_id,
                    "chr": normalize_chromosome(chrom),
                    "start": start_i,
                    "end": end_i,
                    "type": cnv_type,
                    "label": label,
                    "details_html": html,
                }
            )
        if not rows:
            raise HTTPException(status_code=400, detail="No valid clinical CNV rows found")
        await session.execute(
            text(
                """
                INSERT INTO clinical_cnvs (assembly_id, chr, start, "end", type, label, details_html)
                VALUES (
                    CAST(:assembly_id AS uuid),
                    :chr,
                    :start,
                    :end,
                    :type,
                    :label,
                    :details_html
                )
                """
            ),
            rows,
        )
        inserted = len(rows)

    else:
        rows = []
        for row in _reader_from_text(text_value):
            if not row or row[0].startswith("#") or row[0].startswith("track") or _is_interval_header_row(row):
                continue
            if len(row) < 4:
                continue

            chrom, start, end, label = row[:4]
            try:
                start_i = int(start)
                end_i = int(end)
            except ValueError:
                continue

            item_rgb = row[8] if len(row) > 8 else None
            normalized_label = (label or "").strip()
            source = row[4].strip() if len(row) > 4 and row[4].strip() not in {"", ".", "0"} else None

            # ClinGen recurrent-CNV BED encodes LCR/segmental duplication anchors
            # in black and recurrent CNV intervals in orange.
            if item_rgb is not None and item_rgb.strip():
                if not _is_black_rgb(item_rgb):
                    continue
            elif normalized_label:
                label_upper = normalized_label.upper()
                if not any(token in label_upper for token in ("LCR", "SEG", "DUP", "REP")):
                    continue

            if not normalized_label:
                normalized_label = "Segmental duplication"

            rows.append(
                {
                    "assembly_id": assembly_id,
                    "chr": normalize_chromosome(chrom),
                    "start": start_i,
                    "end": end_i,
                    "label": normalized_label,
                    "source": source,
                }
            )

        if not rows:
            raise HTTPException(status_code=400, detail="No valid segmental duplication rows found")
        await session.execute(
            text(
                """
                INSERT INTO segmental_duplications (assembly_id, chr, start, "end", label, source)
                VALUES (CAST(:assembly_id AS uuid), :chr, :start, :end, :label, :source)
                """
            ),
            rows,
        )
        inserted = len(rows)

    if commit:
        await session.commit()
    return ReferenceUploadResult(
        assembly_id=assembly["id"],
        assembly_name=assembly["assembly_name"],
        dataset_type=dataset_type,
        inserted=inserted,
        replaced=replaced,
    )


async def get_gene_region_records(
    session: AsyncSession,
    *,
    assembly: str,
    chrom: str,
    start: int,
    end: int,
) -> list[GeneOut]:
    assembly_row = await _get_assembly_by_name(session, assembly)
    stmt = text(
        """
        SELECT
            g.id::text AS id,
            g.gene_id,
            g.hgnc_symbol,
            g.chr,
            g.start,
            g."end",
            g.exons,
            g.strand,
            g.extra,
            gi.extra AS gene_info_extra
        FROM genes g
        LEFT JOIN gene_info gi
          ON gi.assembly_id = g.assembly_id
         AND upper(gi.hgnc_symbol) = upper(g.hgnc_symbol)
        WHERE g.assembly_id = CAST(:assembly_id AS uuid)
          AND g.chr IN :chromosomes
          AND (:apply_window = false OR (g.start < :end AND g."end" > :start))
        ORDER BY g.start, g."end", g.hgnc_symbol
        """
    ).bindparams(bindparam("chromosomes", expanding=True))
    result = await session.execute(
        stmt,
        {
            "assembly_id": assembly_row["id"],
            "chromosomes": chromosome_aliases(chrom),
            "apply_window": end > start,
            "start": start,
            "end": end,
        },
    )
    rows = [dict(row) for row in result.mappings().all()]
    preferred_rows = _select_preferred_gene_rows(rows)
    return [
        GeneOut(
            _id=row["id"],
            gene_id=row["gene_id"],
            hgnc_symbol=row["hgnc_symbol"],
            chr=row["chr"],
            start=int(row["start"]),
            end=int(row["end"]),
            exons=row.get("exons") or [],
            strand=int(row["strand"]),
        )
        for row in preferred_rows
    ]


async def get_blacklist_regions_data(
    session: AsyncSession,
    *,
    assembly: str,
    chrom: str,
    start: int,
    end: int,
) -> list[BlacklistRegionOut]:
    assembly_row = await _get_assembly_by_name(session, assembly)
    stmt = text(
        """
        SELECT id::text AS id, chr, start, "end", label
        FROM blacklist
        WHERE assembly_id = CAST(:assembly_id AS uuid)
          AND chr IN :chromosomes
          AND (:apply_window = false OR (start < :end AND "end" > :start))
        ORDER BY start, "end", label
        """
    ).bindparams(bindparam("chromosomes", expanding=True))
    result = await session.execute(
        stmt,
        {
            "assembly_id": assembly_row["id"],
            "chromosomes": chromosome_aliases(chrom),
            "apply_window": end > start,
            "start": start,
            "end": end,
        },
    )
    return [
        BlacklistRegionOut(
            _id=row["id"],
            chr=row["chr"],
            start=int(row["start"]),
            end=int(row["end"]),
            label=row["label"],
        )
        for row in result.mappings().all()
    ]


async def get_segmental_duplications_data(
    session: AsyncSession,
    *,
    assembly: str,
    chrom: str,
    start: int,
    end: int,
) -> list[SegmentalDuplicationOut]:
    assembly_row = await _get_assembly_by_name(session, assembly)
    stmt = text(
        """
        SELECT id::text AS id, chr, start, "end", label, source
        FROM segmental_duplications
        WHERE assembly_id = CAST(:assembly_id AS uuid)
          AND chr IN :chromosomes
          AND (:apply_window = false OR (start < :end AND "end" > :start))
        ORDER BY start, "end", label
        """
    ).bindparams(bindparam("chromosomes", expanding=True))
    result = await session.execute(
        stmt,
        {
            "assembly_id": assembly_row["id"],
            "chromosomes": chromosome_aliases(chrom),
            "apply_window": end > start,
            "start": start,
            "end": end,
        },
    )
    return [
        SegmentalDuplicationOut(
            _id=row["id"],
            chr=row["chr"],
            start=int(row["start"]),
            end=int(row["end"]),
            label=row["label"],
            source=row.get("source"),
        )
        for row in result.mappings().all()
    ]


async def get_clinical_cnvs_data(
    session: AsyncSession,
    *,
    assembly: str,
    chrom: str,
    start: int,
    end: int,
) -> list[ClinicalCnvOut]:
    assembly_row = await _get_assembly_by_name(session, assembly)
    stmt = text(
        """
        SELECT id::text AS id, chr, start, "end", type, label, details_html
        FROM clinical_cnvs
        WHERE assembly_id = CAST(:assembly_id AS uuid)
          AND chr IN :chromosomes
          AND (:apply_window = false OR (start < :end AND "end" > :start))
        ORDER BY start, "end", label
        """
    ).bindparams(bindparam("chromosomes", expanding=True))
    result = await session.execute(
        stmt,
        {
            "assembly_id": assembly_row["id"],
            "chromosomes": chromosome_aliases(chrom),
            "apply_window": end > start,
            "start": start,
            "end": end,
        },
    )
    return [
        ClinicalCnvOut(
            _id=row["id"],
            chr=row["chr"],
            start=int(row["start"]),
            end=int(row["end"]),
            type=row.get("type"),
            label=row["label"],
            details_html=row.get("details_html"),
        )
        for row in result.mappings().all()
    ]


async def list_chromosome_sizes_data(
    session: AsyncSession,
    *,
    assembly: str,
    chroms: list[str] | None = None,
) -> list[ChromosomeSizeOut]:
    assembly_row = await _get_assembly_by_name(session, assembly)
    normalized_chroms = chroms or []
    stmt = text(
        """
        SELECT chr, size
        FROM chromosomes
        WHERE assembly_id = CAST(:assembly_id AS uuid)
          AND (:apply_filter = false OR chr IN :chromosomes)
        ORDER BY chr
        """
    ).bindparams(bindparam("chromosomes", expanding=True))
    result = await session.execute(
        stmt,
        {
            "assembly_id": assembly_row["id"],
            "apply_filter": bool(normalized_chroms),
            "chromosomes": list(
                dict.fromkeys(
                    alias
                    for chrom in normalized_chroms
                    for alias in chromosome_aliases(chrom)
                )
            ) or [""],
        },
    )
    return [
        ChromosomeSizeOut(chr=row["chr"], size=int(row["size"]))
        for row in result.mappings().all()
    ]


async def list_chromosome_details_data(
    session: AsyncSession,
    *,
    assembly: str,
    chroms: list[str] | None = None,
) -> list[ChromosomeOut]:
    assembly_row = await _get_assembly_by_name(session, assembly)
    normalized_chroms = chroms or []
    stmt = text(
        """
        SELECT id::text AS id, assembly_id::text AS assembly_id, chr, size, bands
        FROM chromosomes
        WHERE assembly_id = CAST(:assembly_id AS uuid)
          AND (:apply_filter = false OR chr IN :chromosomes)
        ORDER BY chr
        """
    ).bindparams(bindparam("chromosomes", expanding=True))
    result = await session.execute(
        stmt,
        {
            "assembly_id": assembly_row["id"],
            "apply_filter": bool(normalized_chroms),
            "chromosomes": list(
                dict.fromkeys(
                    alias
                    for chrom in normalized_chroms
                    for alias in chromosome_aliases(chrom)
                )
            ) or [""],
        },
    )
    return [
        ChromosomeOut(
            _id=row["id"],
            assembly_id=row["assembly_id"],
            chr=row["chr"],
            size=int(row["size"]),
            bands=row.get("bands") or [],
        )
        for row in result.mappings().all()
    ]


async def get_chromosome_data(
    session: AsyncSession,
    *,
    assembly: str,
    chrom: str,
) -> ChromosomeOut:
    assembly_row = await _get_assembly_by_name(session, assembly)
    stmt = text(
        """
        SELECT id::text AS id, assembly_id::text AS assembly_id, chr, size, bands
        FROM chromosomes
        WHERE assembly_id = CAST(:assembly_id AS uuid)
          AND chr IN :chromosomes
        LIMIT 1
        """
    ).bindparams(bindparam("chromosomes", expanding=True))
    result = await session.execute(
        stmt,
        {
            "assembly_id": assembly_row["id"],
            "chromosomes": chromosome_aliases(chrom),
        },
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Chromosome not found")
    return ChromosomeOut(
        _id=row["id"],
        assembly_id=row["assembly_id"],
        chr=row["chr"],
        size=int(row["size"]),
        bands=row.get("bands") or [],
    )

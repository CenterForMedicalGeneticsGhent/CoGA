from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import (
    FamilyImportDatasetSummary,
)
from .bed_service import upload_bed_data
from .clickhouse_interval_tracks import (
    count_interval_track_source_rows,
    delete_interval_track_sources,
    delete_interval_tracks,
)
from .clickhouse_variant_storage import (
    count_family_small_variants,
    count_family_structural_variants,
    delete_family_small_variants,
    replace_family_structural_variants,
)
from .family_metadata_context import (
    FamilyMetadataContext,
    SampleMetadataContext,
)
from .hpo_service import (
    import_family_hpo_annotations,
)
from .repeat_expansion_pg import (
    clear_sample_repeat_expansions,
    decode_repeat_upload_text,
    ingest_family_trgt_text,
    ingest_trgt_text,
)
from .variant_upload_service import upload_family_small_variant_file

from .family_package_common import APCAD_PCF_SOURCE, APCAD_PCF_TRACK_TYPE, DatasetProgressCallback, FamilyPackageBundle, ManifestDataset, _display_path, _read_package_text, _resolve_package_path, _run_with_periodic_progress  # noqa: F401
from .family_package_manifest import _ped_embryo_sample_ids  # noqa: F401
from .family_package_registration import _interval_track_count, _paraphase_count, _register_only, _repeat_expansion_count  # noqa: F401
from .family_package_tracks import _delete_sample_interval_source, _import_apcad_track_file, _import_copy_number_track, _import_pcf_segment_file, _import_wisecondorx_track  # noqa: F401
from .family_package_validation import _manifest_hpo_rows, _pcf_role_path  # noqa: F401
from .family_package_variants import _iter_needlr_structural_records, _paraphase_rows_for_sample, _replace_sample_paraphase_rows, _update_sv_file_metadata  # noqa: F401


logger = logging.getLogger(__name__)


@asynccontextmanager
async def _local_upload(path: Path):
    handle = path.open("rb")
    upload = UploadFile(file=handle, filename=path.name)
    try:
        yield upload
    finally:
        await upload.close()


async def _import_snv_dataset(
    session: AsyncSession,
    *,
    bundle: FamilyPackageBundle,
    dataset: ManifestDataset,
    summary: FamilyImportDatasetSummary,
    family_context: FamilyMetadataContext,
    sample_contexts: dict[str, SampleMetadataContext],
    conflict_mode: str = "overwrite",
    progress: DatasetProgressCallback | None = None,
) -> FamilyImportDatasetSummary:
    if not family_context.assembly_name:
        return await _register_only(summary, "Registered only; family is not linked to a single assembly")
    vcf_path = _resolve_package_path(bundle.root, dataset.family_vcf)
    if vcf_path is None:
        return await _register_only(summary, "Registered only; family_vcf path is unavailable")
    source_format = str((dataset.model_extra or {}).get("source_format") or "auto")
    # The SNV dataset holds primary (directly-called) genotypes — clair3 unless the
    # manifest overrides it. Scope the coexistence checks/cleanup to this source so
    # the imputed glimpse2 callset is never touched by the SNV importer.
    snv_source = "glimpse2" if source_format == "glimpse2" else "clair3"
    if conflict_mode == "update":
        existing_count = await count_family_small_variants(
            family_context.assembly_name,
            family_context.family_uuid,
            project_ids=family_context.project_ids,
            source=snv_source,
        )
        if existing_count:
            return summary.model_copy(
                update={
                    "status": "skipped",
                    "message": "Skipped SNV import in update mode because small variants already exist for this family",
                    "summary": {"existing": existing_count},
                }
            )
    annotation_path = _resolve_package_path(bundle.root, dataset.annotation_tsv)
    progress_lock = asyncio.Lock()

    async def report_snv_progress(stats: dict[str, Any]) -> None:
        if progress is None:
            return
        async with progress_lock:
            await progress(
                summary.model_copy(
                    update={
                        "status": "running",
                        "message": "Importing SNV VCF and VEP annotations",
                        "summary": stats,
                    }
                )
            )

    if progress is not None:
        await report_snv_progress(
            {
                "stage": "starting",
                "family_vcf": _display_path(bundle.root, vcf_path),
                "annotation_tsv": _display_path(bundle.root, annotation_path) if annotation_path else None,
            }
        )

    async def run_upload() -> dict[str, Any]:
        if annotation_path is not None:
            async with _local_upload(vcf_path) as upload:
                async with _local_upload(annotation_path) as annotation_upload:
                    return await upload_family_small_variant_file(
                        session,
                        context=family_context,
                        sample_contexts=sample_contexts,
                        file=upload,
                        annotation_file=annotation_upload,
                        overwrite=True,
                        format_hint=source_format,  # type: ignore[arg-type]
                        progress=report_snv_progress,
                    )
        async with _local_upload(vcf_path) as upload:
            return await upload_family_small_variant_file(
                session,
                context=family_context,
                sample_contexts=sample_contexts,
                file=upload,
                overwrite=True,
                format_hint=source_format,  # type: ignore[arg-type]
                progress=report_snv_progress,
            )

    try:
        result = await _run_with_periodic_progress(
            run_upload(),
            report=report_snv_progress if progress is not None else None,
            stats={
                "family_vcf": _display_path(bundle.root, vcf_path),
                "annotation_tsv": _display_path(bundle.root, annotation_path) if annotation_path else None,
            },
        )
    except Exception:
        # The SNV loader only writes its own small-variant source; it never creates
        # haplotype interval tracks (those belong to the glimpse2 loader). Scope the
        # cleanup to this source so a failed SNV import cannot wipe a previously
        # imported glimpse2 callset or its haplotype blocks.
        with suppress(Exception):
            await delete_family_small_variants(
                family_context.assembly_name,
                family_context.family_uuid,
                source=snv_source,
            )
        raise
    return summary.model_copy(
        update={
            "status": "imported",
            "message": "Imported through existing family small-variant loader",
            "summary": result,
        }
    )


async def _import_haplotypes_dataset(
    session: AsyncSession,
    *,
    bundle: FamilyPackageBundle,
    dataset: ManifestDataset,
    summary: FamilyImportDatasetSummary,
    family_context: FamilyMetadataContext,
    sample_contexts: dict[str, SampleMetadataContext],
    conflict_mode: str = "overwrite",
    progress: DatasetProgressCallback | None = None,
) -> FamilyImportDatasetSummary:
    if not dataset.family_vcf:
        return await _register_only(
            summary,
            "Registered only; direct per-sample GLIMPSE2 BCF haplotype import is not implemented yet",
        )
    if not family_context.assembly_name:
        return await _register_only(summary, "Registered only; family is not linked to a single assembly")
    vcf_path = _resolve_package_path(bundle.root, dataset.family_vcf)
    if vcf_path is None:
        return await _register_only(summary, "Registered only; family_vcf path is unavailable")
    if conflict_mode == "update":
        existing_count = await count_family_small_variants(
            family_context.assembly_name,
            family_context.family_uuid,
            project_ids=family_context.project_ids,
            source="glimpse2",
        )
        existing_haplotype_count = await count_interval_track_source_rows(
            session,
            family_uuid=family_context.family_uuid,
            track_type="haplotype",
            source="glimpse2",
        )
        if existing_count or existing_haplotype_count:
            return summary.model_copy(
                update={
                    "status": "skipped",
                    "message": "Skipped GLIMPSE2 import in update mode because small variants or haplotypes already exist",
                    "summary": {
                        "existing_small_variants": existing_count,
                        "existing_haplotypes": existing_haplotype_count,
                    },
                }
            )

    progress_lock = asyncio.Lock()

    async def report_haplotype_progress(stats: dict[str, Any]) -> None:
        if progress is None:
            return
        async with progress_lock:
            await progress(
                summary.model_copy(
                    update={
                        "status": "running",
                        "message": "Importing GLIMPSE2 VCF and haplotype blocks",
                        "summary": stats,
                    }
                )
            )

    async def run_upload() -> dict[str, Any]:
        async with _local_upload(vcf_path) as upload:
            return await upload_family_small_variant_file(
                session,
                context=family_context,
                sample_contexts=sample_contexts,
                file=upload,
                annotation_file=None,
                overwrite=True,
                format_hint="glimpse2",
                progress=report_haplotype_progress,
            )

    try:
        result = await _run_with_periodic_progress(
            run_upload(),
            report=report_haplotype_progress if progress is not None else None,
            stats={"family_vcf": _display_path(bundle.root, vcf_path)},
        )
    except Exception:
        # The glimpse2 loader owns the imputed small-variant source and the haplotype
        # interval tracks, so scope the small-variant cleanup to glimpse2 (leaving the
        # annotated clair3 SNVs intact) while still clearing its own haplotype blocks.
        with suppress(Exception):
            await delete_family_small_variants(
                family_context.assembly_name,
                family_context.family_uuid,
                source="glimpse2",
            )
        with suppress(Exception):
            await delete_interval_tracks(
                family_context.assembly_name,
                family_uuid=family_context.family_uuid,
                track_type="haplotype",
            )
        with suppress(Exception):
            await delete_interval_track_sources(
                session,
                family_uuid=family_context.family_uuid,
                track_type="haplotype",
            )
        raise
    return summary.model_copy(
        update={
            "status": "imported",
            "message": "Imported GLIMPSE2 family VCF as small variants and haplotype blocks",
            "summary": result,
        }
    )


async def _import_wisecondorx_dataset(
    session: AsyncSession,
    *,
    bundle: FamilyPackageBundle,
    dataset: ManifestDataset,
    summary: FamilyImportDatasetSummary,
    sample_contexts: dict[str, SampleMetadataContext],
    conflict_mode: str = "overwrite",
    progress: DatasetProgressCallback | None = None,
) -> FamilyImportDatasetSummary:
    sample_results: dict[str, Any] = {}
    for sample_id, raw_entry in dataset.per_sample.items():
        sample_context = sample_contexts.get(sample_id)
        if sample_context is None or not isinstance(raw_entry, dict):
            continue
        sample_results[sample_id] = {}

        async def report_track(role: str, stats: dict[str, int]) -> None:
            sample_results.setdefault(sample_id, {})[role] = stats
            if progress is not None:
                await progress(
                    summary.model_copy(
                        update={
                            "status": "running",
                            "message": f"Importing WisecondorX {role} for {sample_id}",
                            "summary": sample_results,
                        }
                    )
                )

        bins_path = _resolve_package_path(bundle.root, raw_entry.get("bins"))
        segments_path = _resolve_package_path(bundle.root, raw_entry.get("segments"))
        if bins_path is not None:
            existing_bins = await _interval_track_count(
                session,
                sample_context=sample_context,
                track_type="coverage",
                source="wisecondorx",
            )
            if conflict_mode == "update" and existing_bins:
                sample_results[sample_id]["bins"] = {"skipped": True, "existing": existing_bins}
            else:
                sample_results[sample_id]["bins"] = await _import_wisecondorx_track(
                    session,
                    sample_context=sample_context,
                    path=bins_path,
                    track_type="coverage",
                    progress=lambda stats, role="bins": report_track(role, stats),
                )
        if segments_path is not None:
            existing_segments = await _interval_track_count(
                session,
                sample_context=sample_context,
                track_type="segments",
                source="wisecondorx",
            )
            if conflict_mode == "update" and existing_segments:
                sample_results[sample_id]["segments"] = {"skipped": True, "existing": existing_segments}
            else:
                sample_results[sample_id]["segments"] = await _import_wisecondorx_track(
                    session,
                    sample_context=sample_context,
                    path=segments_path,
                    track_type="segments",
                    progress=lambda stats, role="segments": report_track(role, stats),
                )
    skipped = [
        f"{sample_id}:{role}"
        for sample_id, roles in sample_results.items()
        for role, stats in roles.items()
        if isinstance(stats, dict) and stats.get("existing") is not None
    ]
    return summary.model_copy(
        update={
            "status": "imported",
            "message": (
                "Imported WisecondorX bins as coverage and segments as segment interval tracks"
                if not skipped
                else f"Imported WisecondorX data; skipped existing tracks in update mode: {', '.join(skipped)}"
            ),
            "summary": sample_results,
        }
    )


async def _import_qdnaseq_dataset(
    session: AsyncSession,
    *,
    bundle: FamilyPackageBundle,
    dataset: ManifestDataset,
    summary: FamilyImportDatasetSummary,
    sample_contexts: dict[str, SampleMetadataContext],
    conflict_mode: str = "overwrite",
    progress: DatasetProgressCallback | None = None,
) -> FamilyImportDatasetSummary:
    sample_results: dict[str, Any] = {}
    for sample_id, raw_entry in dataset.per_sample.items():
        sample_context = sample_contexts.get(sample_id)
        if sample_context is None or not isinstance(raw_entry, dict):
            continue
        sample_results[sample_id] = {}

        async def report_track(role: str, stats: dict[str, int]) -> None:
            sample_results.setdefault(sample_id, {})[role] = stats
            if progress is not None:
                await progress(
                    summary.model_copy(
                        update={
                            "status": "running",
                            "message": f"Importing QDNAseq {role} for {sample_id}",
                            "summary": sample_results,
                        }
                    )
                )

        bins_path = _resolve_package_path(bundle.root, raw_entry.get("bins") or raw_entry.get("file"))
        segments_path = _resolve_package_path(bundle.root, raw_entry.get("segments"))
        if bins_path is not None:
            existing_bins = await _interval_track_count(
                session,
                sample_context=sample_context,
                track_type="coverage",
                source="qdnaseq",
            )
            if conflict_mode == "update" and existing_bins:
                sample_results[sample_id]["bins"] = {"skipped": True, "existing": existing_bins}
            else:
                sample_results[sample_id]["bins"] = await _import_copy_number_track(
                    session,
                    sample_context=sample_context,
                    path=bins_path,
                    track_type="coverage",
                    source="qdnaseq",
                    progress=lambda stats, role="bins": report_track(role, stats),
                )
        if segments_path is not None:
            existing_segments = await _interval_track_count(
                session,
                sample_context=sample_context,
                track_type="segments",
                source="qdnaseq",
            )
            if conflict_mode == "update" and existing_segments:
                sample_results[sample_id]["segments"] = {"skipped": True, "existing": existing_segments}
            else:
                sample_results[sample_id]["segments"] = await _import_copy_number_track(
                    session,
                    sample_context=sample_context,
                    path=segments_path,
                    track_type="segments",
                    source="qdnaseq",
                    progress=lambda stats, role="segments": report_track(role, stats),
                )
    skipped = [
        f"{sample_id}:{role}"
        for sample_id, roles in sample_results.items()
        for role, stats in roles.items()
        if isinstance(stats, dict) and stats.get("existing") is not None
    ]
    return summary.model_copy(
        update={
            "status": "imported",
            "message": (
                "Imported QDNAseq bins as coverage and segments as segment interval tracks"
                if not skipped
                else f"Imported QDNAseq data; skipped existing tracks in update mode: {', '.join(skipped)}"
            ),
            "summary": sample_results,
        }
    )


async def _import_sv_needlr_dataset(
    session: AsyncSession,
    *,
    bundle: FamilyPackageBundle,
    dataset: ManifestDataset,
    summary: FamilyImportDatasetSummary,
    family_context: FamilyMetadataContext,
    sample_contexts: dict[str, SampleMetadataContext],
    conflict_mode: str = "overwrite",
) -> FamilyImportDatasetSummary:
    if not family_context.assembly_name:
        return await _register_only(summary, "Registered only; family is not linked to a single assembly")
    vcf_path = _resolve_package_path(bundle.root, dataset.family_vcf)
    if vcf_path is None:
        return await _register_only(summary, "Registered only; family_vcf path is unavailable")
    if conflict_mode == "update":
        existing_count = await count_family_structural_variants(
            family_context.assembly_name,
            family_context.family_uuid,
            project_ids=family_context.project_ids,
            source="needlr",
        )
        if existing_count:
            return summary.model_copy(
                update={
                    "status": "skipped",
                    "message": "Skipped Needlr SV import in update mode because Needlr SVs already exist for this family",
                    "summary": {"existing": existing_count},
                }
            )
    text_value = _read_package_text(vcf_path)
    records = _iter_needlr_structural_records(
        text_value,
        ped=bundle.ped,
        sample_contexts=sample_contexts,
    )
    if not records:
        raise RuntimeError("No Needlr structural variants with PED sample calls were found")
    await replace_family_structural_variants(
        family_context.assembly_name,
        family_context.family_uuid,
        family_context.project_ids,
        records,
        source="needlr",
    )
    await _update_sv_file_metadata(
        session,
        sample_contexts=sample_contexts,
        source="needlr",
        filename=vcf_path.name,
    )
    # Capture SV provenance into the family's annotation manifest (best-effort;
    # joins the import transaction). The NeedlR SV VCF carries no structured version
    # header lines — its annotation-database releases (GENCODE/OMIM/GenCC/gnomAD/
    # GIAB) live in the ``##INFO`` descriptions — so mine those too.
    from .annotation_manifest_service import merge_vcf_header_provenance
    from .vcf_header_provenance import (
        extract_header_provenance,
        extract_info_description_provenance,
        merge_module_maps,
    )

    sv_lines = text_value.splitlines()
    sv_modules = merge_module_maps(
        extract_header_provenance(sv_lines, modality="sv").as_modules(),
        extract_info_description_provenance(sv_lines),
    )
    await merge_vcf_header_provenance(
        session,
        family_uuid=family_context.family_uuid,
        assembly_id=getattr(family_context, "assembly_id", None),
        modules=sv_modules,
        modality="sv",
    )
    return summary.model_copy(
        update={
            "status": "imported",
            "message": "Imported Needlr family SV VCF into structural variant storage",
            "summary": {
                "processed": len(records),
                "source": "needlr",
            },
        }
    )


async def _import_apcad_dataset(
    session: AsyncSession,
    *,
    bundle: FamilyPackageBundle,
    dataset: ManifestDataset,
    summary: FamilyImportDatasetSummary,
    sample_contexts: dict[str, SampleMetadataContext],
    conflict_mode: str = "overwrite",
) -> FamilyImportDatasetSummary:
    if dataset.family_vcf:
        vcf_path = _resolve_package_path(bundle.root, dataset.family_vcf)
        if vcf_path is None:
            return await _register_only(summary, "Registered only; family_vcf path is unavailable")
        embryo_sample_ids = _ped_embryo_sample_ids(bundle.ped)
        target_sample_contexts = (
            {
                sample_id: sample_context
                for sample_id, sample_context in sample_contexts.items()
                if sample_id in embryo_sample_ids
            }
            or sample_contexts
        )
        existing_by_sample = {
            sample_id: await _interval_track_count(
                session,
                sample_context=sample_context,
                track_type="apcad",
            )
            for sample_id, sample_context in target_sample_contexts.items()
        }
        if conflict_mode == "update" and any(existing_by_sample.values()):
            return summary.model_copy(
                update={
                    "status": "skipped",
                    "message": "Skipped APCAD import in update mode because APCAD tracks already exist",
                    "summary": {"existing": existing_by_sample},
                }
            )
        sample_results = await _import_apcad_track_file(
            session,
            sample_contexts=target_sample_contexts,
            path=vcf_path,
            ped=bundle.ped,
        )
        return summary.model_copy(
            update={
                "status": "imported",
                "message": "Imported APCAD VCF into embryo APCAD interval tracks",
                "summary": sample_results,
            }
        )
    if not dataset.per_sample:
        return await _register_only(
            summary,
            "Registered only; this manifest uses a family-level APCAD BED and existing loaders are sample-scoped",
        )
    sample_results: dict[str, Any] = {}
    for sample_id, raw_entry in dataset.per_sample.items():
        sample_context = sample_contexts.get(sample_id)
        if sample_context is None or not isinstance(raw_entry, dict):
            continue
        bed_path = _resolve_package_path(
            bundle.root,
            raw_entry.get("bed") or raw_entry.get("file") or raw_entry.get("vcf"),
        )
        if bed_path is None:
            continue
        existing_count = await _interval_track_count(
            session,
            sample_context=sample_context,
            track_type="apcad",
        )
        if conflict_mode == "update" and existing_count:
            sample_results[sample_id] = {"skipped": True, "existing": existing_count}
            continue
        import_result = await _import_apcad_track_file(
            session,
            sample_contexts=sample_contexts,
            path=bed_path,
            ped=bundle.ped,
            selected_sample_id=sample_id,
            selected_vcf_sample=raw_entry.get("sample_name") or raw_entry.get("vcf_sample"),
        )
        sample_results[sample_id] = (
            import_result.get(sample_id, import_result)
            if isinstance(import_result, dict)
            else import_result
        )
        if not import_result:
            async with _local_upload(bed_path) as upload:
                sample_results[sample_id] = await upload_bed_data(
                    session,
                    sample_context=sample_context,
                    bed_type="apcad",
                    file=upload,
                    overwrite=True,
                )
    skipped = [
        sample_id
        for sample_id, stats in sample_results.items()
        if isinstance(stats, dict) and stats.get("existing") is not None
    ]
    return summary.model_copy(
        update={
            "status": "imported",
            "message": (
                "Imported APCAD data into interval tracks"
                if not skipped
                else f"Imported APCAD data; skipped existing samples in update mode: {', '.join(skipped)}"
            ),
            "summary": sample_results,
        }
    )


async def _import_coverage_dataset(
    session: AsyncSession,
    *,
    bundle: FamilyPackageBundle,
    dataset: ManifestDataset,
    summary: FamilyImportDatasetSummary,
    sample_contexts: dict[str, SampleMetadataContext],
    conflict_mode: str = "overwrite",
) -> FamilyImportDatasetSummary:
    if not dataset.per_sample:
        return await _register_only(
            summary, "Registered only; coverage dataset has no per_sample entries"
        )
    sample_results: dict[str, Any] = {}
    for sample_id, raw_entry in dataset.per_sample.items():
        sample_context = sample_contexts.get(sample_id)
        if sample_context is None or not isinstance(raw_entry, dict):
            continue
        bed_path = _resolve_package_path(
            bundle.root, raw_entry.get("bed") or raw_entry.get("file")
        )
        if bed_path is None:
            continue
        existing_count = await _interval_track_count(
            session, sample_context=sample_context, track_type="coverage"
        )
        if conflict_mode == "update" and existing_count:
            sample_results[sample_id] = {"skipped": True, "existing": existing_count}
            continue
        async with _local_upload(bed_path) as upload:
            sample_results[sample_id] = await upload_bed_data(
                session,
                sample_context=sample_context,
                bed_type="coverage",
                file=upload,
                overwrite=True,
            )
    skipped = [
        sample_id
        for sample_id, stats in sample_results.items()
        if isinstance(stats, dict) and stats.get("existing") is not None
    ]
    return summary.model_copy(
        update={
            "status": "imported",
            "message": (
                "Imported coverage into interval tracks"
                if not skipped
                else f"Imported coverage; skipped existing samples in update mode: {', '.join(skipped)}"
            ),
            "summary": sample_results,
        }
    )


async def _import_pcf_dataset(
    session: AsyncSession,
    *,
    bundle: FamilyPackageBundle,
    dataset: ManifestDataset,
    summary: FamilyImportDatasetSummary,
    sample_contexts: dict[str, SampleMetadataContext],
    conflict_mode: str = "overwrite",
) -> FamilyImportDatasetSummary:
    if not dataset.per_sample:
        return await _register_only(summary, "No PCF segment files were provided")
    sample_results: dict[str, Any] = {}
    for sample_id, raw_entry in dataset.per_sample.items():
        sample_context = sample_contexts.get(sample_id)
        if sample_context is None or not isinstance(raw_entry, dict):
            continue
        role_paths: list[tuple[str, Path]] = []
        for role, origin in (("maternal", "maternal"), ("paternal", "paternal")):
            path = _resolve_package_path(bundle.root, _pcf_role_path(raw_entry, role))
            if path is not None:
                role_paths.append((origin, path))
        if not role_paths:
            continue

        existing_count = await count_interval_track_source_rows(
            session,
            sample_uuid=sample_context.sample_uuid,
            track_type=APCAD_PCF_TRACK_TYPE,
            source=APCAD_PCF_SOURCE,
        )
        if conflict_mode == "update" and existing_count:
            sample_results[sample_id] = {"skipped": True, "existing": existing_count}
            continue

        await _delete_sample_interval_source(
            session,
            sample_context=sample_context,
            track_type=APCAD_PCF_TRACK_TYPE,
            source=APCAD_PCF_SOURCE,
        )
        sample_results[sample_id] = {}
        for origin, path in role_paths:
            sample_results[sample_id][origin] = await _import_pcf_segment_file(
                session,
                sample_context=sample_context,
                path=path,
                origin=origin,
            )

    skipped = [
        sample_id
        for sample_id, stats in sample_results.items()
        if isinstance(stats, dict) and stats.get("existing") is not None
    ]
    return summary.model_copy(
        update={
            "status": "imported" if sample_results else "skipped",
            "message": (
                "Imported PCF APCAD segment overlays into interval tracks"
                if sample_results and not skipped
                else f"Imported PCF data; skipped existing samples in update mode: {', '.join(skipped)}"
                if skipped
                else "No PCF segment files were imported"
            ),
            "summary": sample_results,
        }
    )


async def _import_repeats_dataset(
    session: AsyncSession,
    *,
    bundle: FamilyPackageBundle,
    dataset: ManifestDataset,
    summary: FamilyImportDatasetSummary,
    sample_contexts: dict[str, SampleMetadataContext],
    conflict_mode: str = "overwrite",
) -> FamilyImportDatasetSummary:
    if conflict_mode == "update":
        existing_count = await _repeat_expansion_count(session, sample_contexts=sample_contexts)
        if existing_count:
            return summary.model_copy(
                update={
                    "status": "skipped",
                    "message": "Skipped TRGT repeat import in update mode because repeat expansions already exist for this family",
                    "summary": {"existing": existing_count},
                }
            )
    family_vcf_path = _resolve_package_path(bundle.root, dataset.family_vcf)
    if family_vcf_path is not None:
        async with _local_upload(family_vcf_path) as upload:
            text_value = await decode_repeat_upload_text(upload)
            result = await ingest_family_trgt_text(
                session,
                sample_contexts=sample_contexts,
                text_value=text_value,
                metadata={
                    "source": "trgt_family",
                    "filename": family_vcf_path.name,
                    "uploaded_from": "family_package",
                    "family_vcf": _display_path(bundle.root, family_vcf_path),
                },
            )
        return summary.model_copy(
            update={
                "status": "imported",
                "message": "Imported family TRGT VCF through existing repeat-expansion storage",
                "summary": result,
            }
        )
    if not dataset.per_sample:
        return await _register_only(
            summary,
            "Registered only; no family VCF or per-sample TRGT files were provided",
        )
    sample_results: dict[str, Any] = {}
    for sample_id, raw_entry in dataset.per_sample.items():
        sample_context = sample_contexts.get(sample_id)
        if sample_context is None or not isinstance(raw_entry, dict):
            continue
        vcf_path = _resolve_package_path(bundle.root, raw_entry.get("file") or raw_entry.get("vcf"))
        if vcf_path is None:
            continue
        await clear_sample_repeat_expansions(session, sample_uuid=sample_context.sample_uuid)
        async with _local_upload(vcf_path) as upload:
            text_value = await decode_repeat_upload_text(upload)
            sample_results[sample_id] = await ingest_trgt_text(
                session,
                sample_context=sample_context,
                text_value=text_value,
                metadata={
                    "source": "trgt",
                    "filename": vcf_path.name,
                    "uploaded_from": "family_package",
                },
            )
    return summary.model_copy(
        update={
            "status": "imported",
            "message": "Imported sample-scoped TRGT files through existing repeat-expansion loader",
            "summary": sample_results,
        }
    )


async def _import_paraphase_dataset(
    session: AsyncSession,
    *,
    bundle: FamilyPackageBundle,
    dataset: ManifestDataset,
    summary: FamilyImportDatasetSummary,
    sample_contexts: dict[str, SampleMetadataContext],
    conflict_mode: str = "overwrite",
) -> FamilyImportDatasetSummary:
    sample_results: dict[str, Any] = {}
    for sample_id, raw_entry in dataset.per_sample.items():
        sample_context = sample_contexts.get(sample_id)
        if sample_context is None or not isinstance(raw_entry, dict):
            continue
        existing_count = await _paraphase_count(session, sample_context=sample_context)
        if conflict_mode == "update" and existing_count:
            sample_results[sample_id] = {"skipped": True, "existing": existing_count}
            continue
        json_path = _resolve_package_path(bundle.root, raw_entry.get("json"))
        if json_path is None:
            continue
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError(f"Paraphase JSON for {sample_id} must contain an object")
        rows = _paraphase_rows_for_sample(
            sample_context=sample_context,
            path=json_path,
            payload=payload,
        )
        await _replace_sample_paraphase_rows(
            session,
            sample_context=sample_context,
            rows=rows,
        )
        sample_results[sample_id] = {
            "genes": len(rows),
            "filename": json_path.name,
        }
    skipped = [
        sample_id
        for sample_id, stats in sample_results.items()
        if isinstance(stats, dict) and stats.get("existing") is not None
    ]
    return summary.model_copy(
        update={
            "status": "imported",
            "message": (
                "Imported Paraphase JSON into sample paraphase result storage"
                if not skipped
                else f"Imported Paraphase JSON; skipped existing samples in update mode: {', '.join(skipped)}"
            ),
            "summary": sample_results,
        }
    )


async def _import_phenotypes_dataset(
    session: AsyncSession,
    *,
    bundle: FamilyPackageBundle,
    summary: FamilyImportDatasetSummary,
    family_context: FamilyMetadataContext,
    sample_contexts: dict[str, SampleMetadataContext],
) -> FamilyImportDatasetSummary:
    rows, issues, _files, fatal_errors = _manifest_hpo_rows(
        root=bundle.root,
        manifest=bundle.manifest,
        family_id=family_context.family_id,
    )
    if fatal_errors:
        return summary.model_copy(
            update={
                "status": "failed",
                "message": "; ".join(error.message for error in fatal_errors),
                "summary": {"errors": [error.model_dump() for error in fatal_errors]},
            }
        )
    result = await import_family_hpo_annotations(
        session,
        family_uuid=family_context.family_uuid,
        family_id=family_context.family_id,
        sample_uuids_by_id={
            sample_id: sample_context.sample_uuid
            for sample_id, sample_context in sample_contexts.items()
        },
        rows=rows,
        issues=issues,
    )
    status = "imported" if result["imported"] else "skipped"
    if result["errors"]:
        status = "warning" if result["imported"] else "skipped"
    return summary.model_copy(
        update={
            "status": status,
            "message": (
                f"Imported {result['imported']} HPO phenotype annotation row(s)"
                if result["imported"]
                else "No HPO phenotype annotation rows were imported"
            ),
            "summary": {
                **result,
                "assumption": "PED phenotype remains coarse affected/unaffected status; detailed HPO phenotypes are stored in individual_hpo.",
            },
        }
    )


async def _import_dataset(
    session: AsyncSession,
    *,
    bundle: FamilyPackageBundle,
    summary: FamilyImportDatasetSummary,
    family_context: FamilyMetadataContext,
    sample_contexts: dict[str, SampleMetadataContext],
    conflict_mode: str = "overwrite",
    progress: DatasetProgressCallback | None = None,
) -> FamilyImportDatasetSummary:
    if summary.dataset_type == "phenotypes":
        return await _import_phenotypes_dataset(
            session,
            bundle=bundle,
            summary=summary,
            family_context=family_context,
            sample_contexts=sample_contexts,
        )
    dataset = bundle.manifest.datasets.get(summary.dataset_type)
    if dataset is None or not dataset.enabled:
        return summary
    if summary.dataset_type == "snv":
        return await _import_snv_dataset(
            session,
            bundle=bundle,
            dataset=dataset,
            summary=summary,
            family_context=family_context,
            sample_contexts=sample_contexts,
            conflict_mode=conflict_mode,
            progress=progress,
        )
    if summary.dataset_type == "wisecondorx":
        return await _import_wisecondorx_dataset(
            session,
            bundle=bundle,
            dataset=dataset,
            summary=summary,
            sample_contexts=sample_contexts,
            conflict_mode=conflict_mode,
            progress=progress,
        )
    if summary.dataset_type == "qdnaseq":
        return await _import_qdnaseq_dataset(
            session,
            bundle=bundle,
            dataset=dataset,
            summary=summary,
            sample_contexts=sample_contexts,
            conflict_mode=conflict_mode,
            progress=progress,
        )
    if summary.dataset_type == "apcad":
        return await _import_apcad_dataset(
            session,
            bundle=bundle,
            dataset=dataset,
            summary=summary,
            sample_contexts=sample_contexts,
            conflict_mode=conflict_mode,
        )
    if summary.dataset_type == "coverage":
        return await _import_coverage_dataset(
            session,
            bundle=bundle,
            dataset=dataset,
            summary=summary,
            sample_contexts=sample_contexts,
            conflict_mode=conflict_mode,
        )
    if summary.dataset_type == "pcf":
        return await _import_pcf_dataset(
            session,
            bundle=bundle,
            dataset=dataset,
            summary=summary,
            sample_contexts=sample_contexts,
            conflict_mode=conflict_mode,
        )
    if summary.dataset_type == "repeats_trgt":
        return await _import_repeats_dataset(
            session,
            bundle=bundle,
            dataset=dataset,
            summary=summary,
            sample_contexts=sample_contexts,
            conflict_mode=conflict_mode,
        )
    if summary.dataset_type == "sv_needlr":
        return await _import_sv_needlr_dataset(
            session,
            bundle=bundle,
            dataset=dataset,
            summary=summary,
            family_context=family_context,
            sample_contexts=sample_contexts,
            conflict_mode=conflict_mode,
        )
    if summary.dataset_type == "haplotypes":
        return await _import_haplotypes_dataset(
            session,
            bundle=bundle,
            dataset=dataset,
            summary=summary,
            family_context=family_context,
            sample_contexts=sample_contexts,
            conflict_mode=conflict_mode,
            progress=progress,
        )
    if summary.dataset_type == "paraphase":
        return await _import_paraphase_dataset(
            session,
            bundle=bundle,
            dataset=dataset,
            summary=summary,
            sample_contexts=sample_contexts,
            conflict_mode=conflict_mode,
        )
    return summary

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.sql import uuid_list_bindparam, uuid_values
from ..schemas import (
    GeneLocation,
    GenePanelCreate,
    GenePanelCreateResponse,
    GenePanelOut,
    PanelAppImportRequest,
    PanelAppImportResponse,
)
from .metadata_service import CurrentUser
from .panelapp_service import (
    extract_panelapp_import_content,
    fetch_panelapp_panel,
    panelapp_default_panel_name,
    panelapp_panel_url,
)

_panel_source_schema_ready = False


def _require_panel_uuid(panel_id: str) -> None:
    try:
        UUID(panel_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid panel id") from exc


def _ensure_admin(user: CurrentUser) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")


_ASSEMBLY_PRIORITY_SQL = """
CASE
    WHEN a.assembly_name = 'GRCh38' THEN 0
    WHEN a.assembly_name IN ('T2T-CHM13', 'T2T-CHM13v2.0')
         OR a.assembly_name LIKE 'T2T-CHM13%' THEN 1
    WHEN a.assembly_name IN ('GRCh37', 'hg19') THEN 2
    ELSE 9
END
""".strip()


async def _ensure_panel_source_schema(session: AsyncSession) -> None:
    global _panel_source_schema_ready
    if _panel_source_schema_ready:
        return
    for statement in (
        "ALTER TABLE gene_panels ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'local'",
        "ALTER TABLE gene_panels ADD COLUMN IF NOT EXISTS external_id TEXT",
        "ALTER TABLE gene_panels ADD COLUMN IF NOT EXISTS external_version TEXT",
        "ALTER TABLE gene_panels ADD COLUMN IF NOT EXISTS external_url TEXT",
        "ALTER TABLE gene_panels ADD COLUMN IF NOT EXISTS source_updated_at TIMESTAMPTZ",
        "ALTER TABLE gene_panels ADD COLUMN IF NOT EXISTS source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb",
    ):
        await session.execute(text(statement))
    await session.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_gene_panels_source_external
                ON gene_panels (source, external_id)
                WHERE external_id IS NOT NULL
            """
        )
    )
    await session.commit()
    _panel_source_schema_ready = True


def _panel_out_from_rows(
    panel_row: dict[str, Any],
    genes: list[str],
    region_rows: list[dict[str, Any]],
) -> GenePanelOut:
    source_metadata = panel_row.get("source_metadata") or {}
    if isinstance(source_metadata, str):
        try:
            source_metadata = json.loads(source_metadata)
        except json.JSONDecodeError:
            source_metadata = {}
    return GenePanelOut(
        _id=panel_row["id"],
        name=panel_row["name"],
        genes=genes,
        gene_count=len(genes),
        regions=[
            GeneLocation(
                gene=row["gene"],
                chr=row["chr"],
                start=int(row["start"]),
                end=int(row["end"]),
            )
            for row in region_rows
        ],
        created_by=panel_row["created_by"],
        created_by_email=panel_row.get("created_by_email"),
        created_at=panel_row["created_at"],
        description=panel_row.get("description"),
        source=panel_row.get("source") or "local",
        external_id=panel_row.get("external_id"),
        external_version=panel_row.get("external_version"),
        external_url=panel_row.get("external_url"),
        source_updated_at=panel_row.get("source_updated_at"),
        source_metadata=source_metadata if isinstance(source_metadata, dict) else {},
    )


async def _fetch_panel_rows(
    session: AsyncSession,
    panel_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    await _ensure_panel_source_schema(session)
    if panel_ids is None:
        result = await session.execute(
            text(
                """
                SELECT
                    gp.id::text AS id,
                    gp.name,
                    gp.created_by::text AS created_by,
                    gp.created_at,
                    gp.description,
                    COALESCE(gp.source, 'local') AS source,
                    gp.external_id,
                    gp.external_version,
                    gp.external_url,
                    gp.source_updated_at,
                    COALESCE(gp.source_metadata, '{}'::jsonb) AS source_metadata,
                    COALESCE(NULLIF(u.email, ''), u.username) AS created_by_email
                FROM gene_panels gp
                LEFT JOIN users u ON u.id = gp.created_by
                ORDER BY lower(name)
                """
            )
        )
        return [dict(row) for row in result.mappings().all()]
    if not panel_ids:
        return []
    result = await session.execute(
        text(
            """
            SELECT
                gp.id::text AS id,
                gp.name,
                gp.created_by::text AS created_by,
                gp.created_at,
                gp.description,
                COALESCE(gp.source, 'local') AS source,
                gp.external_id,
                gp.external_version,
                gp.external_url,
                gp.source_updated_at,
                COALESCE(gp.source_metadata, '{}'::jsonb) AS source_metadata,
                COALESCE(NULLIF(u.email, ''), u.username) AS created_by_email
            FROM gene_panels gp
            LEFT JOIN users u ON u.id = gp.created_by
            WHERE gp.id IN :panel_ids
            ORDER BY lower(name)
            """
        ).bindparams(uuid_list_bindparam("panel_ids")),
        {"panel_ids": uuid_values(panel_ids)},
    )
    return [dict(row) for row in result.mappings().all()]


async def _fetch_panel_genes(
    session: AsyncSession,
    panel_ids: list[str],
) -> dict[str, list[str]]:
    if not panel_ids:
        return {}
    result = await session.execute(
        text(
            """
            SELECT panel_id::text AS panel_id, gene_symbol
            FROM gene_panel_genes
            WHERE panel_id IN :panel_ids
            ORDER BY gene_symbol
            """
        ).bindparams(uuid_list_bindparam("panel_ids")),
        {"panel_ids": uuid_values(panel_ids)},
    )
    grouped: dict[str, list[str]] = {panel_id: [] for panel_id in panel_ids}
    for row in result.mappings().all():
        grouped.setdefault(row["panel_id"], []).append(row["gene_symbol"])
    return grouped


async def _fetch_panel_regions(
    session: AsyncSession,
    panel_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    if not panel_ids:
        return {}
    result = await session.execute(
        text(
            """
            SELECT panel_id::text AS panel_id, gene, chr, start, "end"
            FROM gene_panel_regions
            WHERE panel_id IN :panel_ids
            ORDER BY gene, chr, start, "end"
            """
        ).bindparams(uuid_list_bindparam("panel_ids")),
        {"panel_ids": uuid_values(panel_ids)},
    )
    grouped: dict[str, list[dict[str, Any]]] = {panel_id: [] for panel_id in panel_ids}
    for row in result.mappings().all():
        grouped.setdefault(row["panel_id"], []).append(dict(row))
    return grouped


async def list_panels_data(session: AsyncSession) -> list[GenePanelOut]:
    panel_rows = await _fetch_panel_rows(session)
    panel_ids = [row["id"] for row in panel_rows]
    genes = await _fetch_panel_genes(session, panel_ids)
    regions = await _fetch_panel_regions(session, panel_ids)
    return [
        _panel_out_from_rows(row, genes.get(row["id"], []), regions.get(row["id"], []))
        for row in panel_rows
    ]


async def get_panel_or_404(
    session: AsyncSession,
    panel_id: str,
) -> GenePanelOut:
    _require_panel_uuid(panel_id)
    panel_rows = await _fetch_panel_rows(session, [panel_id])
    if not panel_rows:
        raise HTTPException(status_code=404, detail="Panel not found")
    genes = await _fetch_panel_genes(session, [panel_id])
    regions = await _fetch_panel_regions(session, [panel_id])
    return _panel_out_from_rows(panel_rows[0], genes.get(panel_id, []), regions.get(panel_id, []))


async def _resolve_gene_regions(
    session: AsyncSession,
    symbols: list[str],
) -> tuple[list[GeneLocation], list[str]]:
    deduped_symbols = list(dict.fromkeys(symbol.strip() for symbol in symbols if symbol and symbol.strip()))
    if not deduped_symbols:
        return [], []
    result = await session.execute(
        text(
            f"""
            SELECT DISTINCT ON (upper(g.hgnc_symbol))
                upper(g.hgnc_symbol) AS symbol_key,
                g.hgnc_symbol,
                g.chr,
                g.start,
                g."end" AS "end"
            FROM genes g
            JOIN assemblies a ON a.id = g.assembly_id
            WHERE upper(g.hgnc_symbol) IN :symbols
            ORDER BY
                upper(g.hgnc_symbol),
                {_ASSEMBLY_PRIORITY_SQL},
                (g."end" - g.start) DESC,
                a.release_date DESC NULLS LAST,
                a.version DESC NULLS LAST,
                g.start,
                g."end"
            """
        ).bindparams(bindparam("symbols", expanding=True)),
        {"symbols": [symbol.upper() for symbol in deduped_symbols]},
    )
    grouped_regions = {str(row["symbol_key"]): dict(row) for row in result.mappings().all()}
    missing_genes: list[str] = []
    regions: list[GeneLocation] = []
    for symbol in deduped_symbols:
        match = grouped_regions.get(symbol.upper())
        if match is None:
            missing_genes.append(symbol)
            continue
        regions.append(
            GeneLocation(
                gene=symbol,
                chr=match["chr"],
                start=int(match["start"]),
                end=int(match["end"]),
            )
        )
    return regions, missing_genes


async def _ensure_panel_name_available(
    session: AsyncSession,
    name: str,
    *,
    existing_panel_id: str | None = None,
) -> None:
    if existing_panel_id is None:
        result = await session.execute(
            text(
                """
                SELECT id::text
                FROM gene_panels
                WHERE name = :name
                """
            ),
            {"name": name},
        )
        if result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Panel already exists")
        return

    result = await session.execute(
        text(
            """
            SELECT id::text
            FROM gene_panels
            WHERE name = :name
              AND id::text <> :existing_panel_id
            """
        ),
        {"name": name, "existing_panel_id": existing_panel_id},
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Panel already exists")


async def _replace_panel_members(
    session: AsyncSession,
    *,
    panel_id: str,
    genes: list[str],
    regions: list[GeneLocation],
) -> None:
    await session.execute(
        text("DELETE FROM gene_panel_genes WHERE panel_id = CAST(:panel_id AS uuid)"),
        {"panel_id": panel_id},
    )
    await session.execute(
        text("DELETE FROM gene_panel_regions WHERE panel_id = CAST(:panel_id AS uuid)"),
        {"panel_id": panel_id},
    )
    if genes:
        await session.execute(
            text(
                """
                INSERT INTO gene_panel_genes (panel_id, gene_symbol)
                VALUES (CAST(:panel_id AS uuid), :gene_symbol)
                """
            ),
            [{"panel_id": panel_id, "gene_symbol": symbol} for symbol in genes],
        )
    if regions:
        await session.execute(
            text(
                """
                INSERT INTO gene_panel_regions (panel_id, gene, chr, start, "end")
                VALUES (CAST(:panel_id AS uuid), :gene, :chr, :start, :end)
                """
            ),
            [
                {
                    "panel_id": panel_id,
                    "gene": region.gene,
                    "chr": region.chr,
                    "start": region.start,
                    "end": region.end,
                }
                for region in regions
            ],
        )


async def create_panel_data(
    session: AsyncSession,
    panel: GenePanelCreate,
    user: CurrentUser,
) -> GenePanelCreateResponse:
    _ensure_admin(user)
    await _ensure_panel_source_schema(session)
    await _ensure_panel_name_available(session, panel.name)

    normalized_symbols = [
        symbol.strip() for symbol in panel.genes if symbol and symbol.strip()
    ]
    deduped_symbols = list(dict.fromkeys(normalized_symbols))
    regions, missing_genes = await _resolve_gene_regions(session, deduped_symbols)

    description = panel.description.strip() if panel.description and panel.description.strip() else None

    created = await session.execute(
        text(
            """
            INSERT INTO gene_panels (name, description, created_by, created_at)
            VALUES (:name, :description, CAST(:created_by AS uuid), :created_at)
            RETURNING
                id::text AS id,
                name,
                created_by::text AS created_by,
                created_at,
                description
            """
        ),
        {
            "name": panel.name,
            "description": description,
            "created_by": user.id,
            "created_at": datetime.now(timezone.utc),
        },
    )
    panel_row = dict(created.mappings().one())
    panel_row["created_by_email"] = user.email
    panel_row["source"] = "local"
    panel_row["external_id"] = None
    panel_row["external_version"] = None
    panel_row["external_url"] = None
    panel_row["source_updated_at"] = None
    panel_row["source_metadata"] = {}
    panel_id = panel_row["id"]

    await _replace_panel_members(session, panel_id=panel_id, genes=deduped_symbols, regions=regions)

    await session.commit()
    panel_out = _panel_out_from_rows(
        panel_row,
        deduped_symbols,
        [
            {
                "gene": region.gene,
                "chr": region.chr,
                "start": region.start,
                "end": region.end,
            }
            for region in regions
        ],
    )
    message = f"Panel created with {len(regions)} of {len(deduped_symbols)} genes"
    if missing_genes:
        message += f"; missing genes: {', '.join(missing_genes)}"
    return GenePanelCreateResponse(
        panel=panel_out,
        message=message,
        missing_genes=missing_genes,
    )


async def import_panelapp_panel_data(
    session: AsyncSession,
    request: PanelAppImportRequest,
    user: CurrentUser,
) -> PanelAppImportResponse:
    _ensure_admin(user)
    await _ensure_panel_source_schema(session)
    if not request.confidence_levels:
        raise HTTPException(status_code=400, detail="At least one PanelApp confidence level is required")

    payload = await fetch_panelapp_panel(request.panelapp_id, version=request.version)
    content = extract_panelapp_import_content(
        payload,
        confidence_levels=request.confidence_levels,
        include_regions=request.include_regions,
        include_strs=request.include_strs,
        assembly=request.assembly,
    )
    genes = content.genes
    region_keys = {region.gene.upper() for region in content.regions}
    unresolved_symbols = [symbol for symbol in genes if symbol.upper() not in region_keys]
    fallback_regions, missing_genes = await _resolve_gene_regions(session, unresolved_symbols)
    regions = content.regions + [
        region
        for region in fallback_regions
        if (region.gene.upper(), region.chr, region.start, region.end)
        not in {(row.gene.upper(), row.chr, row.start, row.end) for row in content.regions}
    ]
    if not genes and not regions:
        raise HTTPException(status_code=400, detail="No PanelApp entities matched the selected import options")

    external_id = str(request.panelapp_id)
    existing = await session.execute(
        text(
            """
            SELECT id::text
            FROM gene_panels
            WHERE source = 'panelapp' AND external_id = :external_id
            """
        ),
        {"external_id": external_id},
    )
    existing_panel_id = existing.scalar_one_or_none()
    name = request.name.strip() if request.name and request.name.strip() else panelapp_default_panel_name(payload)
    await _ensure_panel_name_available(session, name, existing_panel_id=existing_panel_id)

    source_metadata = {
        **content.metadata,
        "missing_coordinate_genes": missing_genes,
    }
    source_metadata_json = json.dumps(source_metadata, sort_keys=True, default=str)
    now = datetime.now(timezone.utc)
    description = (
        f"Imported from PanelApp {request.panelapp_id}"
        f" version {payload.get('version') or request.version or 'latest'}."
    )
    if payload.get("disease_group"):
        description += f" Disease group: {payload['disease_group']}."
    if payload.get("relevant_disorders"):
        description += f" Relevant disorders: {', '.join(str(value) for value in payload['relevant_disorders'])}."

    if existing_panel_id:
        updated = await session.execute(
            text(
                """
                UPDATE gene_panels
                SET
                    name = :name,
                    description = :description,
                    external_version = :external_version,
                    external_url = :external_url,
                    source_updated_at = :source_updated_at,
                    source_metadata = CAST(:source_metadata_json AS jsonb)
                WHERE id = CAST(:panel_id AS uuid)
                RETURNING
                    id::text AS id,
                    name,
                    created_by::text AS created_by,
                    created_at,
                    description,
                    source,
                    external_id,
                    external_version,
                    external_url,
                    source_updated_at,
                    source_metadata
                """
            ),
            {
                "panel_id": existing_panel_id,
                "name": name,
                "description": description,
                "external_version": str(payload.get("version") or request.version or ""),
                "external_url": panelapp_panel_url(request.panelapp_id),
                "source_updated_at": now,
                "source_metadata_json": source_metadata_json,
            },
        )
        panel_row = dict(updated.mappings().one())
        panel_id = panel_row["id"]
    else:
        created = await session.execute(
            text(
                """
                INSERT INTO gene_panels (
                    name,
                    description,
                    source,
                    external_id,
                    external_version,
                    external_url,
                    source_updated_at,
                    source_metadata,
                    created_by,
                    created_at
                )
                VALUES (
                    :name,
                    :description,
                    'panelapp',
                    :external_id,
                    :external_version,
                    :external_url,
                    :source_updated_at,
                    CAST(:source_metadata_json AS jsonb),
                    CAST(:created_by AS uuid),
                    :created_at
                )
                RETURNING
                    id::text AS id,
                    name,
                    created_by::text AS created_by,
                    created_at,
                    description,
                    source,
                    external_id,
                    external_version,
                    external_url,
                    source_updated_at,
                    source_metadata
                """
            ),
            {
                "name": name,
                "description": description,
                "external_id": external_id,
                "external_version": str(payload.get("version") or request.version or ""),
                "external_url": panelapp_panel_url(request.panelapp_id),
                "source_updated_at": now,
                "source_metadata_json": source_metadata_json,
                "created_by": user.id,
                "created_at": now,
            },
        )
        panel_row = dict(created.mappings().one())
        panel_id = panel_row["id"]

    await _replace_panel_members(session, panel_id=panel_id, genes=genes, regions=regions)
    panel_rows = await _fetch_panel_rows(session, [panel_id])
    if panel_rows:
        panel_row = panel_rows[0]
    await session.commit()

    panel_out = _panel_out_from_rows(
        panel_row,
        genes,
        [
            {
                "gene": region.gene,
                "chr": region.chr,
                "start": region.start,
                "end": region.end,
            }
            for region in regions
        ],
    )
    action = "updated" if existing_panel_id else "imported"
    message = (
        f"PanelApp panel {action} with {len(genes)} genes and {len(regions)} regions"
        f" from confidence level{'s' if len(request.confidence_levels) != 1 else ''} "
        f"{', '.join(request.confidence_levels)}"
    )
    if missing_genes:
        message += f"; no coordinates for: {', '.join(missing_genes)}"
    return PanelAppImportResponse(
        panel=panel_out,
        message=message,
        missing_genes=missing_genes,
        imported_gene_count=len(genes),
        imported_region_count=len(regions),
    )


async def delete_panel_data(
    session: AsyncSession,
    panel_id: str,
    user: CurrentUser,
) -> None:
    _ensure_admin(user)
    _require_panel_uuid(panel_id)
    result = await session.execute(
        text("DELETE FROM gene_panels WHERE id = CAST(:panel_id AS uuid)"),
        {"panel_id": panel_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Panel not found")
    await session.commit()

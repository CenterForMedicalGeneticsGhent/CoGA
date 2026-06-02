from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import date
import io
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from fastapi import HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

HPO_ID_PATTERN = re.compile(r"^HP:[0-9]{7}$", re.IGNORECASE)
HPO_ID_SEARCH_PATTERN = re.compile(r"(?:HP[:_])([0-9]{7})", re.IGNORECASE)
HPO_URI_PATTERN = re.compile(r"(?:^|[/_])HP[_:]([0-9]{7})$", re.IGNORECASE)

PRESENT_STATUS_VALUES = {"present", "positive", "observed", "yes", "true", "1"}
ABSENT_STATUS_VALUES = {"absent", "excluded", "negative", "no", "false", "0"}
UNKNOWN_STATUS_VALUES = {"unknown", "uncertain", "na", "n/a", "not_applicable"}
ANNOTATION_STATUSES = {"present", "absent", "unknown"}


@dataclass(slots=True)
class ParsedHpoTerm:
    hpo_id: str
    label: str
    definition: str | None = None
    is_obsolete: bool = False
    replaced_by: str | None = None
    synonyms: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParsedHpoEdge:
    child_id: str
    parent_id: str
    relation: str = "is_a"


@dataclass(slots=True)
class ParsedHpoOntology:
    terms: dict[str, ParsedHpoTerm]
    edges: list[ParsedHpoEdge]


@dataclass(frozen=True, slots=True)
class HpoAnnotationImportIssue:
    line_no: int | None
    code: str
    message: str
    sample_id: str | None = None
    hpo_id: str | None = None


@dataclass(frozen=True, slots=True)
class HpoAnnotationImportRow:
    family_id: str
    individual_id: str
    hpo_id: str
    label: str | None = None
    status: str = "present"
    onset: str | None = None
    evidence: str | None = None
    source: str | None = None
    note: str | None = None
    line_no: int | None = None


def normalize_hpo_id(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    direct_match = HPO_ID_PATTERN.match(cleaned)
    if direct_match:
        return cleaned.upper()
    uri_match = HPO_URI_PATTERN.search(cleaned)
    if uri_match:
        return f"HP:{uri_match.group(1)}"
    search_match = HPO_ID_SEARCH_PATTERN.search(cleaned)
    if search_match:
        return f"HP:{search_match.group(1)}"
    return None


def normalize_annotation_status(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in ANNOTATION_STATUSES:
        return normalized
    if normalized in PRESENT_STATUS_VALUES:
        return "present"
    if normalized in ABSENT_STATUS_VALUES:
        return "absent"
    if normalized in UNKNOWN_STATUS_VALUES:
        return "unknown"
    return None


def _dedupe_preserve_order(values: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        cleaned = (value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def _quoted_value(line: str) -> str | None:
    match = re.search(r'"((?:\\"|[^"])*)"', line)
    if not match:
        return None
    return match.group(1).replace('\\"', '"')


def parse_hpo_obo_text(text_value: str) -> ParsedHpoOntology:
    terms: dict[str, ParsedHpoTerm] = {}
    edges: list[ParsedHpoEdge] = []
    current: dict[str, Any] | None = None

    def flush_current() -> None:
        nonlocal current
        if not current:
            return
        hpo_id = normalize_hpo_id(current.get("id"))
        label = str(current.get("name") or "").strip()
        if not hpo_id or not label:
            current = None
            return
        synonyms = _dedupe_preserve_order(
            [*current.get("synonyms", []), *current.get("alt_ids", [])]
        )
        term = ParsedHpoTerm(
            hpo_id=hpo_id,
            label=label,
            definition=current.get("definition"),
            is_obsolete=bool(current.get("is_obsolete")),
            replaced_by=normalize_hpo_id(current.get("replaced_by")),
            synonyms=synonyms,
            metadata={"alt_ids": current.get("alt_ids", [])},
        )
        terms[hpo_id] = term
        for relation, parent_value in current.get("parents", []):
            parent_id = normalize_hpo_id(parent_value)
            if parent_id:
                edges.append(ParsedHpoEdge(child_id=hpo_id, parent_id=parent_id, relation=relation))
        current = None

    for raw_line in text_value.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("!"):
            continue
        if line == "[Term]":
            flush_current()
            current = {"synonyms": [], "parents": [], "alt_ids": []}
            continue
        if line.startswith("["):
            flush_current()
            current = None
            continue
        if current is None:
            continue
        if line.startswith("id:"):
            current["id"] = line.removeprefix("id:").strip()
        elif line.startswith("name:"):
            current["name"] = line.removeprefix("name:").strip()
        elif line.startswith("def:"):
            current["definition"] = _quoted_value(line)
        elif line.startswith("synonym:"):
            synonym = _quoted_value(line)
            if synonym:
                current["synonyms"].append(synonym)
        elif line.startswith("alt_id:"):
            alt_id = normalize_hpo_id(line.removeprefix("alt_id:").strip())
            if alt_id:
                current["alt_ids"].append(alt_id)
        elif line.startswith("is_a:"):
            parent_id = line.removeprefix("is_a:").strip().split()[0]
            current["parents"].append(("is_a", parent_id))
        elif line.startswith("relationship:"):
            parts = line.removeprefix("relationship:").strip().split()
            if len(parts) >= 2 and normalize_hpo_id(parts[1]):
                current["parents"].append((parts[0], parts[1]))
        elif line.startswith("is_obsolete:"):
            current["is_obsolete"] = line.removeprefix("is_obsolete:").strip().lower() == "true"
        elif line.startswith("replaced_by:"):
            current["replaced_by"] = line.removeprefix("replaced_by:").strip()
    flush_current()

    return ParsedHpoOntology(terms=terms, edges=edges)


def _json_graphs(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    graphs = payload.get("graphs")
    if isinstance(graphs, list):
        return [graph for graph in graphs if isinstance(graph, dict)]
    graph = payload.get("graph")
    if isinstance(graph, dict):
        return [graph]
    if isinstance(payload.get("nodes"), list) or isinstance(payload.get("edges"), list):
        return [payload]
    return []


def _json_definition(meta: Mapping[str, Any]) -> str | None:
    definition = meta.get("definition")
    if isinstance(definition, dict):
        value = definition.get("val") or definition.get("value")
        return str(value).strip() if value else None
    if isinstance(definition, str):
        return definition.strip() or None
    return None


def _json_synonyms(meta: Mapping[str, Any]) -> list[str]:
    raw_synonyms = meta.get("synonyms")
    if not isinstance(raw_synonyms, list):
        return []
    values: list[str] = []
    for synonym in raw_synonyms:
        if isinstance(synonym, dict):
            value = synonym.get("val") or synonym.get("value")
            if value:
                values.append(str(value))
        elif isinstance(synonym, str):
            values.append(synonym)
    return _dedupe_preserve_order(values)


def _json_replaced_by(meta: Mapping[str, Any]) -> str | None:
    basic_values = meta.get("basicPropertyValues")
    if not isinstance(basic_values, list):
        return None
    for item in basic_values:
        if not isinstance(item, dict):
            continue
        pred = str(item.get("pred") or "").lower()
        if "replaced_by" not in pred and "term_replaced_by" not in pred:
            continue
        replacement = normalize_hpo_id(str(item.get("val") or item.get("value") or ""))
        if replacement:
            return replacement
    return None


def parse_hpo_json_text(text_value: str) -> ParsedHpoOntology:
    payload = json.loads(text_value)
    terms: dict[str, ParsedHpoTerm] = {}
    edges: list[ParsedHpoEdge] = []
    for graph in _json_graphs(payload):
        for node in graph.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            hpo_id = normalize_hpo_id(str(node.get("id") or ""))
            if not hpo_id:
                continue
            label = str(node.get("lbl") or node.get("label") or node.get("name") or "").strip()
            if not label:
                continue
            meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
            terms[hpo_id] = ParsedHpoTerm(
                hpo_id=hpo_id,
                label=label,
                definition=_json_definition(meta),
                is_obsolete=bool(meta.get("deprecated") or node.get("deprecated")),
                replaced_by=_json_replaced_by(meta),
                synonyms=_json_synonyms(meta),
                metadata={},
            )
        for edge in graph.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            child_id = normalize_hpo_id(str(edge.get("sub") or edge.get("subject") or ""))
            parent_id = normalize_hpo_id(str(edge.get("obj") or edge.get("object") or ""))
            if not child_id or not parent_id:
                continue
            relation = str(edge.get("pred") or edge.get("predicate") or "is_a").split("/")[-1]
            edges.append(ParsedHpoEdge(child_id=child_id, parent_id=parent_id, relation=relation))
    return ParsedHpoOntology(terms=terms, edges=edges)


def parse_hpo_ontology_path(path: str | Path) -> ParsedHpoOntology:
    resolved = Path(path)
    text_value = resolved.read_text(encoding="utf-8")
    if resolved.suffix.lower() == ".json":
        return parse_hpo_json_text(text_value)
    return parse_hpo_obo_text(text_value)


def compute_hpo_closure(
    terms: Iterable[str],
    edges: Iterable[ParsedHpoEdge],
) -> list[tuple[str, str, int]]:
    term_ids = {term_id for term_id in terms if normalize_hpo_id(term_id)}
    parents_by_child: dict[str, set[str]] = {}
    for edge in edges:
        child_id = normalize_hpo_id(edge.child_id)
        parent_id = normalize_hpo_id(edge.parent_id)
        if not child_id or not parent_id:
            continue
        term_ids.add(child_id)
        term_ids.add(parent_id)
        parents_by_child.setdefault(child_id, set()).add(parent_id)

    closure: list[tuple[str, str, int]] = []
    for hpo_id in sorted(term_ids):
        visited = {hpo_id: 0}
        queue: list[tuple[str, int]] = [(parent, 1) for parent in sorted(parents_by_child.get(hpo_id, set()))]
        while queue:
            ancestor_id, distance = queue.pop(0)
            previous_distance = visited.get(ancestor_id)
            if previous_distance is not None and previous_distance <= distance:
                continue
            visited[ancestor_id] = distance
            queue.extend((parent, distance + 1) for parent in sorted(parents_by_child.get(ancestor_id, set())))
        closure.extend((hpo_id, ancestor_id, distance) for ancestor_id, distance in visited.items())
    return sorted(closure, key=lambda item: (item[0], item[2], item[1]))


async def import_hpo_ontology(
    session: AsyncSession,
    *,
    path: str | Path,
    release_version: str | None = None,
    release_date: date | None = None,
    commit: bool = True,
) -> dict[str, int]:
    ontology = parse_hpo_ontology_path(path)
    if not ontology.terms:
        raise ValueError("HPO ontology import found no terms")

    term_rows = [
        {
            "hpo_id": term.hpo_id,
            "label": term.label,
            "definition": term.definition,
            "is_obsolete": term.is_obsolete,
            "replaced_by": term.replaced_by,
            "release_version": release_version,
            "release_date": release_date,
            "metadata": json.dumps(term.metadata),
        }
        for term in ontology.terms.values()
    ]
    await session.execute(
        text(
            """
            INSERT INTO hpo_term (
                hpo_id, label, definition, is_obsolete, replaced_by,
                release_version, release_date, metadata, updated_at
            )
            VALUES (
                :hpo_id, :label, :definition, :is_obsolete, :replaced_by,
                :release_version, :release_date, CAST(:metadata AS jsonb), timezone('utc', now())
            )
            ON CONFLICT (hpo_id) DO UPDATE SET
                label = EXCLUDED.label,
                definition = EXCLUDED.definition,
                is_obsolete = EXCLUDED.is_obsolete,
                replaced_by = EXCLUDED.replaced_by,
                release_version = EXCLUDED.release_version,
                release_date = EXCLUDED.release_date,
                metadata = EXCLUDED.metadata,
                updated_at = timezone('utc', now())
            """
        ),
        term_rows,
    )

    await session.execute(text("DELETE FROM hpo_synonym"))
    synonym_rows = [
        {"hpo_id": term.hpo_id, "synonym": synonym}
        for term in ontology.terms.values()
        for synonym in term.synonyms
    ]
    if synonym_rows:
        await session.execute(
            text(
                """
                INSERT INTO hpo_synonym (hpo_id, synonym)
                VALUES (:hpo_id, :synonym)
                ON CONFLICT DO NOTHING
                """
            ),
            synonym_rows,
        )

    await session.execute(text("DELETE FROM hpo_edge"))
    ontology_term_ids = set(ontology.terms)
    edge_rows = [
        {
            "child_id": edge.child_id,
            "parent_id": edge.parent_id,
            "relation": edge.relation or "is_a",
        }
        for edge in ontology.edges
        if edge.child_id in ontology_term_ids and edge.parent_id in ontology_term_ids
    ]
    if edge_rows:
        await session.execute(
            text(
                """
                INSERT INTO hpo_edge (child_id, parent_id, relation)
                VALUES (:child_id, :parent_id, :relation)
                ON CONFLICT DO NOTHING
                """
            ),
            edge_rows,
        )

    await session.execute(text("DELETE FROM hpo_closure"))
    closure_rows = [
        {"hpo_id": hpo_id, "ancestor_id": ancestor_id, "distance": distance}
        for hpo_id, ancestor_id, distance in compute_hpo_closure(ontology.terms, ontology.edges)
        if hpo_id in ontology_term_ids and ancestor_id in ontology_term_ids
    ]
    if closure_rows:
        await session.execute(
            text(
                """
                INSERT INTO hpo_closure (hpo_id, ancestor_id, distance)
                VALUES (:hpo_id, :ancestor_id, :distance)
                ON CONFLICT (hpo_id, ancestor_id) DO UPDATE SET distance = EXCLUDED.distance
                """
            ),
            closure_rows,
        )

    if commit:
        await session.commit()
    return {
        "terms": len(term_rows),
        "synonyms": len(synonym_rows),
        "edges": len(edge_rows),
        "closure_rows": len(closure_rows),
    }


def _row_value(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    return str(value).strip() if value is not None else ""


def parse_hpo_tsv_text(
    text_value: str,
    *,
    expected_family_id: str | None = None,
    default_source: str | None = None,
) -> tuple[list[HpoAnnotationImportRow], list[HpoAnnotationImportIssue]]:
    reader = csv.DictReader(io.StringIO(text_value), delimiter="\t")
    required_fields = {"family_id", "individual_id", "hpo_id", "status"}
    fieldnames = {str(field).strip().lower() for field in (reader.fieldnames or []) if field}
    if not required_fields.issubset(fieldnames):
        missing = ", ".join(sorted(required_fields - fieldnames))
        return [], [
            HpoAnnotationImportIssue(
                line_no=1,
                code="phenotype_header_invalid",
                message=f"Phenotype TSV header is missing required column(s): {missing}",
            )
        ]

    rows: list[HpoAnnotationImportRow] = []
    issues: list[HpoAnnotationImportIssue] = []
    for index, raw_row in enumerate(reader, start=2):
        row = {str(key).strip().lower(): str(value or "").strip() for key, value in raw_row.items() if key}
        family_id = _row_value(row, "family_id")
        individual_id = _row_value(row, "individual_id")
        hpo_id = normalize_hpo_id(_row_value(row, "hpo_id"))
        status = normalize_annotation_status(_row_value(row, "status"))
        if expected_family_id and family_id and family_id != expected_family_id:
            issues.append(
                HpoAnnotationImportIssue(
                    line_no=index,
                    code="phenotype_family_mismatch",
                    message=f"Phenotype row family_id '{family_id}' does not match package family_id '{expected_family_id}'",
                    sample_id=individual_id or None,
                    hpo_id=hpo_id,
                )
            )
            continue
        if not individual_id:
            issues.append(
                HpoAnnotationImportIssue(
                    line_no=index,
                    code="phenotype_sample_missing",
                    message="Phenotype row is missing individual_id",
                    hpo_id=hpo_id,
                )
            )
            continue
        if not hpo_id:
            issues.append(
                HpoAnnotationImportIssue(
                    line_no=index,
                    code="phenotype_hpo_invalid",
                    message="Phenotype row has an invalid HPO identifier",
                    sample_id=individual_id,
                )
            )
            continue
        if not status:
            issues.append(
                HpoAnnotationImportIssue(
                    line_no=index,
                    code="phenotype_status_invalid",
                    message="Phenotype row status must be present, absent, or unknown",
                    sample_id=individual_id,
                    hpo_id=hpo_id,
                )
            )
            continue
        rows.append(
            HpoAnnotationImportRow(
                family_id=family_id or expected_family_id or "",
                individual_id=individual_id,
                hpo_id=hpo_id,
                label=_row_value(row, "label") or None,
                status=status,
                onset=_row_value(row, "onset") or None,
                evidence=_row_value(row, "evidence") or None,
                source=_row_value(row, "source") or default_source,
                note=_row_value(row, "note") or None,
                line_no=index,
            )
        )
    return rows, issues


def parse_hpo_tsv_path(
    path: str | Path,
    *,
    expected_family_id: str | None = None,
    default_source: str | None = None,
) -> tuple[list[HpoAnnotationImportRow], list[HpoAnnotationImportIssue]]:
    return parse_hpo_tsv_text(
        Path(path).read_text(encoding="utf-8"),
        expected_family_id=expected_family_id,
        default_source=default_source,
    )


def _inline_term_to_row(
    *,
    family_id: str,
    individual_id: str,
    status: str,
    value: Any,
) -> tuple[HpoAnnotationImportRow | None, HpoAnnotationImportIssue | None]:
    if isinstance(value, str):
        hpo_id = normalize_hpo_id(value)
        label = None
        onset = evidence = note = None
    elif isinstance(value, Mapping):
        hpo_id = normalize_hpo_id(str(value.get("hpo_id") or value.get("id") or value.get("term") or ""))
        label = str(value.get("label") or "").strip() or None
        onset = str(value.get("onset") or "").strip() or None
        evidence = str(value.get("evidence") or "").strip() or None
        note = str(value.get("note") or "").strip() or None
    else:
        hpo_id = None
        label = onset = evidence = note = None
    if not hpo_id:
        return None, HpoAnnotationImportIssue(
            line_no=None,
            code="manifest_hpo_invalid",
            message=f"Inline HPO annotation for {individual_id} has an invalid term",
            sample_id=individual_id,
        )
    return HpoAnnotationImportRow(
        family_id=family_id,
        individual_id=individual_id,
        hpo_id=hpo_id,
        label=label,
        status=status,
        onset=onset,
        evidence=evidence,
        source="manifest_inline",
        note=note,
    ), None


def parse_manifest_inline_hpo(
    individuals: Any,
    *,
    family_id: str,
) -> tuple[list[HpoAnnotationImportRow], list[HpoAnnotationImportIssue]]:
    if individuals in (None, {}):
        return [], []
    if not isinstance(individuals, Mapping):
        return [], [
            HpoAnnotationImportIssue(
                line_no=None,
                code="manifest_individuals_invalid",
                message="Manifest individuals section must be an object keyed by individual ID",
            )
        ]
    rows: list[HpoAnnotationImportRow] = []
    issues: list[HpoAnnotationImportIssue] = []
    for individual_id_raw, individual_payload in individuals.items():
        individual_id = str(individual_id_raw).strip()
        if not individual_id or not isinstance(individual_payload, Mapping):
            continue
        hpo_payload = individual_payload.get("hpo")
        if hpo_payload is None:
            continue
        status_blocks: dict[str, Any]
        if isinstance(hpo_payload, list):
            status_blocks = {"present": hpo_payload}
        elif isinstance(hpo_payload, Mapping):
            status_blocks = {
                status: hpo_payload.get(status)
                for status in ("present", "absent", "unknown")
                if hpo_payload.get(status) is not None
            }
        else:
            issues.append(
                HpoAnnotationImportIssue(
                    line_no=None,
                    code="manifest_hpo_invalid",
                    message=f"Inline HPO block for {individual_id} must be a list or status object",
                    sample_id=individual_id,
                )
            )
            continue
        for status, values in status_blocks.items():
            term_values = values if isinstance(values, list) else [values]
            for value in term_values:
                row, issue = _inline_term_to_row(
                    family_id=family_id,
                    individual_id=individual_id,
                    status=status,
                    value=value,
                )
                if issue:
                    issues.append(issue)
                if row:
                    rows.append(row)
    return rows, issues


def _issue_dict(issue: HpoAnnotationImportIssue) -> dict[str, Any]:
    return {key: value for key, value in asdict(issue).items() if value is not None}


def _payload_has_field(payload: Any, field_name: str) -> bool:
    fields_set = getattr(payload, "model_fields_set", None)
    if isinstance(fields_set, set):
        return field_name in fields_set
    return hasattr(payload, field_name)


def _payload_value(payload: Any, field_name: str, default: Any = None) -> Any:
    if not _payload_has_field(payload, field_name):
        return default
    return getattr(payload, field_name, default)


async def _existing_hpo_terms(session: AsyncSession, hpo_ids: Iterable[str]) -> set[str]:
    ids = sorted({hpo_id for hpo_id in hpo_ids if hpo_id})
    if not ids:
        return set()
    result = await session.execute(
        text(
            """
            SELECT hpo_id
            FROM hpo_term
            WHERE hpo_id IN :hpo_ids
            """
        ).bindparams(bindparam("hpo_ids", expanding=True)),
        {"hpo_ids": ids},
    )
    return {str(row[0]) for row in result.all()}


async def _sample_uuid_for(
    session: AsyncSession,
    *,
    family_uuid: str,
    sample_id: str,
) -> str:
    result = await session.execute(
        text(
            """
            SELECT id::text
            FROM samples
            WHERE family_id = CAST(:family_uuid AS uuid)
              AND sample_id = :sample_id
            """
        ),
        {"family_uuid": family_uuid, "sample_id": sample_id},
    )
    sample_uuid = result.scalar_one_or_none()
    if sample_uuid is None:
        raise HTTPException(status_code=404, detail="Family member was not found")
    return str(sample_uuid)


async def _annotation_by_id(
    session: AsyncSession,
    *,
    family_uuid: str,
    annotation_id: str,
) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            SELECT
                ih.id::text AS id,
                s.sample_id AS sample_id,
                ih.hpo_id AS hpo_id,
                COALESCE(t.label, ih.hpo_id) AS label,
                ih.status AS status,
                ih.onset AS onset,
                ih.evidence AS evidence,
                ih.source AS source,
                ih.note AS note,
                ih.created_at AS created_at,
                ih.updated_at AS updated_at
            FROM individual_hpo ih
            JOIN samples s ON s.id = ih.sample_id
            LEFT JOIN hpo_term t ON t.hpo_id = ih.hpo_id
            WHERE ih.family_id = CAST(:family_uuid AS uuid)
              AND ih.id = CAST(:annotation_id AS uuid)
            """
        ),
        {"family_uuid": family_uuid, "annotation_id": annotation_id},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def list_family_hpo_annotations(
    session: AsyncSession,
    *,
    family_uuid: str,
    sample_id: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"family_uuid": family_uuid}
    sample_clause = ""
    if sample_id:
        sample_clause = "AND s.sample_id = :sample_id"
        params["sample_id"] = sample_id
    result = await session.execute(
        text(
            f"""
            SELECT
                ih.id::text AS id,
                s.sample_id AS sample_id,
                ih.hpo_id AS hpo_id,
                COALESCE(t.label, ih.hpo_id) AS label,
                ih.status AS status,
                ih.onset AS onset,
                ih.evidence AS evidence,
                ih.source AS source,
                ih.note AS note,
                ih.created_at AS created_at,
                ih.updated_at AS updated_at
            FROM individual_hpo ih
            JOIN samples s ON s.id = ih.sample_id
            LEFT JOIN hpo_term t ON t.hpo_id = ih.hpo_id
            WHERE ih.family_id = CAST(:family_uuid AS uuid)
              {sample_clause}
            ORDER BY s.sample_id, ih.status DESC, COALESCE(t.label, ih.hpo_id)
            """
        ),
        params,
    )
    return [dict(row) for row in result.mappings().all()]


async def search_hpo_terms(
    session: AsyncSession,
    *,
    query: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    cleaned = query.strip()
    if not cleaned:
        return []
    bounded_limit = max(1, min(limit, 50))
    like_query = f"%{cleaned.lower()}%"
    prefix_query = f"{cleaned.lower()}%"
    result = await session.execute(
        text(
            """
            SELECT
                t.hpo_id AS hpo_id,
                t.label AS label,
                t.definition AS definition,
                t.is_obsolete AS is_obsolete,
                CASE
                    WHEN lower(t.hpo_id) = lower(:query) THEN 0
                    WHEN lower(t.hpo_id) LIKE :prefix_query THEN 1
                    WHEN lower(t.label) LIKE :prefix_query THEN 2
                    WHEN EXISTS (
                        SELECT 1 FROM hpo_synonym s
                        WHERE s.hpo_id = t.hpo_id
                          AND lower(s.synonym) LIKE :prefix_query
                    ) THEN 3
                    ELSE 4
                END AS match_rank
            FROM hpo_term t
            WHERE t.is_obsolete = FALSE
              AND (
                lower(t.hpo_id) LIKE :like_query
                OR lower(t.label) LIKE :like_query
                OR EXISTS (
                    SELECT 1 FROM hpo_synonym s
                    WHERE s.hpo_id = t.hpo_id
                      AND lower(s.synonym) LIKE :like_query
                )
              )
            ORDER BY match_rank, t.label
            LIMIT :limit
            """
        ),
        {
            "query": cleaned,
            "like_query": like_query,
            "prefix_query": prefix_query,
            "limit": bounded_limit,
        },
    )
    return [dict(row) for row in result.mappings().all()]


async def get_hpo_term_details(
    session: AsyncSession,
    *,
    hpo_id: str,
) -> dict[str, Any]:
    normalized_id = normalize_hpo_id(hpo_id)
    if not normalized_id:
        raise HTTPException(status_code=400, detail="Invalid HPO identifier")
    term_result = await session.execute(
        text(
            """
            SELECT hpo_id, label, definition, is_obsolete, replaced_by,
                   release_version, release_date
            FROM hpo_term
            WHERE hpo_id = :hpo_id
            """
        ),
        {"hpo_id": normalized_id},
    )
    term = term_result.mappings().first()
    if term is None:
        raise HTTPException(status_code=404, detail="HPO term was not found")
    synonym_result = await session.execute(
        text(
            """
            SELECT synonym
            FROM hpo_synonym
            WHERE hpo_id = :hpo_id
            ORDER BY synonym
            """
        ),
        {"hpo_id": normalized_id},
    )
    parent_result = await session.execute(
        text(
            """
            SELECT e.parent_id AS hpo_id, t.label AS label, e.relation AS relation
            FROM hpo_edge e
            JOIN hpo_term t ON t.hpo_id = e.parent_id
            WHERE e.child_id = :hpo_id
            ORDER BY t.label
            """
        ),
        {"hpo_id": normalized_id},
    )
    child_result = await session.execute(
        text(
            """
            SELECT e.child_id AS hpo_id, t.label AS label, e.relation AS relation
            FROM hpo_edge e
            JOIN hpo_term t ON t.hpo_id = e.child_id
            WHERE e.parent_id = :hpo_id
            ORDER BY t.label
            """
        ),
        {"hpo_id": normalized_id},
    )
    return {
        **dict(term),
        "synonyms": [str(row[0]) for row in synonym_result.all()],
        "parents": [dict(row) for row in parent_result.mappings().all()],
        "children": [dict(row) for row in child_result.mappings().all()],
    }


async def create_individual_hpo_annotation(
    session: AsyncSession,
    *,
    family_uuid: str,
    sample_id: str,
    payload: Any,
    commit: bool = True,
) -> dict[str, Any]:
    sample_uuid = await _sample_uuid_for(session, family_uuid=family_uuid, sample_id=sample_id)
    hpo_id = normalize_hpo_id(str(getattr(payload, "hpo_id", None) or ""))
    if not hpo_id:
        raise HTTPException(status_code=400, detail="Invalid HPO identifier")
    if hpo_id not in await _existing_hpo_terms(session, [hpo_id]):
        raise HTTPException(status_code=404, detail="HPO term was not found")
    status = normalize_annotation_status(getattr(payload, "status", None)) or "present"
    result = await session.execute(
        text(
            """
            INSERT INTO individual_hpo (
                family_id, sample_id, hpo_id, status, onset, evidence, source, note, updated_at
            )
            VALUES (
                CAST(:family_uuid AS uuid), CAST(:sample_uuid AS uuid), :hpo_id, :status,
                :onset, :evidence, :source, :note, timezone('utc', now())
            )
            ON CONFLICT (family_id, sample_id, hpo_id, status) DO UPDATE SET
                onset = EXCLUDED.onset,
                evidence = EXCLUDED.evidence,
                source = EXCLUDED.source,
                note = EXCLUDED.note,
                updated_at = timezone('utc', now())
            RETURNING id::text
            """
        ),
        {
            "family_uuid": family_uuid,
            "sample_uuid": sample_uuid,
            "hpo_id": hpo_id,
            "status": status,
            "onset": getattr(payload, "onset", None),
            "evidence": getattr(payload, "evidence", None),
            "source": getattr(payload, "source", None) or "manual",
            "note": getattr(payload, "note", None),
        },
    )
    annotation_id = str(result.scalar_one())
    if commit:
        await session.commit()
    annotation = await _annotation_by_id(session, family_uuid=family_uuid, annotation_id=annotation_id)
    assert annotation is not None
    return annotation


async def update_individual_hpo_annotation(
    session: AsyncSession,
    *,
    family_uuid: str,
    annotation_id: str,
    payload: Any,
    commit: bool = True,
) -> dict[str, Any]:
    existing = await _annotation_by_id(session, family_uuid=family_uuid, annotation_id=annotation_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="HPO annotation was not found")
    status_value = _payload_value(payload, "status")
    status = normalize_annotation_status(status_value) if status_value is not None else existing["status"]
    if not status:
        raise HTTPException(status_code=400, detail="Annotation status must be present, absent, or unknown")
    hpo_id_value = _payload_value(payload, "hpo_id")
    hpo_id = normalize_hpo_id(str(hpo_id_value)) if hpo_id_value is not None else existing["hpo_id"]
    if not hpo_id:
        raise HTTPException(status_code=400, detail="Invalid HPO identifier")
    if hpo_id != existing["hpo_id"] and hpo_id not in await _existing_hpo_terms(session, [hpo_id]):
        raise HTTPException(status_code=404, detail="HPO term was not found")

    await session.execute(
        text(
            """
            UPDATE individual_hpo
            SET hpo_id = :hpo_id,
                status = :status,
                onset = :onset,
                evidence = :evidence,
                source = :source,
                note = :note,
                updated_at = timezone('utc', now())
            WHERE family_id = CAST(:family_uuid AS uuid)
              AND id = CAST(:annotation_id AS uuid)
            """
        ),
        {
            "family_uuid": family_uuid,
            "annotation_id": annotation_id,
            "hpo_id": hpo_id,
            "status": status,
            "onset": _payload_value(payload, "onset", existing["onset"]),
            "evidence": _payload_value(payload, "evidence", existing["evidence"]),
            "source": _payload_value(payload, "source", existing["source"]) or "manual",
            "note": _payload_value(payload, "note", existing["note"]),
        },
    )
    if commit:
        await session.commit()
    updated = await _annotation_by_id(session, family_uuid=family_uuid, annotation_id=annotation_id)
    assert updated is not None
    return updated


async def delete_individual_hpo_annotation(
    session: AsyncSession,
    *,
    family_uuid: str,
    annotation_id: str,
    commit: bool = True,
) -> None:
    result = await session.execute(
        text(
            """
            DELETE FROM individual_hpo
            WHERE family_id = CAST(:family_uuid AS uuid)
              AND id = CAST(:annotation_id AS uuid)
            """
        ),
        {"family_uuid": family_uuid, "annotation_id": annotation_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="HPO annotation was not found")
    if commit:
        await session.commit()


async def query_family_hpo_annotations(
    session: AsyncSession,
    *,
    family_uuid: str,
    hpo_id: str,
    include_descendants: bool = True,
) -> dict[str, Any]:
    normalized_id = normalize_hpo_id(hpo_id)
    if not normalized_id:
        raise HTTPException(status_code=400, detail="Invalid HPO identifier")
    if normalized_id not in await _existing_hpo_terms(session, [normalized_id]):
        raise HTTPException(status_code=404, detail="HPO term was not found")
    if include_descendants:
        term_clause = """
        ih.hpo_id IN (
            SELECT hpo_id
            FROM hpo_closure
            WHERE ancestor_id = :hpo_id
        )
        """
    else:
        term_clause = "ih.hpo_id = :hpo_id"
    result = await session.execute(
        text(
            f"""
            SELECT
                ih.id::text AS id,
                s.sample_id AS sample_id,
                ih.hpo_id AS hpo_id,
                COALESCE(t.label, ih.hpo_id) AS label,
                ih.status AS status,
                ih.onset AS onset,
                ih.evidence AS evidence,
                ih.source AS source,
                ih.note AS note,
                ih.created_at AS created_at,
                ih.updated_at AS updated_at
            FROM individual_hpo ih
            JOIN samples s ON s.id = ih.sample_id
            LEFT JOIN hpo_term t ON t.hpo_id = ih.hpo_id
            WHERE ih.family_id = CAST(:family_uuid AS uuid)
              AND ih.status = 'present'
              AND {term_clause}
            ORDER BY s.sample_id, COALESCE(t.label, ih.hpo_id)
            """
        ),
        {"family_uuid": family_uuid, "hpo_id": normalized_id},
    )
    annotations = [dict(row) for row in result.mappings().all()]
    return {
        "hpo_id": normalized_id,
        "include_descendants": include_descendants,
        "sample_ids": sorted({str(row["sample_id"]) for row in annotations}),
        "annotations": annotations,
    }


async def import_family_hpo_annotations(
    session: AsyncSession,
    *,
    family_uuid: str,
    family_id: str,
    sample_uuids_by_id: Mapping[str, str],
    rows: Iterable[HpoAnnotationImportRow],
    issues: Iterable[HpoAnnotationImportIssue] = (),
    commit: bool = True,
) -> dict[str, Any]:
    row_list = list(rows)
    issue_list = list(issues)
    existing_terms = await _existing_hpo_terms(session, [row.hpo_id for row in row_list])
    imported = 0
    skipped = 0
    imported_by_sample: dict[str, int] = {}
    for row in row_list:
        if row.family_id and row.family_id != family_id:
            skipped += 1
            issue_list.append(
                HpoAnnotationImportIssue(
                    line_no=row.line_no,
                    code="phenotype_family_mismatch",
                    message=f"Phenotype row family_id '{row.family_id}' does not match family '{family_id}'",
                    sample_id=row.individual_id,
                    hpo_id=row.hpo_id,
                )
            )
            continue
        sample_uuid = sample_uuids_by_id.get(row.individual_id)
        if sample_uuid is None:
            skipped += 1
            issue_list.append(
                HpoAnnotationImportIssue(
                    line_no=row.line_no,
                    code="phenotype_sample_unknown",
                    message=f"Phenotype row references unknown individual '{row.individual_id}'",
                    sample_id=row.individual_id,
                    hpo_id=row.hpo_id,
                )
            )
            continue
        if row.hpo_id not in existing_terms:
            skipped += 1
            issue_list.append(
                HpoAnnotationImportIssue(
                    line_no=row.line_no,
                    code="phenotype_hpo_unknown",
                    message=f"HPO term '{row.hpo_id}' is not loaded in the HPO ontology table",
                    sample_id=row.individual_id,
                    hpo_id=row.hpo_id,
                )
            )
            continue
        await session.execute(
            text(
                """
                INSERT INTO individual_hpo (
                    family_id, sample_id, hpo_id, status, onset, evidence, source, note, updated_at
                )
                VALUES (
                    CAST(:family_uuid AS uuid), CAST(:sample_uuid AS uuid), :hpo_id, :status,
                    :onset, :evidence, :source, :note, timezone('utc', now())
                )
                ON CONFLICT (family_id, sample_id, hpo_id, status) DO UPDATE SET
                    onset = EXCLUDED.onset,
                    evidence = EXCLUDED.evidence,
                    source = EXCLUDED.source,
                    note = EXCLUDED.note,
                    updated_at = timezone('utc', now())
                """
            ),
            {
                "family_uuid": family_uuid,
                "sample_uuid": sample_uuid,
                "hpo_id": row.hpo_id,
                "status": row.status,
                "onset": row.onset,
                "evidence": row.evidence,
                "source": row.source or "family_package",
                "note": row.note,
            },
        )
        imported += 1
        imported_by_sample[row.individual_id] = imported_by_sample.get(row.individual_id, 0) + 1
    if commit:
        await session.commit()
    return {
        "imported": imported,
        "skipped": skipped,
        "samples": imported_by_sample,
        "errors": [_issue_dict(issue) for issue in issue_list],
    }

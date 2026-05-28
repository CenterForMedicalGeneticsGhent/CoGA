from __future__ import annotations

from backend.app.services.panelapp_service import (
    extract_panelapp_import_content,
    panelapp_summary,
)


def _panelapp_payload() -> dict:
    return {
        "id": 20,
        "name": "Hereditary ataxia",
        "disease_group": "Neurology",
        "disease_sub_group": "Motor Disorders",
        "status": "public",
        "version": "1.345",
        "version_created": "2026-05-01T14:28:12.522359Z",
        "relevant_disorders": ["R54"],
        "stats": {"number_of_genes": 2, "number_of_strs": 1, "number_of_regions": 1},
        "types": [{"name": "Rare Disease 100K"}],
        "genes": [
            {
                "gene_data": {
                    "hgnc_symbol": "AAAS",
                    "ensembl_genes": {
                        "GRch38": {"90": {"location": "12:53307456-53324864"}}
                    },
                },
                "entity_name": "AAAS",
                "confidence_level": "3",
            },
            {
                "gene_data": {
                    "hgnc_symbol": "AMBER",
                    "ensembl_genes": {
                        "GRch38": {"90": {"location": "1:100-200"}}
                    },
                },
                "entity_name": "AMBER",
                "confidence_level": "2",
            },
        ],
        "strs": [
            {
                "gene_data": {"hgnc_symbol": "ATN1"},
                "entity_name": "ATN1_CAG",
                "confidence_level": "3",
                "chromosome": "12",
                "grch38_coordinates": [6936717, 6936772],
            }
        ],
        "regions": [
            {
                "entity_name": "ISCA-37478-Gain",
                "confidence_level": "3",
                "chromosome": "15",
                "grch38_coordinates": [23465365, 28134728],
            }
        ],
    }


def test_panelapp_summary_maps_public_panel_fields() -> None:
    summary = panelapp_summary(_panelapp_payload())

    assert summary.panelapp_id == 20
    assert summary.name == "Hereditary ataxia"
    assert summary.version == "1.345"
    assert summary.gene_count == 2
    assert summary.str_count == 1
    assert summary.region_count == 1
    assert summary.types == ["Rare Disease 100K"]
    assert summary.url == "https://panelapp.genomicsengland.co.uk/panels/20/"


def test_extract_panelapp_import_content_keeps_green_genes_regions_and_strs() -> None:
    content = extract_panelapp_import_content(
        _panelapp_payload(),
        confidence_levels=["3"],
        include_regions=True,
        include_strs=True,
        assembly="GRCh38",
    )

    assert content.genes == ["AAAS", "ATN1"]
    assert [(region.gene, region.chr, region.start, region.end) for region in content.regions] == [
        ("AAAS", "12", 53307456, 53324864),
        ("ATN1", "12", 6936717, 6936772),
        ("ISCA-37478-Gain", "15", 23465365, 28134728),
    ]
    assert content.metadata["import_options"]["confidence_levels"] == ["3"]
    assert content.metadata["selected_counts"] == {"genes": 1, "regions": 1, "strs": 1}


def test_extract_panelapp_import_content_can_include_amber_entities() -> None:
    content = extract_panelapp_import_content(
        _panelapp_payload(),
        confidence_levels=["2", "3"],
        include_regions=False,
        include_strs=False,
        assembly="GRCh38",
    )

    assert content.genes == ["AAAS", "AMBER"]
    assert [(region.gene, region.chr) for region in content.regions] == [
        ("AAAS", "12"),
        ("AMBER", "1"),
    ]

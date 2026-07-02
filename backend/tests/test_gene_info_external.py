"""Outbound gene-lookup URL encoding (#336).

urllib's quote() defaults to safe='/', so a '/' or '../' in a gene symbol / id would
pass through unescaped and forge the request PATH on the (fixed) external hosts
(genenames / ensembl / clinicalgenome). These tests prove quote(..., safe='') now
confines every interpolated identifier to a single path segment, while leaving
legitimate identifiers byte-identical.
"""
from __future__ import annotations

import pytest

import backend.app.services.gene_info_external as gene_info_external


class _FakeResponse:
    text = "<html></html>"

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        # Shapes tolerated by the callers under test.
        return {"response": {"docs": []}, "data": [], "homologies": []}


@pytest.fixture
def captured_urls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    urls: list[str] = []

    async def fake_request(method: str, url: str, **kwargs):
        urls.append(url)
        return _FakeResponse()

    monkeypatch.setattr(gene_info_external, "resilient_request", fake_request)
    return urls


@pytest.mark.asyncio
async def test_hgnc_url_escapes_slash_in_symbol(captured_urls: list[str]) -> None:
    await gene_info_external.fetch_hgnc_gene("BRCA1/../admin")
    url = captured_urls[-1]
    assert url == "https://rest.genenames.org/fetch/symbol/BRCA1%2F..%2Fadmin"
    assert "/" not in url.split("/symbol/", 1)[1]  # confined to one segment


@pytest.mark.asyncio
async def test_ensembl_homology_url_escapes_slash(captured_urls: list[str]) -> None:
    await gene_info_external.fetch_ensembl_homologies("ENSG/../x")
    assert "/" not in captured_urls[-1].split("/homology/id/human/", 1)[1]


@pytest.mark.asyncio
async def test_ensembl_lookup_keeps_two_path_segments(captured_urls: list[str]) -> None:
    await gene_info_external.fetch_ensembl_gene("TP53/../y", "Homo sapiens")
    tail = captured_urls[-1].split("/lookup/symbol/", 1)[1]
    assert len(tail.split("/")) == 2  # species / symbol — injected '/' added no segment


@pytest.mark.asyncio
async def test_clingen_url_escapes_slash_in_identifier(captured_urls: list[str]) -> None:
    await gene_info_external.fetch_clingen_gene("SYM/../x", None)
    assert "/" not in captured_urls[-1].split("/kb/genes/", 1)[1]


@pytest.mark.asyncio
async def test_hgnc_url_unchanged_for_legit_symbol(captured_urls: list[str]) -> None:
    await gene_info_external.fetch_hgnc_gene("IGH@")
    assert captured_urls[-1].endswith("/symbol/IGH%40")  # '@' still encoded, no regression

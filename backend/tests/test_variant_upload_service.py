from io import BytesIO

from fastapi import UploadFile
import pytest

from backend.app.services.clickhouse_variant_storage import build_small_variant_id
from backend.app.services.family_metadata_context import FamilyMetadataContext, SampleMetadataContext
from backend.app.services import variant_upload_service
from backend.app.services.variant_upload_service import (
    _detect_small_variant_format,
    _detect_small_variant_format_from_upload,
    _haplotype_state_end,
    _haplotype_state_matches_block,
    _new_haplotype_state,
    _parse_vep_tsv_annotations,
    _phased_haplotype_alleles,
)


def test_haplotype_state_end_uses_next_variant_on_same_chromosome() -> None:
    state = {
        "start": 100,
        "last_pos": 200,
        "chr": "1",
    }

    assert _haplotype_state_end(
        state,
        next_chrom="1",
        next_start=500,
        chromosome_sizes={"1": 1_000},
    ) == 500


def test_haplotype_state_end_uses_previous_chromosome_size_on_chromosome_change() -> None:
    state = {
        "start": 800,
        "last_pos": 950,
        "chr": "1",
    }

    assert _haplotype_state_end(
        state,
        next_chrom="2",
        next_start=10,
        chromosome_sizes={"1": 1_000, "2": 2_000},
    ) == 1_000


def test_haplotype_state_end_falls_back_to_last_variant_without_chromosome_size() -> None:
    state = {
        "start": 800,
        "last_pos": 950,
        "chr": "1",
    }

    assert _haplotype_state_end(
        state,
        next_chrom=None,
        next_start=None,
        chromosome_sizes={},
    ) == 951


def test_haplotype_blocks_follow_phase_set_not_individual_genotype_state() -> None:
    state = _new_haplotype_state(chrom="1", start=100, hap1="0", hap2="1", ps=42)

    assert _phased_haplotype_alleles("1|0") == ("1", "0")
    assert _haplotype_state_matches_block(state, chrom="1", ps=42) is True
    assert _haplotype_state_matches_block(state, chrom="1", ps=43) is False


def test_haplotype_blocks_without_phase_set_stay_chromosome_contiguous() -> None:
    state = _new_haplotype_state(chrom="1", start=100, hap1="0", hap2="1", ps=None)

    assert _haplotype_state_matches_block(state, chrom="1", ps=None) is True
    assert _haplotype_state_matches_block(state, chrom="2", ps=None) is False
    assert _phased_haplotype_alleles("0/1") is None


def test_gt_only_shapeit_vcf_is_detected_as_glimpse2() -> None:
    vcf_text = (
        "##fileformat=VCFv4.2\n"
        "##source=SHAPEIT5 phase_common 1.1\n"
        "##FORMAT=<ID=GT,Number=1,Type=String,Description=\"Phased genotype\">\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\tS2\n"
        "1\t100\t.\tA\tG\t.\tPASS\t.\tGT\t0|1\t0|0\n"
    )

    assert _detect_small_variant_format(vcf_text, "auto") == "glimpse2"

    upload = UploadFile(file=BytesIO(vcf_text.encode()), filename="co619_phased_final.vcf")
    assert _detect_small_variant_format_from_upload(upload, "auto") == "glimpse2"


def test_gt_only_clair3_vcf_is_not_detected_as_glimpse2() -> None:
    vcf_text = (
        "##fileformat=VCFv4.2\n"
        "##source=clair3\n"
        "##FORMAT=<ID=GT,Number=1,Type=String,Description=\"Genotype\">\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
        "1\t100\t.\tA\tG\t.\tPASS\t.\tGT\t0/1\n"
    )

    assert _detect_small_variant_format(vcf_text, "auto") == "clair3"


def test_segregation_haplotype_switch_requires_repeated_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(variant_upload_service, "SEGREGATION_HAPLOTYPE_SWITCH_MIN_MARKERS", 2)
    monkeypatch.setattr(variant_upload_service, "SEGREGATION_HAPLOTYPE_SWITCH_MIN_SPAN", 10)

    state = variant_upload_service._empty_segregation_side_state()
    assert (
        variant_upload_service._observe_segregation_haplotype(
            state,
            chrom="1",
            start=100,
            hap="0",
        )
        == (100, "0")
    )
    assert (
        variant_upload_service._observe_segregation_haplotype(
            state,
            chrom="1",
            start=120,
            hap="1",
        )
        is None
    )
    assert (
        variant_upload_service._observe_segregation_haplotype(
            state,
            chrom="1",
            start=130,
            hap="0",
        )
        is None
    )
    assert (
        variant_upload_service._observe_segregation_haplotype(
            state,
            chrom="1",
            start=200,
            hap="1",
        )
        is None
    )
    assert (
        variant_upload_service._observe_segregation_haplotype(
            state,
            chrom="1",
            start=215,
            hap="1",
        )
        == (200, "1")
    )


@pytest.mark.asyncio
async def test_glimpse2_upload_stores_haplotype_blocks_separate_from_snv_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inserted_variant_batches = []
    inserted_haplotype_rows = []
    upserted_sources = []

    async def fake_count_family_small_variants(*_args, **_kwargs):
        return 0

    async def fake_get_track_presence_by_sample(*_args, **_kwargs):
        return set()

    async def fake_insert_small_variant_records(*_args, **kwargs):
        inserted_variant_batches.append(list(_args[3]))
        assert kwargs["annotation_version"] == "vcf_info"

    async def fake_refresh_family_small_variant_summaries(*_args, **_kwargs):
        return None

    async def fake_insert_interval_track_rows(_assembly_name, rows):
        inserted_haplotype_rows.extend(rows)

    async def fake_upsert_interval_track_source(*_args, **kwargs):
        upserted_sources.append(kwargs)

    async def fake_fetch_chromosome_sizes(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(
        variant_upload_service,
        "count_family_small_variants",
        fake_count_family_small_variants,
    )
    monkeypatch.setattr(
        variant_upload_service,
        "get_track_presence_by_sample",
        fake_get_track_presence_by_sample,
    )
    monkeypatch.setattr(
        variant_upload_service,
        "insert_small_variant_records",
        fake_insert_small_variant_records,
    )
    monkeypatch.setattr(
        variant_upload_service,
        "refresh_family_small_variant_summaries",
        fake_refresh_family_small_variant_summaries,
    )
    monkeypatch.setattr(
        variant_upload_service,
        "insert_interval_track_rows",
        fake_insert_interval_track_rows,
    )
    monkeypatch.setattr(
        variant_upload_service,
        "upsert_interval_track_source",
        fake_upsert_interval_track_source,
    )
    monkeypatch.setattr(
        variant_upload_service,
        "_fetch_chromosome_sizes",
        fake_fetch_chromosome_sizes,
    )

    class FakeSession:
        commits = 0

        async def commit(self) -> None:
            self.commits += 1

    context = FamilyMetadataContext(
        family_uuid="family-uuid",
        family_id="FAM001",
        project_ids=["project-uuid"],
        sample_rows=[],
        sample_uuid_to_name={"sample-uuid": "S1"},
        sample_name_to_uuid={"S1": "sample-uuid"},
        affected_sample_names=[],
        assembly_id="assembly-uuid",
        assembly_name="GRCh38",
    )
    sample_contexts = {
        "S1": SampleMetadataContext(
            sample_uuid="sample-uuid",
            sample_id="S1",
            family_uuid="family-uuid",
            family_id="FAM001",
            sex="und",
            project_ids=["project-uuid"],
            assembly_id="assembly-uuid",
            assembly_name="GRCh38",
        )
    }
    vcf_text = (
        "##fileformat=VCFv4.2\n"
        "##FORMAT=<ID=GT,Number=1,Type=String,Description=\"Phased genotype\">\n"
        "##FORMAT=<ID=GP,Number=G,Type=Float,Description=\"Genotype probabilities\">\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
        "1\t100\t.\tA\tG\t.\tPASS\t.\tGT:GP\t0|1:0.01,0.98,0.01\n"
        "1\t200\t.\tC\tT\t.\tPASS\t.\tGT:GP\t1|0:0.01,0.98,0.01\n"
        "1\t300\t.\tG\tA\t.\tPASS\t.\tGT:GP\t0|0:0.98,0.01,0.01\n"
    )
    upload = UploadFile(file=BytesIO(vcf_text.encode()), filename="glimpse2.vcf")

    result = await variant_upload_service.upload_family_small_variant_file(
        FakeSession(),  # type: ignore[arg-type]
        context=context,
        sample_contexts=sample_contexts,
        file=upload,
        overwrite=False,
        format_hint="auto",
    )

    assert result["source_format"] == "glimpse2"
    assert result["inserted"] == 3
    assert result["haplotypes_inserted"] == 1
    assert len(inserted_variant_batches[0]) == 3
    assert inserted_haplotype_rows == [
        {
            "sample_id": "sample-uuid",
            "family_id": "family-uuid",
            "assembly_id": "assembly-uuid",
            "track_type": "haplotype",
            "source": "glimpse2",
            "chr": "1",
            "start": 100,
            "end": 301,
            "hap1": "0",
            "hap2": "1",
            "ps": None,
            "metadata_json": inserted_haplotype_rows[0]["metadata_json"],
        }
    ]
    assert upserted_sources[0]["track_type"] == "haplotype"
    assert upserted_sources[0]["row_count"] == 1


@pytest.mark.asyncio
async def test_glimpse2_upload_derives_child_haplotype_blocks_from_parental_segregation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inserted_haplotype_rows = []
    monkeypatch.setattr(variant_upload_service, "SEGREGATION_HAPLOTYPE_SWITCH_MIN_MARKERS", 1)
    monkeypatch.setattr(variant_upload_service, "SEGREGATION_HAPLOTYPE_SWITCH_MIN_SPAN", 0)

    async def fake_count_family_small_variants(*_args, **_kwargs):
        return 0

    async def fake_get_track_presence_by_sample(*_args, **_kwargs):
        return set()

    async def fake_insert_small_variant_records(*_args, **_kwargs):
        return None

    async def fake_refresh_family_small_variant_summaries(*_args, **_kwargs):
        return None

    async def fake_insert_interval_track_rows(_assembly_name, rows):
        inserted_haplotype_rows.extend(rows)

    async def fake_upsert_interval_track_source(*_args, **_kwargs):
        return None

    async def fake_fetch_chromosome_sizes(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(
        variant_upload_service,
        "count_family_small_variants",
        fake_count_family_small_variants,
    )
    monkeypatch.setattr(
        variant_upload_service,
        "get_track_presence_by_sample",
        fake_get_track_presence_by_sample,
    )
    monkeypatch.setattr(
        variant_upload_service,
        "insert_small_variant_records",
        fake_insert_small_variant_records,
    )
    monkeypatch.setattr(
        variant_upload_service,
        "refresh_family_small_variant_summaries",
        fake_refresh_family_small_variant_summaries,
    )
    monkeypatch.setattr(
        variant_upload_service,
        "insert_interval_track_rows",
        fake_insert_interval_track_rows,
    )
    monkeypatch.setattr(
        variant_upload_service,
        "upsert_interval_track_source",
        fake_upsert_interval_track_source,
    )
    monkeypatch.setattr(
        variant_upload_service,
        "_fetch_chromosome_sizes",
        fake_fetch_chromosome_sizes,
    )

    class FakeSession:
        async def commit(self) -> None:
            return None

    members = [
        ("father-uuid", "FATHER", "father", False, "male"),
        ("mother-uuid", "MOTHER", "mother", False, "female"),
        ("affected-uuid", "AFFECTED", "proband", True, "female"),
        ("embryo-uuid", "EMBRYO1", "embryo", False, "und"),
    ]
    context = FamilyMetadataContext(
        family_uuid="family-uuid",
        family_id="FAM001",
        project_ids=["project-uuid"],
        sample_rows=[
            {
                "sample_uuid": sample_uuid,
                "sample_id": sample_id,
                "role": role,
                "affected": affected,
                "sex": sex,
            }
            for sample_uuid, sample_id, role, affected, sex in members
        ],
        sample_uuid_to_name={sample_uuid: sample_id for sample_uuid, sample_id, *_ in members},
        sample_name_to_uuid={sample_id: sample_uuid for sample_uuid, sample_id, *_ in members},
        affected_sample_names=["AFFECTED"],
        assembly_id="assembly-uuid",
        assembly_name="GRCh38",
    )
    sample_contexts = {
        sample_id: SampleMetadataContext(
            sample_uuid=sample_uuid,
            sample_id=sample_id,
            family_uuid="family-uuid",
            family_id="FAM001",
            sex=sex,
            project_ids=["project-uuid"],
            assembly_id="assembly-uuid",
            assembly_name="GRCh38",
        )
        for sample_uuid, sample_id, _role, _affected, sex in members
    }
    vcf_text = (
        "##fileformat=VCFv4.2\n"
        "##FORMAT=<ID=GT,Number=1,Type=String,Description=\"Phased genotype\">\n"
        "##FORMAT=<ID=GP,Number=G,Type=Float,Description=\"Genotype probabilities\">\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tFATHER\tMOTHER\tAFFECTED\tEMBRYO1\n"
        "1\t100\t.\tA\tG\t.\tPASS\t.\tGT:GP\t0|1:.\t0|0:.\t0|1:.\t0|1:.\n"
        "1\t150\t.\tC\tT\t.\tPASS\t.\tGT:GP\t0|0:.\t0|1:.\t0|1:.\t0|1:.\n"
        "1\t200\t.\tG\tA\t.\tPASS\t.\tGT:GP\t0|1:.\t0|0:.\t0|1:.\t0|0:.\n"
        "1\t250\t.\tT\tC\t.\tPASS\t.\tGT:GP\t0|0:.\t0|1:.\t0|1:.\t0|0:.\n"
    )
    upload = UploadFile(file=BytesIO(vcf_text.encode()), filename="glimpse2.vcf")

    result = await variant_upload_service.upload_family_small_variant_file(
        FakeSession(),  # type: ignore[arg-type]
        context=context,
        sample_contexts=sample_contexts,
        file=upload,
        overwrite=False,
        format_hint="auto",
    )

    assert result["haplotypes_inserted"] >= 6
    rows_by_uuid: dict[str, list[dict[str, object]]] = {}
    for row in inserted_haplotype_rows:
        rows_by_uuid.setdefault(str(row["sample_id"]), []).append(row)

    embryo_rows = rows_by_uuid["embryo-uuid"]
    assert [(row["start"], row["end"], row["hap1"], row["hap2"]) for row in embryo_rows] == [
        (100, 150, "1", "?"),
        (150, 200, "1", "1"),
        (200, 250, "0", "1"),
        (250, 251, "0", "0"),
    ]
    affected_rows = rows_by_uuid["affected-uuid"]
    assert affected_rows[-1]["hap1"] == "1"
    assert affected_rows[-1]["hap2"] == "1"
    assert rows_by_uuid["father-uuid"][0]["hap1"] == "0"
    assert rows_by_uuid["father-uuid"][0]["hap2"] == "1"
    assert rows_by_uuid["mother-uuid"][0]["hap1"] == "0"
    assert rows_by_uuid["mother-uuid"][0]["hap2"] == "1"


def test_parse_vep_tsv_annotations_indexes_by_variant_id_and_locus_allele() -> None:
    lookup = _parse_vep_tsv_annotations(
        "#Uploaded_variation\tLocation\tAllele\tGene\tFeature\tFeature_type\tConsequence\tIMPACT\tSYMBOL\tCANONICAL\n"
        "chr1_101_A/G\tchr1:101\tG\tENSG1\tENST1\tTranscript\tmissense_variant\tMODERATE\tGENE1\tYES\n"
    )

    variant_id = build_small_variant_id("1", 101, "A", "G")
    assert lookup.row_count == 1
    assert lookup.by_variant_id[variant_id][0]["gene"] == "GENE1"
    assert lookup.by_locus_allele[("1", 101, "G")][0]["effect"] == "missense_variant"

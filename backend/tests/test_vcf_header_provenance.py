"""Unit tests for VCF/TRGT header provenance extraction.

Realistic header fragments from the tools CoGA ingests (DeepVariant/GATK +
VEP/snpEff/bcftools for SNV, Sniffles/Spectre for SV, TRGT for repeats). The
parser is best-effort: it must extract what it can and never raise.
"""

from __future__ import annotations

from app.services.vcf_header_provenance import (
    extract_header_provenance,
    merge_module_maps,
    provenance_to_modules,
)

SNV_VEP_HEADER = """\
##fileformat=VCFv4.2
##fileDate=20240115
##source=DeepVariant
##DeepVariant_version=1.6.0
##reference=/data/ref/GRCh38.fa
##VEP="v110" time="2024-01-15 10:00:00" cache="/data/vep/homo_sapiens/110_GRCh38" ensembl-version=110 gnomADe="r2.1.1" gnomADg="v3.1.2" ClinVar="202301" dbNSFP="4.3a" SpliceAI="1.3" dbSNP="154" assembly="GRCh38.p14" sift="sift5.2.2" polyphen="2.2.2"
##INFO=<ID=CSQ,Number=.,Type=String,Description="Consequence annotations from Ensembl VEP">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tPROBAND
"""

SNV_GATK_SNPEFF_HEADER = """\
##fileformat=VCFv4.2
##GATKCommandLine=<ID=HaplotypeCaller,CommandLine="HaplotypeCaller --input x.bam",Version="4.4.0.0",Date="2024-01-15">
##SnpEffVersion="5.1d (build 2022-04-19 15:05), by Pablo Cingolani"
##SnpEffCmd="SnpEff  GRCh38.105 input.vcf"
##bcftools_normVersion=1.17+htslib-1.17
##bcftools_normCommand=norm -f ref.fa; Date=2024-01-15
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
"""

SV_SNIFFLES_HEADER = """\
##fileformat=VCFv4.2
##source=Sniffles2_2.2
##command="sniffles --input proband.bam --vcf out.vcf"
##fileDate=2024-02-01
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tPROBAND
"""

SV_SPECTRE_HEADER = """\
##fileformat=VCFv4.2
##source=Spectre
##spectreVersion=0.2.1
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
"""

TRGT_HEADER = """\
##fileformat=VCFv4.2
##fileDate=2024-03-01
##trgtVersion=0.7.0
##trgtCommand=trgt genotype --genome ref.fa --repeats catalog.bed
##reference=GRCh38.fa
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tPROBAND
"""


def _modules(text: str, modality: str | None = None) -> dict:
    return extract_header_provenance(text.splitlines(), modality=modality).as_modules()


def test_snv_vep_extracts_caller_engine_and_db_versions():
    prov = extract_header_provenance(SNV_VEP_HEADER.splitlines(), modality="snv")
    mods = prov.as_modules()
    assert prov.fileformat == "VCFv4.2"
    assert prov.file_date == "20240115"
    assert prov.reference == "GRCh38.fa"
    assert mods["deepvariant"]["version"] == "1.6.0"
    assert mods["vep"]["version"] == "110"
    assert "110_GRCh38" in mods["vep"]["detail"]  # cache path
    # Database releases embedded in the VEP header.
    assert mods["gnomad"]["version"] == "r2.1.1"
    assert mods["clinvar"]["version"] == "202301"
    assert mods["dbnsfp"]["version"] == "4.3a"
    assert mods["spliceai"]["version"] == "1.3"
    assert mods["dbsnp"]["version"] == "154"
    assert mods["sift"]["version"] == "sift5.2.2"


def test_snv_vep_caller_tagged_with_modality():
    prov = extract_header_provenance(SNV_VEP_HEADER.splitlines(), modality="snv")
    assert prov.caller is not None and prov.caller["name"] == "deepvariant"
    assert prov.modules["deepvariant"]["detail"] == "snv caller"


def test_gatk_snpeff_bcftools():
    mods = _modules(SNV_GATK_SNPEFF_HEADER)
    assert mods["gatk"]["version"] == "4.4.0.0"
    assert mods["snpeff"]["version"] == "5.1d"
    assert mods["snpeff"]["detail"] == "GRCh38.105"  # genome db from SnpEffCmd
    assert mods["bcftools"]["version"] == "1.17+htslib-1.17"


def test_sv_sniffles_name_version_split():
    prov = extract_header_provenance(SV_SNIFFLES_HEADER.splitlines(), modality="sv")
    mods = prov.as_modules()
    assert mods["sniffles"]["version"] == "2.2"
    assert prov.caller["name"] == "sniffles"


def test_sv_spectre():
    mods = _modules(SV_SPECTRE_HEADER, modality="sv")
    assert "spectre" in mods
    assert mods["spectre"]["version"] == "0.2.1"


def test_trgt_repeats():
    prov = extract_header_provenance(TRGT_HEADER.splitlines(), modality="repeats")
    mods = prov.as_modules()
    assert mods["trgt"]["version"] == "0.7.0"
    assert prov.reference == "GRCh38.fa"


def test_stops_at_column_header_and_ignores_data():
    # A data line with a '##'-looking value must not be parsed as header.
    text = SV_SPECTRE_HEADER + "chr1\t100\t.\tA\t<DEL>\t.\tPASS\tSVTYPE=DEL\n"
    mods = _modules(text)
    assert "spectre" in mods  # header parsed
    assert "del" not in mods  # data line ignored


def test_empty_and_malformed_never_raise():
    assert extract_header_provenance([]).as_modules() == {}
    # Malformed lines: no '=', stray quotes, truncated VEP — must not raise.
    junk = [
        "##VEP=",
        "##GATKCommandLine=<ID=,Version=>",
        "##source=",
        "##weird line without equals",
        "##bcftools_=",
        "not even a header",
    ]
    assert isinstance(extract_header_provenance(junk).as_modules(), dict)


def test_merge_prefers_existing_then_fills_gaps():
    base = {"vep": {"version": "110"}, "clinvar": {"version": "202301"}}
    new = {"vep": {"version": "112"}, "gnomad": {"version": "v4.1"}}
    merged = merge_module_maps(base, new)
    assert merged["vep"]["version"] == "110"  # base wins
    assert merged["clinvar"]["version"] == "202301"  # base-only kept
    assert merged["gnomad"]["version"] == "v4.1"  # gap filled from new


def test_provenance_to_modules_combines_modalities():
    snv = extract_header_provenance(SNV_VEP_HEADER.splitlines(), modality="snv")
    sv = extract_header_provenance(SV_SNIFFLES_HEADER.splitlines(), modality="sv")
    trgt = extract_header_provenance(TRGT_HEADER.splitlines(), modality="repeats")
    combined = provenance_to_modules([snv, sv, trgt])
    # Each modality's caller is present in one merged family manifest.
    assert combined["deepvariant"]["version"] == "1.6.0"
    assert combined["sniffles"]["version"] == "2.2"
    assert combined["trgt"]["version"] == "0.7.0"
    assert combined["vep"]["version"] == "110"

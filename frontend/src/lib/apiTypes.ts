export interface ApiPaginatedTotalResponse {
  total: number;
}

export interface ApiVariantPage<TVariant> extends ApiPaginatedTotalResponse {
  total_is_estimated?: boolean;
  count_limit?: number | null;
  variants: TVariant[];
}

export interface ApiFamilyMemberRef {
  sample_id: string;
}

export interface ApiFamilyMember extends ApiFamilyMemberRef {
  role: string;
  affected: boolean;
  sex: string;
  clinical_status?: 'unknown' | 'unaffected' | 'affected';
  carrier_status?: 'unknown' | 'not_carrier' | 'carrier';
  carrier_type?: 'obligate' | 'proven' | 'reported' | 'inferred' | null;
  carrier_evidence?: Record<string, unknown>;
  active?: boolean;
}

export interface ApiFamilyMemberImpact {
  sample_id: string;
  pedigree_references: Record<string, number>;
  data_counts: Record<string, number>;
  affected_analysis_scopes: string[];
  stale_analysis_scopes: string[];
  warnings: string[];
  destructive: boolean;
  requires_manual_recalculation: boolean;
}

export interface ApiFamilyMemberDetail {
  member: ApiFamilyMember;
  father_id?: string | null;
  mother_id?: string | null;
  hpo_annotations: ApiHpoAnnotation[];
  impact: ApiFamilyMemberImpact;
}

export interface ApiFamilyMemberUpdateResponse {
  family: ApiFamilyRecord;
  member: ApiFamilyMember;
  father_id?: string | null;
  mother_id?: string | null;
  impact: ApiFamilyMemberImpact;
  warnings?: string[];
  stale_analysis_scopes?: string[];
  data_counts?: Record<string, number>;
  cleared_data_counts?: Record<string, number>;
}

export interface ApiFamilyMemberBatchUpdateItem {
  sample_id: string;
  new_sample_id?: string | null;
  sex?: 'male' | 'female' | 'und' | null;
  role?: 'proband' | 'father' | 'mother' | 'sibling' | 'embryo' | 'relative' | null;
  clinical_status?: 'unknown' | 'unaffected' | 'affected' | null;
  carrier_status?: 'unknown' | 'not_carrier' | 'carrier' | null;
  carrier_type?: 'obligate' | 'proven' | 'reported' | 'inferred' | null;
  father_id?: string | null;
  mother_id?: string | null;
}

export interface ApiFamilyMemberBatchUpdateResponse {
  family: ApiFamilyRecord;
  warnings?: string[];
  stale_analysis_scopes?: string[];
  data_counts?: Record<string, number>;
  cleared_data_counts?: Record<string, number>;
}

export interface ApiFamilyMemberDeleteResponse {
  family: ApiFamilyRecord;
  impact: ApiFamilyMemberImpact;
  warnings?: string[];
  stale_analysis_scopes?: string[];
  data_counts?: Record<string, number>;
  cleared_data_counts?: Record<string, number>;
}

export interface ApiFamilyRelationship {
  id: string;
  relationship_type: 'parent_child' | 'couple';
  sample_id_a: string;
  sample_id_b: string;
  role_a?: string | null;
  role_b?: string | null;
  source?: string;
  metadata?: Record<string, unknown>;
}

export interface ApiFamilyStructureVersion {
  version: number;
  structure_hash?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ApiFamilyRegionOfInterest {
  query: string;
  label: string;
  source: 'gene' | 'region';
  assembly_id?: string | null;
  chr: string;
  start: number;
  end: number;
}

export interface ApiFamilyBase<TMember = ApiFamilyMemberRef> {
  family_id: string;
  members: TMember[];
  projects?: string[];
  created_at?: string;
}

export interface ApiFamilySummary extends ApiFamilyBase<ApiFamilyMember> {
  id?: string;
  _id?: string;
}

export interface ApiFamilyRecord extends ApiFamilyBase<ApiFamilyMember> {
  _id?: string;
  relationships?: ApiFamilyRelationship[];
  structure_version?: ApiFamilyStructureVersion | null;
  pedigree?: string | null;
  roi?: ApiFamilyRegionOfInterest | null;
  metadata?: Record<string, unknown>;
}

export interface ApiHpoTerm {
  hpo_id: string;
  label: string;
  definition?: string | null;
  is_obsolete?: boolean;
}

export interface ApiHpoAnnotation {
  id: string;
  sample_id: string;
  hpo_id: string;
  label: string;
  definition?: string | null;
  status: 'present' | 'absent' | 'unknown';
  onset?: string | null;
  evidence?: string | null;
  source: string;
  note?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiHpoFamilyQuery {
  hpo_id: string;
  include_descendants: boolean;
  sample_ids: string[];
  annotations: ApiHpoAnnotation[];
}

export interface ApiSmallVariantReviewSummary {
  reviewed_variant_count: number;
  note_count: number;
  tag_counts: Record<string, number>;
}

export interface ApiProjectRecord<TFamily = ApiFamilySummary> {
  id: string;
  name: string;
  description?: string;
  species_id?: string;
  assembly_id?: string;
  species_name?: string;
  assembly_name?: string;
  assembly_version?: string;
  user_ids?: string[];
  families: TFamily[];
  samples: string[];
}

export interface ApiUserRecord {
  id: string;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  affiliation?: string | null;
  role: string;
  is_active: boolean;
  projects: string[];
}

export interface ApiSpeciesRecord {
  id: string;
  name: string;
  tax_id?: string | number;
  common_name?: string | null;
}

export interface ApiAssemblyRecord {
  id: string;
  species_id?: string;
  assembly_name: string;
  version: string;
}

export interface ApiClinicalCnv {
  _id: string;
  chr: string;
  start: number;
  end: number;
  type?: string | null;
  label: string;
  details_html?: string | null;
  assembly?: string | null;
  omim_id?: string | null;
  omim_title?: string | null;
  decipher_id?: string | null;
  description?: string | null;
  cytoband?: string | null;
  source_id?: string | null;
  orpha_id?: string | null;
  orpha_name?: string | null;
}

export interface ApiChromosomeBand {
  name: string;
  start: number;
  end: number;
  stain: string;
}

export interface ApiChromosome {
  chr: string;
  size: number;
  bands: ApiChromosomeBand[];
}

export type ApiTrackAvailabilityResponse<TTrackAvailability> = {
  samples: Record<string, TTrackAvailability>;
};

export interface ApiChromosomeTrackAvailability {
  coverage: boolean;
  apcad: boolean;
  apcad_pcf: boolean;
  variants: boolean;
  small_variants: boolean;
  haplotypes: boolean;
  repeat_expansions: boolean;
}

export interface ApiGenomeTrackAvailability {
  coverage: boolean;
  segments: boolean;
  apcad: boolean;
  apcad_pcf: boolean;
  haplotypes: boolean;
  variants: boolean;
  repeat_expansions: boolean;
}

export interface ApiRepeatExpansionMotifCount {
  motif: string;
  count: number;
}

export interface ApiRepeatExpansionAllele {
  repeat_count?: number | null;
  bp_length?: number | null;
  confidence_interval?: string | null;
  support_reads?: number | null;
  purity?: number | null;
  methylation?: number | null;
  motif_counts?: ApiRepeatExpansionMotifCount[];
  motif_spans?: string | null;
  interrupted?: boolean;
  interruption_label?: string | null;
  status: 'normal' | 'intermediate' | 'pathogenic' | 'unknown';
}

export interface ApiRepeatExpansionSampleCall {
  sample: string;
  role?: string | null;
  affected?: boolean | null;
  sex?: string | null;
  genotype: string;
  allele_count: number;
  alleles: ApiRepeatExpansionAllele[];
  status: 'normal' | 'intermediate' | 'pathogenic' | 'unknown';
}

export interface ApiRepeatExpansionRow {
  locus_id: string;
  gene: string;
  display_name: string;
  disease: string;
  inheritance?: string | null;
  chr: string;
  start: number;
  end: number;
  motif?: string | null;
  warning_min?: number | null;
  pathogenic_min?: number | null;
  status: 'normal' | 'intermediate' | 'pathogenic' | 'unknown';
  calls: Record<string, ApiRepeatExpansionSampleCall>;
}

export interface ApiFamilyRepeatExpansionTable {
  samples: ApiFamilyMember[];
  loci: ApiRepeatExpansionRow[];
}

export interface ApiParaphaseMetric {
  key: string;
  label: string;
  value?: number | null;
}

export interface ApiParaphaseHaplotypeGroup {
  key: string;
  label: string;
  count: number;
  haplotypes: string[];
}

export interface ApiParaphaseDisorder {
  name: string;
  omim_url?: string | null;
}

export interface ApiParaphaseRegionInfo {
  region_id: string;
  display_name: string;
  genes: string[];
  summary?: string | null;
  clinical_priority: number;
  key_copy_number_fields: string[];
  key_read_fields: string[];
  key_haplotype_fields: string[];
  key_extra_fields: string[];
  field_descriptions: Record<string, string>;
  notes: string[];
  disorders: ApiParaphaseDisorder[];
}

export interface ApiParaphaseExtraField {
  key: string;
  label: string;
  value?: unknown;
  description?: string | null;
}

export interface ApiParaphaseSampleResult {
  sample: string;
  role?: string | null;
  affected?: boolean | null;
  sex?: string | null;
  total_cn?: number | null;
  gene_cn?: number | null;
  highest_total_cn?: number | null;
  sample_sex?: string | null;
  phase_region?: string | null;
  region_depth: Record<string, unknown>;
  genome_depth?: number | null;
  final_haplotype_count: number;
  assembled_haplotype_count: number;
  variant_site_count: number;
  heterozygous_site_count: number;
  fusion_count?: number | null;
  copy_number_signal?: boolean;
  copy_number_metrics?: ApiParaphaseMetric[];
  read_metrics?: ApiParaphaseMetric[];
  haplotype_groups?: ApiParaphaseHaplotypeGroup[];
  extra_fields?: ApiParaphaseExtraField[];
  uploaded_at?: string | null;
}

export interface ApiParaphaseGeneResult {
  gene_symbol: string;
  is_medically_relevant?: boolean;
  region_info?: ApiParaphaseRegionInfo | null;
  max_total_cn?: number | null;
  max_gene_cn?: number | null;
  max_highest_total_cn?: number | null;
  has_copy_number_signal?: boolean;
  samples: Record<string, ApiParaphaseSampleResult>;
}

export interface ApiFamilyParaphaseTable {
  samples: ApiFamilyMember[];
  genes: ApiParaphaseGeneResult[];
}

export interface ApiMitoDNACoverage {
  mean_depth?: number | null;
  min_depth?: number | null;
  max_depth?: number | null;
  breadth?: number | null;
  source?: string | null;
  regions: number;
}

export interface ApiMitoDNAQc {
  status: 'pass' | 'warning' | 'fail' | 'unknown';
  notes: string[];
  contamination?: number | null;
  mean_depth?: number | null;
  min_mean_depth?: number | null;
}

export interface ApiMitoDNASample {
  sample_id: string;
  role?: string | null;
  affected?: boolean | null;
  sex?: string | null;
  haplogroup?: string | null;
  coverage: ApiMitoDNACoverage;
  qc: ApiMitoDNAQc;
}

export interface ApiMitoDNAVariantSampleCall {
  sample: string;
  role?: string | null;
  affected?: boolean | null;
  sex?: string | null;
  genotype: string;
  allele_fraction?: number | null;
  depth?: number | null;
  alt_depth?: number | null;
  zygosity: 'homoplasmic' | 'heteroplasmic' | 'low_level' | 'reference' | 'no_call' | 'unknown';
  display: string;
}

export interface ApiMitoDNAVariantAnnotation {
  region: string;
  gene?: string | null;
  consequence?: string | null;
  category?: string | null;
  clinical_significance:
    | 'pathogenic'
    | 'likely_pathogenic'
    | 'benign'
    | 'likely_benign'
    | 'reported'
    | 'uncertain'
    | 'polymorphism'
    | 'unknown';
  disorders: string[];
  polymorphism_notes: string[];
  mitomap_query: string;
  mitomap_url: string;
  source_keys: string[];
}

export interface ApiMitoDNAVariant {
  variant_id: string;
  position: number;
  ref: string;
  alt: string;
  label: string;
  type: string;
  rsid?: string | null;
  annotation: ApiMitoDNAVariantAnnotation;
  calls: Record<string, ApiMitoDNAVariantSampleCall>;
  maternal_transmission:
    | 'maternal_shared'
    | 'maternal_not_observed'
    | 'maternal_only'
    | 'father_only'
    | 'family_private'
    | 'no_alt_calls'
    | 'unknown';
}

export interface ApiFamilyMitoDNAAnalysis {
  samples: ApiMitoDNASample[];
  variants: ApiMitoDNAVariant[];
  qc_notes: string[];
  heteroplasmy_threshold: number;
  homoplasmy_threshold: number;
}

export interface ApiRepeatExpansionTrackItem {
  sample: string;
  locus_id: string;
  gene: string;
  display_name: string;
  disease: string;
  chr: string;
  start: number;
  end: number;
  motif?: string | null;
  warning_min?: number | null;
  pathogenic_min?: number | null;
  status: 'normal' | 'intermediate' | 'pathogenic' | 'unknown';
  allele_repeat_counts: number[];
  allele_bp_lengths: number[];
}

export interface ApiRepeatExpansionTrackResponse {
  items: ApiRepeatExpansionTrackItem[];
}

export interface ApiGithubRelease {
  version: string;
  name?: string | null;
  published_at: string;
  summary: string;
  url: string;
  prerelease: boolean;
}

export interface ApiGithubReleaseCatalog {
  repository: string;
  repository_url: string;
  releases_url: string;
  issues_url: string;
  repo_visibility: 'private' | 'public' | 'unknown';
  sync_status: 'ok' | 'unavailable';
  sync_error?: string | null;
  fetched_at?: string | null;
  releases: ApiGithubRelease[];
}

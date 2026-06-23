import React, { useMemo, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../lib/api';
import { getErrorMessage } from '../../lib/errorMessage';
import { useFamilyReference } from '../../lib/reference';
import type {
  ApiFamilyRecord,
  ApiNiptCoverageSummary,
  ApiNiptSummary,
} from '../../lib/apiTypes';
import {
  normalizeReviewClassification,
  parsePedigree,
  type GenePanel,
  type SmallVariant,
  type SmallVariantPage,
  type SmallVariantReview,
  type SmallVariantReviewSavePayload,
  type SmallVariantTagDefinition,
} from './smallVariantSearch';
import {
  buildOptimisticReview,
  buildSmallVariantReviewPath,
  hasReviewContent,
  updateSmallVariantPageReview,
} from './smallVariantReview';
import Pedigree from '../../components/visualizations/Pedigree';
import PageState from '../../components/PageState';
import SmallVariantResults from './SmallVariantResults';

const MONOGENIC_NIPT_ANALYSIS_TYPE = 'monogenic_nipt';
const PAGE_SIZE = 50;

const CATEGORY_LABELS: Record<number, string> = {
  1: 'De novo in fetus',
  2: 'Maternal het, not inherited',
  3: 'Maternal het, inherited',
  4: 'Maternal het → hom fetus',
  5: 'Maternal hom, het fetus',
  6: 'Maternal & fetal hom',
  7: 'Paternal, transmitted',
  8: 'Paternal hom-alt, absent (FN)',
};
const CATEGORY_NUMBERS = Object.keys(CATEGORY_LABELS).map(Number);

const INHERITANCE_PRESETS: { value: string; label: string }[] = [
  { value: '', label: 'Any inheritance' },
  { value: 'de_novo', label: 'De novo candidates' },
  { value: 'paternal_dominant', label: 'Paternal dominant (transmitted)' },
  { value: 'maternal_dominant', label: 'Maternal dominant (transmitted)' },
  { value: 'recessive_at_risk', label: 'Recessive at-risk' },
];

const FILTER_STEPS: { key: string; label: string }[] = [
  { key: 'total_in', label: 'Total' },
  { key: 'failed_quality', label: 'Quality-filtered' },
  { key: 'failed_artifact', label: 'Artifact-filtered' },
  { key: 'passed', label: 'Analysed' },
];

const IMPACT_OPTIONS = ['HIGH', 'MODERATE', 'LOW', 'MODIFIER'];
const EFFECT_OPTIONS = [
  'frameshift_variant',
  'stop_gained',
  'stop_lost',
  'start_lost',
  'splice_acceptor_variant',
  'splice_donor_variant',
  'missense_variant',
  'inframe_insertion',
  'inframe_deletion',
  'protein_altering_variant',
  'splice_region_variant',
  'synonymous_variant',
  'intron_variant',
];

const pct = (value?: number | null): string =>
  value == null ? '—' : `${(value * 100).toFixed(1)}%`;

const depth = (value?: number | null): string =>
  value == null ? '—' : `${value.toFixed(0)}x`;

interface NiptFilters {
  panelId: string;
  gene: string;
  excludeGene: string;
  intervals: string;
  categories: number[];
  inheritance: string;
  minConfidence: string;
  impact: string[];
  effect: string[];
  maxGnomadAf: string;
  maxGnomadPopmaxAf: string;
  minCadd: string;
  minRevel: string;
  minSpliceai: string;
  canonicalOnly: boolean;
  maneOnly: boolean;
  lofOnly: boolean;
}

const EMPTY_FILTERS: NiptFilters = {
  panelId: '',
  gene: '',
  excludeGene: '',
  intervals: '',
  categories: [],
  inheritance: '',
  minConfidence: '',
  impact: [],
  effect: [],
  maxGnomadAf: '',
  maxGnomadPopmaxAf: '',
  minCadd: '',
  minRevel: '',
  minSpliceai: '',
  canonicalOnly: false,
  maneOnly: false,
  lofOnly: false,
};

// Serialize repeated params (category/impact/effect arrays) as `key=a&key=b`,
// which is what the FastAPI `Query(None)` list params expect.
const niptParamsSerializer = (params: Record<string, unknown>): string => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((item) => search.append(key, String(item)));
    } else if (value !== undefined && value !== null && value !== '') {
      search.append(key, String(value));
    }
  });
  return search.toString();
};

const buildVariantParams = (filters: NiptFilters, page: number): Record<string, unknown> => {
  const params: Record<string, unknown> = { page, page_size: PAGE_SIZE };
  if (filters.panelId) params.panel_id = filters.panelId;
  if (filters.gene.trim()) params.gene = filters.gene.trim();
  if (filters.excludeGene.trim()) params.exclude_gene = filters.excludeGene.trim();
  if (filters.intervals.trim()) params.intervals = filters.intervals.trim();
  if (filters.categories.length) params.category = [...filters.categories].sort((a, b) => a - b);
  if (filters.inheritance) params.inheritance = filters.inheritance;
  if (filters.minConfidence) params.min_confidence = Number(filters.minConfidence);
  if (filters.impact.length) params.impact = filters.impact;
  if (filters.effect.length) params.effect = filters.effect;
  if (filters.maxGnomadAf) params.max_gnomad_af = Number(filters.maxGnomadAf);
  if (filters.maxGnomadPopmaxAf) params.max_gnomad_popmax_af = Number(filters.maxGnomadPopmaxAf);
  if (filters.minCadd) params.min_cadd = Number(filters.minCadd);
  if (filters.minRevel) params.min_revel = Number(filters.minRevel);
  if (filters.minSpliceai) params.min_spliceai = Number(filters.minSpliceai);
  if (filters.canonicalOnly) params.canonical_only = true;
  if (filters.maneOnly) params.mane_only = true;
  if (filters.lofOnly) params.lof_only = true;
  return params;
};

interface ActiveChip {
  id: string;
  label: string;
  clear: () => NiptFilters;
}

const buildActiveChips = (filters: NiptFilters): ActiveChip[] => {
  const chips: ActiveChip[] = [];
  const add = (id: string, label: string, clear: () => NiptFilters) =>
    chips.push({ id, label, clear });

  if (filters.panelId) add('panel', 'Gene panel', () => ({ ...filters, panelId: '' }));
  if (filters.gene.trim()) add('gene', `Gene: ${filters.gene.trim()}`, () => ({ ...filters, gene: '' }));
  if (filters.excludeGene.trim())
    add('exclude_gene', `Exclude: ${filters.excludeGene.trim()}`, () => ({ ...filters, excludeGene: '' }));
  if (filters.intervals.trim())
    add('intervals', 'Intervals', () => ({ ...filters, intervals: '' }));
  filters.categories.forEach((category) =>
    add(`cat-${category}`, `Cat ${category}`, () => ({
      ...filters,
      categories: filters.categories.filter((value) => value !== category),
    })),
  );
  if (filters.inheritance) {
    const label = INHERITANCE_PRESETS.find((preset) => preset.value === filters.inheritance)?.label;
    add('inheritance', label ?? filters.inheritance, () => ({ ...filters, inheritance: '' }));
  }
  if (filters.minConfidence)
    add('min_confidence', `Confidence ≥ ${filters.minConfidence}`, () => ({ ...filters, minConfidence: '' }));
  filters.impact.forEach((impact) =>
    add(`impact-${impact}`, impact, () => ({
      ...filters,
      impact: filters.impact.filter((value) => value !== impact),
    })),
  );
  filters.effect.forEach((effect) =>
    add(`effect-${effect}`, effect, () => ({
      ...filters,
      effect: filters.effect.filter((value) => value !== effect),
    })),
  );
  if (filters.maxGnomadAf)
    add('gnomad_af', `gnomAD ≤ ${filters.maxGnomadAf}`, () => ({ ...filters, maxGnomadAf: '' }));
  if (filters.maxGnomadPopmaxAf)
    add('gnomad_popmax', `gnomAD popmax ≤ ${filters.maxGnomadPopmaxAf}`, () => ({
      ...filters,
      maxGnomadPopmaxAf: '',
    }));
  if (filters.minCadd) add('cadd', `CADD ≥ ${filters.minCadd}`, () => ({ ...filters, minCadd: '' }));
  if (filters.minRevel) add('revel', `REVEL ≥ ${filters.minRevel}`, () => ({ ...filters, minRevel: '' }));
  if (filters.minSpliceai)
    add('spliceai', `SpliceAI ≥ ${filters.minSpliceai}`, () => ({ ...filters, minSpliceai: '' }));
  if (filters.canonicalOnly) add('canonical', 'Canonical only', () => ({ ...filters, canonicalOnly: false }));
  if (filters.maneOnly) add('mane', 'MANE only', () => ({ ...filters, maneOnly: false }));
  if (filters.lofOnly) add('lof', 'LoF only', () => ({ ...filters, lofOnly: false }));
  return chips;
};

const summarize = (count: number): string => (count ? `${count} filter${count === 1 ? '' : 's'}` : 'No filters');

const FamilyNiptPage: React.FC = () => {
  const { familyId } = useParams<{ familyId: string }>();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<NiptFilters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<NiptFilters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [filtersCollapsed, setFiltersCollapsed] = useState(false);
  // All filter subsections start collapsed.
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({});

  const setField = <K extends keyof NiptFilters>(key: K, value: NiptFilters[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));
  const toggleListValue = (key: 'categories' | 'impact' | 'effect', value: number | string) =>
    setDraft((current) => {
      const list = current[key] as (number | string)[];
      const next = list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
      return { ...current, [key]: next } as NiptFilters;
    });
  const sectionToggle = (key: string) => (event: React.SyntheticEvent<HTMLDetailsElement>) => {
    // jsdom fires a spurious toggle on mount of a controlled <details> with a
    // null currentTarget; ignore those and only react to real user toggles.
    const details = event.currentTarget;
    if (!details) return;
    const open = details.open;
    setOpenSections((current) => ({ ...current, [key]: open }));
  };

  const handleApply = (event?: React.FormEvent) => {
    event?.preventDefault();
    setApplied(draft);
    setPage(1);
  };
  const handleReset = () => {
    setDraft(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
    setPage(1);
  };
  const removeChip = (chip: ActiveChip) => {
    const next = chip.clear();
    setDraft(next);
    setApplied(next);
    setPage(1);
  };

  const { data: family, isLoading: familyLoading, isError: familyError } = useQuery<ApiFamilyRecord>({
    queryKey: ['family', familyId],
    enabled: Boolean(familyId),
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}`);
      return res.data as ApiFamilyRecord;
    },
  });

  const isMonogenicNipt = family?.metadata?.analysis_type === MONOGENIC_NIPT_ANALYSIS_TYPE;

  const { data: panels = [] } = useQuery<GenePanel[]>({
    queryKey: ['panels'],
    enabled: Boolean(familyId && isMonogenicNipt),
    queryFn: async () => {
      const res = await api.get('/panels');
      return res.data as GenePanel[];
    },
  });

  const { data: summary } = useQuery<ApiNiptSummary>({
    queryKey: ['family', familyId, 'nipt', 'summary'],
    enabled: Boolean(familyId && isMonogenicNipt),
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}/nipt/summary`);
      return res.data as ApiNiptSummary;
    },
  });

  const { data: coverage } = useQuery<ApiNiptCoverageSummary>({
    queryKey: ['family', familyId, 'nipt', 'coverage', applied.panelId, applied.gene],
    enabled: Boolean(familyId && isMonogenicNipt),
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (applied.panelId) params.panel_id = applied.panelId;
      if (applied.gene.trim()) params.gene = applied.gene.trim();
      const res = await api.get(`/families/${familyId}/nipt/coverage`, { params });
      return res.data as ApiNiptCoverageSummary;
    },
  });

  // The reference (assembly/species/project) powers the reused small-variant
  // card's IGV/gene links and the review/ACMG project scoping.
  const { speciesName, assemblyName, assemblyVersion, projectId } = useFamilyReference(
    family?.projects,
  );

  const { data: tags = [] } = useQuery<SmallVariantTagDefinition[]>({
    queryKey: ['family', familyId, 'small-variant-tags', projectId || null],
    enabled: Boolean(familyId && isMonogenicNipt),
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}/small-variant-tags`, {
        params: projectId ? { project_id: projectId } : undefined,
      });
      return res.data as SmallVariantTagDefinition[];
    },
  });

  // The NIPT variants endpoint now returns the full small-variant payload plus a
  // per-variant `nipt` classification block, so it is a SmallVariantPage.
  const niptVariantsKey = ['family', familyId, 'nipt', 'variants'] as const;
  const { data: variantPage, isFetching: variantsFetching } = useQuery<SmallVariantPage>({
    queryKey: [...niptVariantsKey, JSON.stringify(applied), page],
    enabled: Boolean(familyId && isMonogenicNipt),
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}/nipt/variants`, {
        params: buildVariantParams(applied, page),
        paramsSerializer: niptParamsSerializer,
      });
      return res.data as SmallVariantPage;
    },
    placeholderData: keepPreviousData,
  });

  // Variant review (tag / report / classification). The endpoints are shared
  // with the small-variant view; only the optimistic cache key differs.
  const reviewMutation = useMutation({
    mutationFn: async ({
      variant,
      payload,
    }: {
      variant: SmallVariant;
      payload: SmallVariantReviewSavePayload;
    }) => {
      if (!familyId) {
        throw new Error('Family id is required');
      }
      const reviewPath = buildSmallVariantReviewPath(familyId, variant._id);
      const res = projectId
        ? await api.put(reviewPath, payload, { params: { project_id: projectId } })
        : await api.put(reviewPath, payload);
      return res.data as SmallVariantReview;
    },
    onMutate: async ({ variant, payload }) => {
      await queryClient.cancelQueries({ queryKey: niptVariantsKey });
      const snapshots = queryClient.getQueriesData<SmallVariantPage>({ queryKey: niptVariantsKey });
      const optimisticReview = buildOptimisticReview(variant, payload);
      snapshots.forEach(([key]) => {
        queryClient.setQueryData<SmallVariantPage>(key, (current) =>
          updateSmallVariantPageReview(current, variant._id, optimisticReview),
        );
      });
      return { snapshots };
    },
    onSuccess: (review, { variant }) => {
      queryClient.getQueriesData<SmallVariantPage>({ queryKey: niptVariantsKey }).forEach(([key]) => {
        queryClient.setQueryData<SmallVariantPage>(key, (current) =>
          updateSmallVariantPageReview(current, variant._id, hasReviewContent(review) ? review : null),
        );
      });
      void queryClient.invalidateQueries({ queryKey: niptVariantsKey });
    },
    onError: (_error, _variables, context) => {
      context?.snapshots.forEach(([key, snapshot]) => {
        queryClient.setQueryData(key, snapshot);
      });
    },
  });

  const pedRows = useMemo(() => parsePedigree(family?.pedigree), [family?.pedigree]);
  const activeChips = useMemo(() => buildActiveChips(applied), [applied]);
  const categoryCounts = summary?.category_counts ?? {};

  if (familyLoading) {
    return <PageState kicker="Monogenic NIPT" title="Loading family…" />;
  }
  if (familyError || !family) {
    return (
      <PageState
        kicker="Monogenic NIPT"
        title="Family not found"
        message="This family could not be loaded."
        action={<Link className="button-secondary" to="/families">Back to families</Link>}
      />
    );
  }
  if (!isMonogenicNipt) {
    return (
      <PageState
        kicker="Monogenic NIPT"
        title="Not a monogenic NIPT family"
        message={`Family ${family.family_id} is not configured for monogenic NIPT analysis.`}
        action={
          <Link className="button-secondary" to={`/families/${family.family_id}`}>
            Back to family
          </Link>
        }
      />
    );
  }

  const ff = summary?.fetal_fraction;
  const totalVariants = variantPage?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(totalVariants / PAGE_SIZE));

  // Filter-count badges per section.
  const locationCount =
    (applied.panelId ? 1 : 0) +
    (applied.gene.trim() ? 1 : 0) +
    (applied.excludeGene.trim() ? 1 : 0) +
    (applied.intervals.trim() ? 1 : 0);
  const annotationCount = draft.impact.length + draft.effect.length;
  const frequencyCount = (draft.maxGnomadAf ? 1 : 0) + (draft.maxGnomadPopmaxAf ? 1 : 0);
  const inSilicoCount = (draft.minCadd ? 1 : 0) + (draft.minRevel ? 1 : 0) + (draft.minSpliceai ? 1 : 0);
  const flagCount = (draft.canonicalOnly ? 1 : 0) + (draft.maneOnly ? 1 : 0) + (draft.lofOnly ? 1 : 0);

  return (
    <div className="page-shell analysis-shell">
      <section className="surface-card page-top-card variant-workbench-card">
        <div className={`page-top-card-grid${pedRows.length ? ' page-top-card-grid--with-visual' : ''}`}>
          <div className="page-top-card-copy">
            <div className="page-header">
              <div className="space-y-2">
                <p className="page-kicker">Monogenic NIPT</p>
                <h1 className="catalog-card-title">Family {family.family_id}</h1>
                <div className="variant-sample-summary">
                  <div className="variant-summary-row">
                    <span className="badge-chip badge-chip--signature">Fetal fraction {pct(ff?.ff)}</span>
                    {ff?.ci_low != null && ff?.ci_high != null ? (
                      <span className="badge-chip">95% CI {pct(ff.ci_low)}–{pct(ff.ci_high)}</span>
                    ) : null}
                    {ff ? (
                      <span className="badge-chip" title={ff.method}>
                        {ff.n_sites} cat-7 sites
                      </span>
                    ) : null}
                    {ff?.low_confidence ? <span className="badge-chip">Low-confidence FF</span> : null}
                    {ff?.ff_external != null ? (
                      <span className="badge-chip">External FF {pct(ff.ff_external)}</span>
                    ) : null}
                    {ff?.disagreement ? <span className="badge-chip">FF disagreement</span> : null}
                  </div>
                  <div className="variant-summary-row">
                    {FILTER_STEPS.map((step) => (
                      <span className="badge-chip" key={step.key}>
                        {step.label} {summary?.filter_counts?.[step.key] ?? 0}
                      </span>
                    ))}
                    <span className="badge-chip">Active filters {activeChips.length}</span>
                    {variantsFetching ? <span className="badge-chip">Updating…</span> : null}
                  </div>
                </div>
              </div>
              <div className="inline-actions">
                <Link to={`/families/${family.family_id}`} className="button-ghost hover:no-underline">
                  Family
                </Link>
              </div>
            </div>
          </div>
          {pedRows.length > 0 && (
            <div className="page-top-card-visual">
              <div className="page-top-card-pedigree">
                <p className="analysis-section-title">Pedigree</p>
                <Pedigree rows={pedRows} members={family.members} relationships={family.relationships ?? []} />
              </div>
            </div>
          )}
        </div>

        <div className="variant-filter-collapse-bar">
          <button
            type="button"
            className="variant-filter-collapse-toggle"
            aria-expanded={!filtersCollapsed}
            onClick={() => setFiltersCollapsed((current) => !current)}
          >
            <span className="variant-filter-dropdown-caret" aria-hidden="true">▾</span>
            <span>{filtersCollapsed ? 'Show filters' : 'Hide filters'}</span>
          </button>
        </div>

        {!filtersCollapsed && (
          <form onSubmit={handleApply} className="space-y-4 variant-search-workspace">
            <div className="variant-search-header">
              <div className="variant-search-meta">
                <div className="variant-search-toolbar">
                  <button type="submit" className="form-button">
                    Apply filters
                  </button>
                  <button type="button" className="button-secondary" onClick={handleReset}>
                    Clear all filters
                  </button>
                </div>
              </div>
            </div>

            {activeChips.length ? (
              <section className="variant-search-section">
                <div className="variant-search-section-copy">
                  <p className="analysis-section-title">Active filters</p>
                </div>
                <div className="variant-filter-chip-list">
                  {activeChips.map((chip) => (
                    <button
                      key={chip.id}
                      type="button"
                      className="badge-chip variant-filter-chip"
                      onClick={() => removeChip(chip)}
                    >
                      {chip.label} ✕
                    </button>
                  ))}
                </div>
              </section>
            ) : null}

            <section className="variant-search-section">
              <div className="variant-filter-dropdown-grid">
                {/* Locations: gene panel + gene + intervals */}
                <details
                  className="variant-filter-dropdown"
                  open={!!openSections.locations}
                  onToggle={sectionToggle('locations')}
                >
                  <summary className="variant-filter-dropdown-summary">
                    <span className="variant-filter-dropdown-summary-copy">
                      <span className="variant-filter-dropdown-title">Locations</span>
                      <span className="variant-filter-dropdown-meta">{summarize(locationCount)}</span>
                    </span>
                    <span
                      className="variant-filter-dropdown-summary-controls"
                      onMouseDown={(event) => event.stopPropagation()}
                      onClick={(event) => event.stopPropagation()}
                    >
                      <label className="variant-summary-select-field">
                        <span>Panel</span>
                        <select
                          aria-label="Gene panel"
                          value={draft.panelId}
                          onChange={(event) => setField('panelId', event.target.value)}
                        >
                          <option value="">Any gene panel</option>
                          {panels.map((panel) => (
                            <option key={panel._id} value={panel._id}>
                              {panel.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    </span>
                    <span className="variant-filter-dropdown-caret" aria-hidden="true">▾</span>
                  </summary>
                  <div className="variant-filter-dropdown-content">
                    <label className="analysis-field-label">
                      Genes
                      <textarea
                        rows={3}
                        value={draft.gene}
                        onChange={(event) => setField('gene', event.target.value)}
                        placeholder="BRCA1, BRCA2, TP53"
                      />
                    </label>
                    <label className="analysis-field-label">
                      Exclude genes
                      <textarea
                        rows={2}
                        value={draft.excludeGene}
                        onChange={(event) => setField('excludeGene', event.target.value)}
                        placeholder="Genes to exclude"
                      />
                    </label>
                    <label className="analysis-field-label">
                      Intervals
                      <textarea
                        rows={2}
                        value={draft.intervals}
                        onChange={(event) => setField('intervals', event.target.value)}
                        placeholder="chr13:32315086-32400266"
                      />
                    </label>
                  </div>
                </details>

                {/* Categories: the NIPT-specific filter, replacing the genotype subsection */}
                <details
                  className="variant-filter-dropdown"
                  open={!!openSections.categories}
                  onToggle={sectionToggle('categories')}
                >
                  <summary className="variant-filter-dropdown-summary">
                    <span className="variant-filter-dropdown-summary-copy">
                      <span className="variant-filter-dropdown-title">Maternal/fetal categories</span>
                      <span className="variant-filter-dropdown-meta">
                        {draft.categories.length ? `${draft.categories.length} selected` : 'All categories'}
                      </span>
                    </span>
                    <span className="variant-filter-dropdown-caret" aria-hidden="true">▾</span>
                  </summary>
                  <div className="variant-filter-dropdown-content">
                    <div className="nipt-category-grid">
                      {CATEGORY_NUMBERS.map((category) => (
                        <label key={category} className="analysis-checkbox nipt-category-option">
                          <input
                            type="checkbox"
                            checked={draft.categories.includes(category)}
                            onChange={() => toggleListValue('categories', category)}
                          />
                          <span className="nipt-category-option-copy">
                            <span className="nipt-category-option-label">
                              {category} — {CATEGORY_LABELS[category]}
                            </span>
                            <span className="nipt-category-option-count">
                              {(categoryCounts[String(category)] ?? 0).toLocaleString()}
                            </span>
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>
                </details>

                {/* Inheritance preset + confidence */}
                <details className="variant-filter-dropdown" open={!!openSections.inheritance} onToggle={sectionToggle('inheritance')}>
                  <summary className="variant-filter-dropdown-summary">
                    <span className="variant-filter-dropdown-summary-copy">
                      <span className="variant-filter-dropdown-title">Inheritance &amp; confidence</span>
                      <span className="variant-filter-dropdown-meta">
                        {summarize((draft.inheritance ? 1 : 0) + (draft.minConfidence ? 1 : 0))}
                      </span>
                    </span>
                    <span className="variant-filter-dropdown-caret" aria-hidden="true">▾</span>
                  </summary>
                  <div className="variant-filter-dropdown-content">
                    <div className="analysis-filter-grid analysis-filter-grid--2">
                      <label className="analysis-field-label">
                        Inheritance
                        <select value={draft.inheritance} onChange={(event) => setField('inheritance', event.target.value)}>
                          {INHERITANCE_PRESETS.map((preset) => (
                            <option key={preset.value} value={preset.value}>
                              {preset.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="analysis-field-label">
                        Min confidence
                        <input
                          type="number"
                          min={0}
                          max={1}
                          step={0.05}
                          value={draft.minConfidence}
                          onChange={(event) => setField('minConfidence', event.target.value)}
                          placeholder="0.00"
                        />
                      </label>
                    </div>
                  </div>
                </details>

                {/* Annotation: impact + effect */}
                <details className="variant-filter-dropdown" open={!!openSections.annotation} onToggle={sectionToggle('annotation')}>
                  <summary className="variant-filter-dropdown-summary">
                    <span className="variant-filter-dropdown-summary-copy">
                      <span className="variant-filter-dropdown-title">Annotation</span>
                      <span className="variant-filter-dropdown-meta">{summarize(annotationCount)}</span>
                    </span>
                    <span className="variant-filter-dropdown-caret" aria-hidden="true">▾</span>
                  </summary>
                  <div className="variant-filter-dropdown-content space-y-3">
                    <div>
                      <p className="analysis-section-title">Impact</p>
                      <div className="variant-gt-toggle-row">
                        {IMPACT_OPTIONS.map((impact) => (
                          <label key={impact} className="analysis-checkbox">
                            <input
                              type="checkbox"
                              checked={draft.impact.includes(impact)}
                              onChange={() => toggleListValue('impact', impact)}
                            />
                            {impact}
                          </label>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="analysis-section-title">Consequence</p>
                      <div className="nipt-effect-grid">
                        {EFFECT_OPTIONS.map((effect) => (
                          <label key={effect} className="analysis-checkbox">
                            <input
                              type="checkbox"
                              checked={draft.effect.includes(effect)}
                              onChange={() => toggleListValue('effect', effect)}
                            />
                            {effect}
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                </details>

                {/* Frequencies */}
                <details className="variant-filter-dropdown" open={!!openSections.frequencies} onToggle={sectionToggle('frequencies')}>
                  <summary className="variant-filter-dropdown-summary">
                    <span className="variant-filter-dropdown-summary-copy">
                      <span className="variant-filter-dropdown-title">Frequencies</span>
                      <span className="variant-filter-dropdown-meta">{summarize(frequencyCount)}</span>
                    </span>
                    <span className="variant-filter-dropdown-caret" aria-hidden="true">▾</span>
                  </summary>
                  <div className="variant-filter-dropdown-content">
                    <div className="analysis-filter-grid analysis-filter-grid--2">
                      <input
                        type="number"
                        step="any"
                        placeholder="gnomAD AF ≤"
                        value={draft.maxGnomadAf}
                        onChange={(event) => setField('maxGnomadAf', event.target.value)}
                      />
                      <input
                        type="number"
                        step="any"
                        placeholder="gnomAD popmax AF ≤"
                        value={draft.maxGnomadPopmaxAf}
                        onChange={(event) => setField('maxGnomadPopmaxAf', event.target.value)}
                      />
                    </div>
                  </div>
                </details>

                {/* In silico */}
                <details className="variant-filter-dropdown" open={!!openSections.inSilico} onToggle={sectionToggle('inSilico')}>
                  <summary className="variant-filter-dropdown-summary">
                    <span className="variant-filter-dropdown-summary-copy">
                      <span className="variant-filter-dropdown-title">In silico</span>
                      <span className="variant-filter-dropdown-meta">{summarize(inSilicoCount)}</span>
                    </span>
                    <span className="variant-filter-dropdown-caret" aria-hidden="true">▾</span>
                  </summary>
                  <div className="variant-filter-dropdown-content">
                    <div className="analysis-filter-grid analysis-filter-grid--3">
                      <input
                        type="number"
                        step="any"
                        placeholder="CADD ≥"
                        value={draft.minCadd}
                        onChange={(event) => setField('minCadd', event.target.value)}
                      />
                      <input
                        type="number"
                        step="any"
                        placeholder="REVEL ≥"
                        value={draft.minRevel}
                        onChange={(event) => setField('minRevel', event.target.value)}
                      />
                      <input
                        type="number"
                        step="any"
                        placeholder="SpliceAI ≥"
                        value={draft.minSpliceai}
                        onChange={(event) => setField('minSpliceai', event.target.value)}
                      />
                    </div>
                  </div>
                </details>

                {/* Flags */}
                <details className="variant-filter-dropdown" open={!!openSections.flags} onToggle={sectionToggle('flags')}>
                  <summary className="variant-filter-dropdown-summary">
                    <span className="variant-filter-dropdown-summary-copy">
                      <span className="variant-filter-dropdown-title">Flags</span>
                      <span className="variant-filter-dropdown-meta">{summarize(flagCount)}</span>
                    </span>
                    <span className="variant-filter-dropdown-caret" aria-hidden="true">▾</span>
                  </summary>
                  <div className="variant-filter-dropdown-content">
                    <div className="variant-gt-toggle-row">
                      <label className="analysis-checkbox">
                        <input
                          type="checkbox"
                          checked={draft.canonicalOnly}
                          onChange={(event) => setField('canonicalOnly', event.target.checked)}
                        />
                        Canonical only
                      </label>
                      <label className="analysis-checkbox">
                        <input
                          type="checkbox"
                          checked={draft.maneOnly}
                          onChange={(event) => setField('maneOnly', event.target.checked)}
                        />
                        MANE only
                      </label>
                      <label className="analysis-checkbox">
                        <input
                          type="checkbox"
                          checked={draft.lofOnly}
                          onChange={(event) => setField('lofOnly', event.target.checked)}
                        />
                        LoF only
                      </label>
                    </div>
                  </div>
                </details>
              </div>
            </section>
          </form>
        )}
      </section>

      <div className="variant-results-region">
        <SmallVariantResults
          assemblyName={assemblyName}
          assemblyVersion={assemblyVersion}
          data={variantPage}
          familyId={familyId}
          locationSearch={location.search}
          members={family.members ?? []}
          onPageChange={setPage}
          page={page}
          projectId={projectId}
          requestQueryString=""
          speciesName={speciesName}
          totalPages={pageCount}
          tags={tags}
          showCsvExport={false}
          reviewIsPending={reviewMutation.isPending}
          reviewError={
            reviewMutation.isError
              ? getErrorMessage(reviewMutation.error, 'Unable to save the variant review')
              : null
          }
          onToggleReviewTag={async (variant, tagKey) => {
            const nextTags = new Set(variant.review?.tags || []);
            if (nextTags.has(tagKey)) {
              nextTags.delete(tagKey);
            } else {
              nextTags.add(tagKey);
            }
            await reviewMutation.mutateAsync({
              variant,
              payload: {
                classification:
                  normalizeReviewClassification(
                    variant.review?.classification,
                    variant.review?.tags,
                  ) || undefined,
                tags: Array.from(nextTags).sort((left, right) => left.localeCompare(right)),
                note: variant.review?.note || undefined,
              },
            });
          }}
          onOpenReview={() => reviewMutation.reset()}
          onSaveReview={async (variant, payload) => {
            await reviewMutation.mutateAsync({ variant, payload });
          }}
        />

        <section className="surface-card space-y-2" aria-label="On-target coverage">
          <h2 className="section-title">On-target coverage</h2>
          {coverage ? (
            coverage.target_region_count === 0 ? (
              <p className="table-subtle">
                No target regions — set a family ROI or gene panel to report coverage.
              </p>
            ) : (
              <div className="family-workspace-summary">
                <div className="family-workspace-stat">
                  <span className="family-workspace-stat-value">{depth(coverage.overall_median_on_target)}</span>
                  <span className="family-workspace-stat-copy">
                    Median on-target ({coverage.target_region_count} region
                    {coverage.target_region_count === 1 ? '' : 's'})
                  </span>
                </div>
              </div>
            )
          ) : (
            <p className="table-subtle">Loading coverage…</p>
          )}
        </section>
      </div>
    </div>
  );
};

export default FamilyNiptPage;

import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../lib/api';
import type {
  ApiFamilyRecord,
  ApiNiptCoverageSummary,
  ApiNiptSummary,
  ApiNiptVariantPage,
} from '../../lib/apiTypes';
import PageState from '../../components/PageState';

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

const INHERITANCE_PRESETS: { value: string; label: string }[] = [
  { value: '', label: 'Any inheritance' },
  { value: 'de_novo', label: 'De novo candidates' },
  { value: 'paternal_dominant', label: 'Paternal dominant (transmitted)' },
  { value: 'maternal_dominant', label: 'Maternal dominant (transmitted)' },
];

const FILTER_STEPS: { key: string; label: string }[] = [
  { key: 'total_in', label: 'Total' },
  { key: 'failed_quality', label: 'Quality-filtered' },
  { key: 'failed_artifact', label: 'Artifact-filtered' },
  { key: 'passed', label: 'Analysed' },
];

const pct = (value?: number | null): string =>
  value == null ? '—' : `${(value * 100).toFixed(1)}%`;

const depth = (value?: number | null): string =>
  value == null ? '—' : `${value.toFixed(0)}x`;

const FamilyNiptPage: React.FC = () => {
  const { familyId } = useParams<{ familyId: string }>();

  const [gene, setGene] = useState('');
  const [inheritance, setInheritance] = useState('');
  const [category, setCategory] = useState('');
  const [minConfidence, setMinConfidence] = useState('');
  const [page, setPage] = useState(1);

  const { data: family, isLoading: familyLoading, isError: familyError } =
    useQuery<ApiFamilyRecord>({
      queryKey: ['family', familyId],
      enabled: Boolean(familyId),
      queryFn: async () => {
        const res = await api.get(`/families/${familyId}`);
        return res.data as ApiFamilyRecord;
      },
    });

  const isMonogenicNipt =
    family?.metadata?.analysis_type === MONOGENIC_NIPT_ANALYSIS_TYPE;

  const { data: summary } = useQuery<ApiNiptSummary>({
    queryKey: ['family', familyId, 'nipt', 'summary'],
    enabled: Boolean(familyId && isMonogenicNipt),
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}/nipt/summary`);
      return res.data as ApiNiptSummary;
    },
  });

  const { data: coverage } = useQuery<ApiNiptCoverageSummary>({
    queryKey: ['family', familyId, 'nipt', 'coverage'],
    enabled: Boolean(familyId && isMonogenicNipt),
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}/nipt/coverage`);
      return res.data as ApiNiptCoverageSummary;
    },
  });

  const { data: variantPage, isFetching: variantsFetching } =
    useQuery<ApiNiptVariantPage>({
      queryKey: [
        'family',
        familyId,
        'nipt',
        'variants',
        gene,
        inheritance,
        category,
        minConfidence,
        page,
      ],
      enabled: Boolean(familyId && isMonogenicNipt),
      queryFn: async () => {
        const params: Record<string, string | number> = {
          page,
          page_size: PAGE_SIZE,
        };
        if (gene.trim()) params.gene = gene.trim();
        if (inheritance) params.inheritance = inheritance;
        if (category) params.category = Number(category);
        if (minConfidence) params.min_confidence = Number(minConfidence);
        const res = await api.get(`/families/${familyId}/nipt/variants`, { params });
        return res.data as ApiNiptVariantPage;
      },
    });

  if (familyLoading) {
    return <PageState kicker="Monogenic NIPT" title="Loading family…" />;
  }

  if (familyError || !family) {
    return (
      <PageState
        kicker="Monogenic NIPT"
        title="Family not found"
        message="This family could not be loaded."
        action={
          <Link className="button-secondary" to="/families">
            Back to families
          </Link>
        }
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
  const onFilterChange = <T,>(setter: (value: T) => void) => (value: T) => {
    setter(value);
    setPage(1);
  };

  return (
    <div className="page-shell space-y-6">
      <header className="page-header">
        <p className="page-kicker">Monogenic NIPT</p>
        <h1 className="section-title">Monogenic NIPT analysis — {family.family_id}</h1>
        <Link className="button-secondary hover:no-underline" to={`/families/${family.family_id}`}>
          Back to family overview
        </Link>
      </header>

      <section className="surface-card space-y-2" aria-label="Fetal fraction">
        <h2 className="section-title">Fetal fraction</h2>
        {ff ? (
          <div className="family-workspace-summary">
            <div className="family-workspace-stat">
              <span className="family-workspace-stat-value">{pct(ff.ff)}</span>
              <span className="family-workspace-stat-copy">
                {ff.ci_low != null && ff.ci_high != null
                  ? `95% CI ${pct(ff.ci_low)}–${pct(ff.ci_high)}`
                  : 'No confidence interval'}
              </span>
            </div>
            <div className="family-workspace-stat">
              <span className="family-workspace-stat-value">{ff.n_sites}</span>
              <span className="family-workspace-stat-copy">Category-7 sites ({ff.method})</span>
            </div>
            <div className="space-y-1">
              {ff.low_confidence && (
                <span className="table-chip" title="Few sites or a wide confidence interval">
                  Low confidence
                </span>
              )}
              {ff.ff_external != null && (
                <span className="table-chip">External FF {pct(ff.ff_external)}</span>
              )}
              {ff.disagreement && (
                <span className="table-chip" title="Computed and external FF disagree">
                  FF disagreement
                </span>
              )}
            </div>
          </div>
        ) : (
          <p className="table-subtle">Loading fetal fraction…</p>
        )}
      </section>

      <section className="surface-card space-y-2" aria-label="Filter funnel">
        <h2 className="section-title">Variant filtering</h2>
        {summary ? (
          <div className="family-workspace-summary">
            {FILTER_STEPS.map((step) => (
              <div className="family-workspace-stat" key={step.key}>
                <span className="family-workspace-stat-value">
                  {summary.filter_counts[step.key] ?? 0}
                </span>
                <span className="family-workspace-stat-copy">{step.label}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="table-subtle">Loading filter counts…</p>
        )}
      </section>

      <section className="surface-card space-y-2" aria-label="Category counts">
        <h2 className="section-title">Maternal/fetal categories</h2>
        {summary ? (
          <div className="data-table-shell overflow-x-auto">
            <table className="analysis-table">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Category</th>
                  <th scope="col">Variants</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(CATEGORY_LABELS).map((key) => {
                  const categoryNumber = Number(key);
                  return (
                    <tr key={key}>
                      <td>{categoryNumber}</td>
                      <td>{CATEGORY_LABELS[categoryNumber]}</td>
                      <td>{summary.category_counts[key] ?? 0}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="table-subtle">Loading category counts…</p>
        )}
      </section>

      <section className="surface-card space-y-2" aria-label="On-target coverage">
        <h2 className="section-title">On-target coverage</h2>
        {coverage ? (
          coverage.target_region_count === 0 ? (
            <p className="table-subtle">
              No target regions — set a family ROI or gene panel to report coverage.
            </p>
          ) : (
            <>
              <div className="family-workspace-summary">
                <div className="family-workspace-stat">
                  <span className="family-workspace-stat-value">
                    {depth(coverage.overall_median_on_target)}
                  </span>
                  <span className="family-workspace-stat-copy">
                    Median on-target ({coverage.target_region_count} region
                    {coverage.target_region_count === 1 ? '' : 's'})
                  </span>
                </div>
              </div>
              {coverage.per_region.length > 0 && (
                <div className="data-table-shell overflow-x-auto">
                  <table className="analysis-table">
                    <thead>
                      <tr>
                        <th scope="col">Region</th>
                        <th scope="col">Location</th>
                        <th scope="col">Median coverage</th>
                        <th scope="col">Covered / target bases</th>
                      </tr>
                    </thead>
                    <tbody>
                      {coverage.per_region.map((region) => (
                        <tr key={`${region.label}-${region.chr}-${region.start}`}>
                          <td>{region.label}</td>
                          <td>
                            {region.chr}:{region.start}-{region.end}
                          </td>
                          <td>{depth(region.median_coverage)}</td>
                          <td>
                            {region.covered_bases} / {region.target_bases}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )
        ) : (
          <p className="table-subtle">Loading coverage…</p>
        )}
      </section>

      <section className="surface-card space-y-4" aria-label="Classified variants">
        <h2 className="section-title">Classified variants</h2>
        <div className="family-repeat-toolbar">
          <label className="family-repeat-filter-field">
            Gene
            <input
              type="text"
              value={gene}
              onChange={(event) => onFilterChange(setGene)(event.target.value)}
              placeholder="e.g. BRCA1"
            />
          </label>
          <label className="family-repeat-filter-field">
            Inheritance
            <select
              value={inheritance}
              onChange={(event) => onFilterChange(setInheritance)(event.target.value)}
            >
              {INHERITANCE_PRESETS.map((preset) => (
                <option key={preset.value} value={preset.value}>
                  {preset.label}
                </option>
              ))}
            </select>
          </label>
          <label className="family-repeat-filter-field">
            Category
            <select
              value={category}
              onChange={(event) => onFilterChange(setCategory)(event.target.value)}
            >
              <option value="">All categories</option>
              {Object.keys(CATEGORY_LABELS).map((key) => (
                <option key={key} value={key}>
                  {key} — {CATEGORY_LABELS[Number(key)]}
                </option>
              ))}
            </select>
          </label>
          <label className="family-repeat-filter-field">
            Min confidence
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={minConfidence}
              onChange={(event) => onFilterChange(setMinConfidence)(event.target.value)}
              placeholder="0.00"
            />
          </label>
        </div>

        <div className="data-table-shell overflow-x-auto">
          <table className="analysis-table">
            <thead>
              <tr>
                <th scope="col">Variant</th>
                <th scope="col">Gene</th>
                <th scope="col">Consequence</th>
                <th scope="col">Category</th>
                <th scope="col">Maternal</th>
                <th scope="col">Fetal inheritance</th>
                <th scope="col">VAF (obs / exp)</th>
                <th scope="col">Confidence</th>
                <th scope="col">Flags</th>
              </tr>
            </thead>
            <tbody>
              {(variantPage?.variants ?? []).map((variant) => (
                <tr key={variant.variant_id}>
                  <td>
                    {variant.chr}:{variant.pos} {variant.ref}&gt;{variant.alt}
                  </td>
                  <td>{variant.gene ?? '—'}</td>
                  <td>{variant.consequence ?? '—'}</td>
                  <td>
                    {variant.category != null
                      ? `${variant.category} — ${variant.category_label}`
                      : 'Undetermined'}
                  </td>
                  <td>{variant.maternal_state}</td>
                  <td>{variant.fetal_inheritance}</td>
                  <td>
                    {pct(variant.observed_vaf)} / {pct(variant.expected_vaf)}
                  </td>
                  <td>{variant.confidence.toFixed(2)}</td>
                  <td>{variant.flags.length ? variant.flags.join(', ') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {totalVariants === 0 && !variantsFetching && (
          <p className="table-subtle">No classified variants match the current filters.</p>
        )}

        <div className="family-repeat-toolbar">
          <span className="family-repeat-filter-count">
            {totalVariants} variant{totalVariants === 1 ? '' : 's'} · page {page} of {pageCount}
          </span>
          <button
            type="button"
            className="button-secondary"
            disabled={page <= 1}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            Previous
          </button>
          <button
            type="button"
            className="button-secondary"
            disabled={page >= pageCount}
            onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
          >
            Next
          </button>
        </div>
      </section>
    </div>
  );
};

export default FamilyNiptPage;

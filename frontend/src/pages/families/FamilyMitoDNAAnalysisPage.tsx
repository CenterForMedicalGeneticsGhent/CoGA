import React, { useCallback, useMemo, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../lib/api';
import type {
  ApiFamilyMitoDNAAnalysis,
  ApiFamilyRecord,
  ApiMitoDNASample,
  ApiMitoDNAVariant,
  ApiMitoDNAVariantSampleCall,
} from '../../lib/apiTypes';
import Pedigree from '../../components/visualizations/Pedigree';
import PageState from '../../components/PageState';
import { sortFamilyMembersProbandFirst } from '../../lib/familyMembers';
import { formatResolvedReferenceLabel, useFamilyReference } from '../../lib/reference';

interface PedRow {
  fid: string;
  iid: string;
  pid: string;
  mid: string;
  sex: string;
  phen: string;
}

const parsePedigree = (pedigree?: string | null): PedRow[] => {
  if (!pedigree) return [];
  return pedigree
    .split('\n')
    .filter((line) => line.trim())
    .map((line) => {
      const [fid, iid, pid, mid, sex, phen] = line.trim().split(/\s+/);
      return { fid, iid, pid, mid, sex, phen };
    });
};

const formatPercent = (value?: number | null, digits = 1): string =>
  value == null
    ? 'n/a'
    : `${(value * 100).toLocaleString(undefined, {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      })}%`;

const formatNumber = (value?: number | null, digits = 0): string =>
  value == null
    ? 'n/a'
    : value.toLocaleString(undefined, {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });

const formatDepth = (value?: number | null): string =>
  value == null ? 'n/a' : `${formatNumber(value, 1)}x`;

const significanceLabel = (status: ApiMitoDNAVariant['annotation']['clinical_significance']) => {
  switch (status) {
    case 'likely_pathogenic':
      return 'Likely pathogenic';
    case 'likely_benign':
      return 'Likely benign';
    case 'polymorphism':
      return 'Polymorphism';
    case 'reported':
      return 'Reported';
    case 'uncertain':
      return 'Uncertain';
    case 'pathogenic':
      return 'Pathogenic';
    case 'benign':
      return 'Benign';
    default:
      return 'Unknown';
  }
};

const zygosityLabel = (zygosity: ApiMitoDNAVariantSampleCall['zygosity']) => {
  switch (zygosity) {
    case 'homoplasmic':
      return 'Homoplasmic';
    case 'heteroplasmic':
      return 'Heteroplasmic';
    case 'low_level':
      return 'Low-level';
    case 'reference':
      return 'Reference';
    case 'no_call':
      return 'No call';
    default:
      return 'Unknown';
  }
};

const transmissionLabel = (status: ApiMitoDNAVariant['maternal_transmission']) => {
  switch (status) {
    case 'maternal_shared':
      return 'Maternal transmission';
    case 'maternal_not_observed':
      return 'Not seen in mother';
    case 'maternal_only':
      return 'Mother only';
    case 'father_only':
      return 'Father only';
    case 'family_private':
      return 'Family private';
    case 'no_alt_calls':
      return 'No alternate calls';
    default:
      return 'Unknown';
  }
};

const hasAltCall = (call?: ApiMitoDNAVariantSampleCall): boolean =>
  Boolean(call && ['homoplasmic', 'heteroplasmic', 'low_level'].includes(call.zygosity));

const hasHeteroplasmicCall = (variant: ApiMitoDNAVariant): boolean =>
  Object.values(variant.calls).some((call) => call.zygosity === 'heteroplasmic' || call.zygosity === 'low_level');

const hasHomoplasmicCall = (variant: ApiMitoDNAVariant): boolean =>
  Object.values(variant.calls).some((call) => call.zygosity === 'homoplasmic');

const isClinicalVariant = (variant: ApiMitoDNAVariant): boolean =>
  ['pathogenic', 'likely_pathogenic', 'reported', 'uncertain'].includes(
    variant.annotation.clinical_significance,
  ) || variant.annotation.disorders.length > 0;

const orderedByFamilyRole = (samples: ApiMitoDNASample[]): ApiMitoDNASample[] => {
  const memberLike = samples.map((sample) => ({
    sample_id: sample.sample_id,
    role: sample.role || 'relative',
    affected: Boolean(sample.affected),
    sex: sample.sex || 'und',
  }));
  const ordered = sortFamilyMembersProbandFirst(memberLike);
  const rank = new Map(ordered.map((member, index) => [member.sample_id, index]));
  return [...samples].sort(
    (left, right) => (rank.get(left.sample_id) ?? 999) - (rank.get(right.sample_id) ?? 999),
  );
};

const variantMatchesSearch = (variant: ApiMitoDNAVariant, query: string): boolean => {
  if (!query) return true;
  const haystack = [
    variant.label,
    variant.variant_id,
    variant.rsid,
    variant.annotation.gene,
    variant.annotation.region,
    variant.annotation.consequence,
    significanceLabel(variant.annotation.clinical_significance),
    ...variant.annotation.disorders,
    ...variant.annotation.polymorphism_notes,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return haystack.includes(query);
};

const VariantCallChip: React.FC<{
  call?: ApiMitoDNAVariantSampleCall;
  sample: ApiMitoDNASample;
}> = ({ call, sample }) => (
  <div
    className={`family-mtdna-call family-mtdna-call--${call?.zygosity || 'missing'}${
      hasAltCall(call) ? ' family-mtdna-call--alt' : ''
    }`}
  >
    <div className="family-mtdna-call-head">
      <strong>{sample.sample_id}</strong>
      <span>{sample.role || 'relative'}</span>
    </div>
    {call ? (
      <>
        <div className="family-mtdna-call-state">
          <span>{zygosityLabel(call.zygosity)}</span>
          <strong>{call.display}</strong>
        </div>
        <div className="table-subtle">
          DP {formatNumber(call.depth)} · AD {formatNumber(call.alt_depth)}
        </div>
      </>
    ) : (
      <span className="table-subtle">No data</span>
    )}
  </div>
);

const SampleSummaryCard: React.FC<{ sample: ApiMitoDNASample }> = ({ sample }) => (
  <div className={`family-mtdna-sample-card family-mtdna-sample-card--${sample.qc.status}`}>
    <div className="family-mtdna-sample-card-head">
      <div>
        <strong>{sample.sample_id}</strong>
        <div className="table-subtle">{sample.role || 'relative'}</div>
      </div>
      <span className={`table-chip family-mtdna-qc-chip family-mtdna-qc-chip--${sample.qc.status}`}>
        {sample.qc.status}
      </span>
    </div>
    <div className="family-mtdna-sample-metrics">
      <span>
        Haplogroup <strong>{sample.haplogroup || 'n/a'}</strong>
      </span>
      <span>
        Mean depth <strong>{formatDepth(sample.coverage.mean_depth)}</strong>
      </span>
      <span>
        Breadth <strong>{formatPercent(sample.coverage.breadth, 0)}</strong>
      </span>
      {sample.qc.contamination != null && (
        <span>
          Contam. <strong>{formatPercent(sample.qc.contamination, 2)}</strong>
        </span>
      )}
    </div>
    {sample.qc.notes.length > 0 && (
      <div className="family-mtdna-qc-notes">{sample.qc.notes.slice(0, 2).join(' · ')}</div>
    )}
  </div>
);

const FamilyMitoDNAAnalysisPage: React.FC = () => {
  const { familyId } = useParams<{ familyId: string }>();
  const location = useLocation();
  const projectIdParam = useMemo(
    () => new URLSearchParams(location.search).get('project_id') || undefined,
    [location.search],
  );
  const [searchText, setSearchText] = useState('');
  const [scope, setScope] = useState<'all' | 'clinical' | 'heteroplasmic' | 'homoplasmic' | 'maternal_review'>('all');
  const [copiedMitomapVariant, setCopiedMitomapVariant] = useState<string | null>(null);

  const { data: family, isLoading: familyLoading } = useQuery<ApiFamilyRecord>({
    queryKey: ['family', familyId],
    queryFn: async () => {
      const response = await api.get(`/families/${familyId}`);
      return response.data as ApiFamilyRecord;
    },
  });

  const {
    assemblyName,
    assemblyVersion,
    projectId: resolvedProjectId,
    isLoading: referenceLoading,
  } = useFamilyReference(family?.projects, projectIdParam);

  const { data: mtDNA, isLoading: mtDNALoading } = useQuery<ApiFamilyMitoDNAAnalysis>({
    queryKey: ['family', familyId, 'mitochondrial-dna', resolvedProjectId],
    queryFn: async () => {
      const response = await api.get(`/families/${familyId}/mitochondrial-dna`, {
        params: resolvedProjectId ? { project_id: resolvedProjectId } : undefined,
      });
      return response.data as ApiFamilyMitoDNAAnalysis;
    },
    enabled: Boolean(familyId && (!family?.projects?.length || !referenceLoading)),
  });

  const pedRows = useMemo(() => parsePedigree(family?.pedigree), [family?.pedigree]);
  const referenceLabel = formatResolvedReferenceLabel(
    { assemblyName, assemblyVersion },
    'Not linked',
  );
  const orderedSamples = useMemo(() => orderedByFamilyRole(mtDNA?.samples || []), [mtDNA?.samples]);
  const mothers = orderedSamples.filter((sample) => sample.role === 'mother');
  const fathers = orderedSamples.filter((sample) => sample.role === 'father');
  const maternalLine = orderedSamples.filter((sample) => sample.role !== 'father');
  const children = maternalLine.filter((sample) => sample.role !== 'mother');

  const filteredVariants = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    return (mtDNA?.variants || []).filter((variant) => {
      if (!variantMatchesSearch(variant, query)) return false;
      if (scope === 'clinical') return isClinicalVariant(variant);
      if (scope === 'heteroplasmic') return hasHeteroplasmicCall(variant);
      if (scope === 'homoplasmic') return hasHomoplasmicCall(variant);
      if (scope === 'maternal_review') {
        return ['maternal_not_observed', 'father_only', 'family_private'].includes(
          variant.maternal_transmission,
        );
      }
      return true;
    });
  }, [mtDNA?.variants, scope, searchText]);

  const heteroplasmicCount = useMemo(
    () => (mtDNA?.variants || []).filter(hasHeteroplasmicCall).length,
    [mtDNA?.variants],
  );
  const homoplasmicCount = useMemo(
    () => (mtDNA?.variants || []).filter(hasHomoplasmicCall).length,
    [mtDNA?.variants],
  );
  const clinicalCount = useMemo(
    () => (mtDNA?.variants || []).filter(isClinicalVariant).length,
    [mtDNA?.variants],
  );
  const qcWarningCount = useMemo(
    () => (mtDNA?.samples || []).filter((sample) => sample.qc.status === 'warning' || sample.qc.status === 'fail').length,
    [mtDNA?.samples],
  );
  const openMitomapVariant = useCallback((variant: ApiMitoDNAVariant) => {
    const query = variant.annotation.mitomap_query || variant.label;
    if (navigator.clipboard?.writeText) {
      void navigator.clipboard
        .writeText(query)
        .then(() => {
          setCopiedMitomapVariant(query);
          window.setTimeout(
            () => setCopiedMitomapVariant((current) => (current === query ? null : current)),
            2000,
          );
        })
        .catch(() => undefined);
    }
    window.open(variant.annotation.mitomap_url, '_blank', 'noopener,noreferrer');
  }, []);

  if (familyLoading || mtDNALoading || (family?.projects?.length && referenceLoading)) {
    return (
      <PageState
        kicker="mtDNA"
        title="Loading mtDNA analysis"
        message="Preparing mitochondrial variant calls, haplogroups, coverage and QC."
      />
    );
  }

  if (!family || !mtDNA) {
    return (
      <PageState
        kicker="mtDNA"
        title="Family not found"
        message="This mtDNA workspace could not resolve the requested family."
      />
    );
  }

  return (
    <div className="page-shell family-mtdna-page space-y-6">
      <section className="surface-card page-top-card">
        <div className={`page-top-card-grid${pedRows.length ? ' page-top-card-grid--with-visual' : ''}`}>
          <div className="page-top-card-copy">
            <div className="space-y-1">
              <p className="page-kicker">mtDNA analysis</p>
              <h1 className="catalog-card-title">Family {family.family_id}</h1>
            </div>
            <div className="family-workspace-summary">
              <div className="family-workspace-stat">
                <span className="stat-label">Members</span>
                <strong className="family-workspace-stat-value">{orderedSamples.length}</strong>
              </div>
              <div className="family-workspace-stat">
                <span className="stat-label">Assembly</span>
                <strong className="family-workspace-stat-copy">{referenceLabel}</strong>
              </div>
              <div className="family-workspace-stat">
                <span className="stat-label">MT variants</span>
                <strong className="family-workspace-stat-value">{mtDNA.variants.length}</strong>
              </div>
              <div className="family-workspace-stat">
                <span className="stat-label">Heteroplasmic</span>
                <strong className="family-workspace-stat-value">{heteroplasmicCount}</strong>
              </div>
              <div className="family-workspace-stat">
                <span className="stat-label">QC warnings</span>
                <strong className="family-workspace-stat-value">{qcWarningCount}</strong>
              </div>
            </div>
          </div>
          {pedRows.length > 0 && (
            <div className="page-top-card-visual">
              <div className="page-top-card-pedigree family-workspace-pedigree">
                <p className="stat-label">Pedigree</p>
                <div className="mono-panel overflow-x-auto !bg-[rgba(255,255,255,0.92)]">
                  <Pedigree
                    rows={pedRows}
                    members={family.members}
                    relationships={family.relationships}
                    inheritanceModel={(family.metadata?.pgt as { inheritance_model?: string } | undefined)?.inheritance_model}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="surface-card space-y-4">
        <div className="page-header">
          <div className="space-y-1">
            <h2 className="section-title">Family mitochondrial summary</h2>
            <p className="catalog-card-copy">
              Mothers and children are grouped together; fathers are shown separately from the maternal line.
            </p>
          </div>
          <Link to={`/families/${family.family_id}`} className="button-secondary hover:no-underline">
            Back to family workspace
          </Link>
        </div>

        <div className="family-mtdna-sample-layout">
          <div className="family-mtdna-sample-group">
            <div className="family-mtdna-sample-group-head">
              <span>Maternal line</span>
              <strong>
                {mothers.length} mother{mothers.length === 1 ? '' : 's'} · {children.length} child sample{children.length === 1 ? '' : 's'}
              </strong>
            </div>
            <div className="family-mtdna-sample-grid">
              {maternalLine.map((sample) => (
                <SampleSummaryCard key={sample.sample_id} sample={sample} />
              ))}
              {maternalLine.length === 0 && (
                <p className="table-subtle">No maternal-line samples are available.</p>
              )}
            </div>
          </div>
          <div className="family-mtdna-sample-group family-mtdna-sample-group--father">
            <div className="family-mtdna-sample-group-head">
              <span>Father</span>
              <strong>{fathers.length || 'No'} sample{fathers.length === 1 ? '' : 's'}</strong>
            </div>
            <div className="family-mtdna-sample-grid">
              {fathers.map((sample) => (
                <SampleSummaryCard key={sample.sample_id} sample={sample} />
              ))}
              {fathers.length === 0 && <p className="table-subtle">No father sample is available.</p>}
            </div>
          </div>
        </div>

        {mtDNA.qc_notes.length > 0 && (
          <div className="family-mtdna-qc-banner">
            {mtDNA.qc_notes.map((note) => (
              <span key={note}>{note}</span>
            ))}
          </div>
        )}
      </section>

      <section className="surface-card space-y-4">
        <div className="page-header">
          <div className="space-y-1">
            <h2 className="section-title">Mitochondrial variants</h2>
            <p className="catalog-card-copy">
              Homoplasmy starts at {formatPercent(mtDNA.homoplasmy_threshold, 0)}; heteroplasmy is shown from {formatPercent(mtDNA.heteroplasmy_threshold, 0)}.
            </p>
          </div>
        </div>

        <div className="family-mtdna-toolbar">
          <label className="family-mtdna-filter-field" htmlFor="mtdna-search">
            <span>Search</span>
            <input
              id="mtdna-search"
              type="search"
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="Variant, gene or disorder"
            />
          </label>
          <div className="family-mtdna-scope-toggle" aria-label="mtDNA variant scope">
            <button
              type="button"
              className={scope === 'all' ? 'is-active' : ''}
              onClick={() => setScope('all')}
            >
              All
            </button>
            <button
              type="button"
              className={scope === 'clinical' ? 'is-active' : ''}
              onClick={() => setScope('clinical')}
            >
              Clinical
            </button>
            <button
              type="button"
              className={scope === 'heteroplasmic' ? 'is-active' : ''}
              onClick={() => setScope('heteroplasmic')}
            >
              Heteroplasmic
            </button>
            <button
              type="button"
              className={scope === 'homoplasmic' ? 'is-active' : ''}
              onClick={() => setScope('homoplasmic')}
            >
              Homoplasmic
            </button>
            <button
              type="button"
              className={scope === 'maternal_review' ? 'is-active' : ''}
              onClick={() => setScope('maternal_review')}
            >
              Maternal review
            </button>
          </div>
          <div className="family-mtdna-filter-count">
            {filteredVariants.length} of {mtDNA.variants.length} variants · {clinicalCount} clinical · {homoplasmicCount} homoplasmic
          </div>
        </div>

        <div className="data-table-shell overflow-x-auto">
          <table className="analysis-table family-mtdna-table">
            <thead>
              <tr>
                <th>Variant</th>
                <th>Annotation</th>
                <th>Transmission</th>
                <th>Mother(s) and children</th>
                <th>Father</th>
              </tr>
            </thead>
            <tbody>
              {filteredVariants.map((variant) => (
                <tr
                  key={variant.variant_id}
                  className={`family-mtdna-row family-mtdna-row--${variant.annotation.clinical_significance}`}
                >
                  <td>
                    <div className="family-mtdna-variant-head">
                      <div>
                        <div className="font-semibold">{variant.label}</div>
                        <div className="table-subtle">
                          MT:{variant.position.toLocaleString()} · {variant.type}
                        </div>
                      </div>
                      <span className={`table-chip family-mtdna-significance family-mtdna-significance--${variant.annotation.clinical_significance}`}>
                        {significanceLabel(variant.annotation.clinical_significance)}
                      </span>
                    </div>
                    {variant.rsid && <div className="table-subtle">{variant.rsid}</div>}
                    <div className="family-mtdna-links">
                      <button
                        type="button"
                        className="table-link"
                        onClick={() => openMitomapVariant(variant)}
                        aria-label={`Open MITOMAP for ${variant.annotation.mitomap_query || variant.label}`}
                      >
                        MITOMAP
                      </button>
                      <Link
                        to={`/families/${family.family_id}/chromosome/MT?start=${Math.max(0, variant.position - 100)}&end=${variant.position + 100}${
                          resolvedProjectId ? `&project_id=${resolvedProjectId}` : ''
                        }`}
                      >
                        Chromosome view
                      </Link>
                      {copiedMitomapVariant === (variant.annotation.mitomap_query || variant.label) && (
                        <span className="family-mtdna-copy-note" aria-live="polite">
                          Copied
                        </span>
                      )}
                    </div>
                  </td>
                  <td>
                    <div className="family-mtdna-annotation">
                      <strong>{variant.annotation.gene || variant.annotation.region}</strong>
                      <span>{variant.annotation.category || 'mitochondrial genome'}</span>
                      {variant.annotation.consequence && <span>{variant.annotation.consequence}</span>}
                      {variant.annotation.disorders.length > 0 && (
                        <div className="family-mtdna-disorders">
                          {variant.annotation.disorders.map((disorder) => (
                            <span key={disorder}>{disorder}</span>
                          ))}
                        </div>
                      )}
                      {variant.annotation.polymorphism_notes.length > 0 && (
                        <div className="family-mtdna-polymorphism">
                          {variant.annotation.polymorphism_notes.slice(0, 2).join(' · ')}
                        </div>
                      )}
                    </div>
                  </td>
                  <td>
                    <span className={`table-chip family-mtdna-transmission family-mtdna-transmission--${variant.maternal_transmission}`}>
                      {transmissionLabel(variant.maternal_transmission)}
                    </span>
                  </td>
                  <td>
                    <div className="family-mtdna-call-grid">
                      {maternalLine.map((sample) => (
                        <VariantCallChip
                          key={sample.sample_id}
                          sample={sample}
                          call={variant.calls[sample.sample_id]}
                        />
                      ))}
                    </div>
                  </td>
                  <td>
                    <div className="family-mtdna-call-grid family-mtdna-call-grid--father">
                      {fathers.map((sample) => (
                        <VariantCallChip
                          key={sample.sample_id}
                          sample={sample}
                          call={variant.calls[sample.sample_id]}
                        />
                      ))}
                      {fathers.length === 0 && <span className="table-subtle">No father sample</span>}
                    </div>
                  </td>
                </tr>
              ))}
              {filteredVariants.length === 0 && (
                <tr>
                  <td colSpan={5} className="table-subtle">
                    {mtDNA.variants.length
                      ? 'No mtDNA variants match the selected filters.'
                      : 'No MT/chrM small variants are loaded for this family.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export default FamilyMitoDNAAnalysisPage;

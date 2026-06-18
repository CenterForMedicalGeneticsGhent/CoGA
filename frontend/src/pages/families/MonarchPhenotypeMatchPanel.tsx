import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import api from '../../lib/api';

interface PhenotypeMatchResult {
  rank: number;
  score?: number | null;
  id: string;
  name: string;
  category?: string | null;
  symbol?: string | null;
  gene_in_platform?: boolean;
}

interface FamilyPhenotypeMatch {
  group: string;
  sample_id?: string | null;
  query_hpo_ids: string[];
  results: PhenotypeMatchResult[];
  source: string;
}

type Props = {
  familyId?: string;
  projectId?: string;
};

const buildGeneHref = (symbol: string, familyId?: string, projectId?: string) => {
  const params = new URLSearchParams({ gene: symbol });
  if (familyId) params.set('family_id', familyId);
  if (projectId) params.set('project_id', projectId);
  return `/genes?${params.toString()}`;
};

export default function MonarchPhenotypeMatchPanel({ familyId, projectId }: Props) {
  const [enabled, setEnabled] = useState(false);

  const { data, isFetching, isError } = useQuery<FamilyPhenotypeMatch>({
    queryKey: ['family', familyId, 'phenotype-match'],
    enabled: Boolean(familyId) && enabled,
    staleTime: 1000 * 60 * 30,
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}/phenotype-match`, {
        params: { group: 'Human Genes', limit: 20 },
      });
      return res.data as FamilyPhenotypeMatch;
    },
  });

  const hasRun = enabled && !isFetching && !isError && data !== undefined;

  return (
    <section className="surface-card space-y-3">
      <div className="family-workspace-card-head">
        <div className="space-y-1">
          <h2 className="section-title">Phenotype match (Monarch)</h2>
          <p className="dashboard-link-note">
            Rank candidate genes by phenotypic similarity to this family&apos;s observed
            HPO terms, via the Monarch Initiative semantic-similarity service.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setEnabled(true)}
          disabled={isFetching}
        >
          {isFetching ? 'Matching…' : hasRun ? 'Re-run match' : 'Find candidate genes'}
        </button>
      </div>

      {isError ? (
        <p className="dashboard-link-note">
          Monarch phenotype matching is currently unavailable. Try again later.
        </p>
      ) : null}

      {hasRun && data ? (
        data.results.length === 0 ? (
          <p className="dashboard-link-note">
            {data.query_hpo_ids.length === 0
              ? 'No present HPO phenotypes recorded for this family yet — add observed phenotypes to rank candidate genes.'
              : 'No phenotype matches were returned.'}
          </p>
        ) : (
          <>
            <p className="dashboard-link-note">
              Ranked from {data.query_hpo_ids.length} observed phenotype
              {data.query_hpo_ids.length === 1 ? '' : 's'}.
            </p>
            <ol className="gene-compact-list">
              {data.results.map((result) => (
                <li key={result.id}>
                  <span className="table-chip">#{result.rank}</span>{' '}
                  {result.symbol && result.gene_in_platform ? (
                    <Link
                      className="gene-compact-link"
                      to={buildGeneHref(result.symbol, familyId, projectId)}
                    >
                      {result.symbol}
                    </Link>
                  ) : (
                    <span>{result.name}</span>
                  )}
                  <span className="gene-compact-list-meta">
                    {[
                      typeof result.score === 'number' ? `score ${result.score.toFixed(2)}` : null,
                      result.symbol && !result.gene_in_platform ? 'not in platform' : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </li>
              ))}
            </ol>
          </>
        )
      ) : null}
    </section>
  );
}

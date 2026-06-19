import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import PageState from '../../components/PageState';
import api from '../../lib/api';
import { getErrorMessage } from '../../lib/errorMessage';
import { formatCount } from './dataManagementTypes';

interface MonarchStatus {
  release_version?: string | null;
  gene_disease_pairs: number;
  genes: number;
  diseases: number;
  causal_pairs: number;
  disease_phenotype_pairs: number;
  phenotype_diseases: number;
  phenotypes: number;
  last_updated_at?: string | null;
}

interface MonarchRefreshSummary {
  release_version?: string | null;
  files_loaded: number;
  gene_disease_pairs: number;
  genes: number;
  diseases: number;
  causal_pairs: number;
  disease_phenotype_pairs: number;
  phenotype_diseases: number;
  phenotypes: number;
  excluded_phenotype_pairs: number;
  completed_at: string;
  duration_seconds: number;
}

const formatTimestamp = (value?: string | null) => {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
};

const MonarchDataAdminPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<{ tone: 'success' | 'error'; message: string } | null>(null);

  const { data, isLoading, error } = useQuery<MonarchStatus>({
    queryKey: ['admin', 'monarch-status'],
    queryFn: async () => {
      const response = await api.get('/admin/monarch/status');
      return response.data as MonarchStatus;
    },
    retry: false,
  });

  const refreshMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/admin/monarch/refresh');
      return response.data as MonarchRefreshSummary;
    },
    onSuccess: async (summary) => {
      setStatus({
        tone: 'success',
        message: `Updated to Monarch release ${summary.release_version ?? 'latest'} — `
          + `${formatCount(summary.gene_disease_pairs)} gene–disease and `
          + `${formatCount(summary.disease_phenotype_pairs)} disease–phenotype pairs `
          + `in ${summary.duration_seconds.toFixed(1)}s.`,
      });
      await queryClient.invalidateQueries({ queryKey: ['admin', 'monarch-status'] });
    },
    onError: (mutationError) => {
      setStatus({
        tone: 'error',
        message: getErrorMessage(mutationError, 'Could not update the Monarch knowledgebase.'),
      });
    },
  });

  if (isLoading) {
    return (
      <PageState
        kicker="Administration"
        title="Loading Monarch data"
        message="Reading the currently loaded Monarch release and table sizes."
      />
    );
  }

  if (error || !data) {
    return (
      <PageState
        kicker="Administration"
        title="Could not load Monarch data"
        message={getErrorMessage(error, 'The Monarch knowledgebase status could not be loaded.')}
      />
    );
  }

  const isEmpty = data.gene_disease_pairs === 0 && data.disease_phenotype_pairs === 0;

  return (
    <div className="page-shell admin-compact space-y-5">
      <section className="surface-card page-top-card">
        <div className="page-header">
          <div className="space-y-1">
            <p className="page-kicker">Administration</p>
            <h1 className="catalog-card-title">Monarch data</h1>
            <p className="catalog-card-copy">
              Gene–disease and disease–phenotype associations from the Monarch Initiative
              knowledge graph. Updating downloads the latest monthly Monarch release and
              replaces both knowledgebase tables in a single transaction.
            </p>
          </div>
          <div className="surface-card-muted gene-profile-status">
            <span className="gene-profile-status-label">Loaded release</span>
            <strong>{data.release_version ?? '—'}</strong>
            <span className="dashboard-link-note">
              Last updated {formatTimestamp(data.last_updated_at)}
            </span>
          </div>
        </div>

        <div className="gene-sync-summary-grid">
          <div className="gene-profile-stat">
            <span className="gene-profile-stat-label">Gene–disease pairs</span>
            <strong>{formatCount(data.gene_disease_pairs)}</strong>
          </div>
          <div className="gene-profile-stat">
            <span className="gene-profile-stat-label">Genes</span>
            <strong>{formatCount(data.genes)}</strong>
          </div>
          <div className="gene-profile-stat">
            <span className="gene-profile-stat-label">Diseases</span>
            <strong>{formatCount(data.diseases)}</strong>
          </div>
          <div className="gene-profile-stat">
            <span className="gene-profile-stat-label">Causal pairs</span>
            <strong>{formatCount(data.causal_pairs)}</strong>
          </div>
          <div className="gene-profile-stat">
            <span className="gene-profile-stat-label">Disease–phenotype pairs</span>
            <strong>{formatCount(data.disease_phenotype_pairs)}</strong>
          </div>
          <div className="gene-profile-stat">
            <span className="gene-profile-stat-label">Phenotype diseases</span>
            <strong>{formatCount(data.phenotype_diseases)}</strong>
          </div>
          <div className="gene-profile-stat">
            <span className="gene-profile-stat-label">Phenotypes</span>
            <strong>{formatCount(data.phenotypes)}</strong>
          </div>
        </div>

        <div className="gene-sync-action-grid">
          <article className="surface-card-muted gene-sync-action-panel">
            <p className="section-title">Update Monarch knowledgebase</p>
            <p className="dashboard-link-note">
              Downloads the latest Monarch release and atomically replaces the gene–disease and
              disease–phenotype tables. Runs inline and usually completes in a few seconds.
            </p>
            <div className="inline-actions">
              <button
                type="button"
                className="button-secondary"
                onClick={() => {
                  setStatus(null);
                  refreshMutation.mutate();
                }}
                disabled={refreshMutation.isPending}
              >
                {refreshMutation.isPending
                  ? 'Updating…'
                  : isEmpty
                    ? 'Import Monarch data'
                    : 'Update Monarch data'}
              </button>
            </div>
          </article>
        </div>

        {status ? (
          <div className={`status-note ${status.tone === 'error' ? 'status-note--error' : 'status-note--success'}`}>
            {status.message}
          </div>
        ) : null}
      </section>
    </div>
  );
};

export default MonarchDataAdminPage;

import React from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../lib/api';
import type { ApiFamilyRecord } from '../../lib/apiTypes';
import PageState from '../../components/PageState';

const MONOGENIC_NIPT_ANALYSIS_TYPE = 'monogenic_nipt';

const FamilyNiptPage: React.FC = () => {
  const { familyId } = useParams<{ familyId: string }>();

  const { data, isLoading, isError } = useQuery<ApiFamilyRecord>({
    queryKey: ['family', familyId],
    enabled: Boolean(familyId),
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}`);
      return res.data as ApiFamilyRecord;
    },
  });

  if (isLoading) {
    return <PageState kicker="Monogenic NIPT" title="Loading family…" />;
  }

  if (isError || !data) {
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

  const isMonogenicNipt = data.metadata?.analysis_type === MONOGENIC_NIPT_ANALYSIS_TYPE;

  if (!isMonogenicNipt) {
    return (
      <PageState
        kicker="Monogenic NIPT"
        title="Not a monogenic NIPT family"
        message={`Family ${data.family_id} is not configured for monogenic NIPT analysis.`}
        action={
          <Link className="button-secondary" to={`/families/${data.family_id}`}>
            Back to family
          </Link>
        }
      />
    );
  }

  return (
    <div className="page-shell">
      <div className="surface-card space-y-2">
        <p className="page-kicker">Monogenic NIPT</p>
        <h1 className="page-state-title">Monogenic NIPT analysis — {data.family_id}</h1>
        <p className="page-state-copy">
          This family is configured for monogenic NIPT analysis. Fetal-fraction
          estimation, variant classification, and on-target coverage reporting are
          not available yet — upload the combined father + maternal-plasma cfDNA VCF
          to begin.
        </p>
        <div className="inline-actions">
          <Link className="form-button" to={`/families/${data.family_id}`}>
            Back to family overview
          </Link>
        </div>
      </div>
    </div>
  );
};

export default FamilyNiptPage;

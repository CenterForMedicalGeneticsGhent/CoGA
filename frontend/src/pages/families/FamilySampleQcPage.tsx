import React from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import api from '../../lib/api';
import PageState from '../../components/PageState';
import type {
  ApiSampleIntegrityMendelianCheck,
  ApiSampleIntegrityPaternityCheck,
  ApiSampleIntegrityQc,
  ApiSampleIntegrityRelatednessCheck,
  ApiSampleIntegritySexCheck,
  QcStatus,
} from '../../lib/apiTypes';

const STATUS_META: Record<QcStatus, { label: string; chip: string }> = {
  pass: { label: 'Pass', chip: 'table-chip table-chip--success' },
  warn: { label: 'Warning', chip: 'table-chip table-chip--warning' },
  fail: { label: 'Fail', chip: 'table-chip table-chip--critical' },
  skip: { label: 'Not run', chip: 'table-chip table-chip--neutral' },
};

const OVERALL_COPY: Record<QcStatus, string> = {
  pass: 'All sample-integrity checks passed. No swaps or mislabelled relationships detected.',
  warn: 'Some checks need attention — review the warnings before interpretation.',
  fail: 'A check failed. Resolve possible sample swaps or pedigree errors before interpretation.',
  skip: 'Sample-integrity QC could not run (no genotypes available).',
};

const StatusChip: React.FC<{ status: QcStatus }> = ({ status }) => (
  <span className={STATUS_META[status].chip}>{STATUS_META[status].label}</span>
);

const CheckRow: React.FC<{ status: QcStatus; title: string; message: string }> = ({
  status,
  title,
  message,
}) => (
  <div className="qc-check-row">
    <StatusChip status={status} />
    <div className="qc-check-body">
      <p className="qc-check-title">{title}</p>
      <p className="table-subtle">{message}</p>
    </div>
  </div>
);

const sexTitle = (c: ApiSampleIntegritySexCheck): string =>
  `${c.sample_id} — recorded ${c.recorded_sex || 'unknown'}, genotypes look ${c.inferred_sex}`;

const relatednessTitle = (c: ApiSampleIntegrityRelatednessCheck): string =>
  `${c.sample_a} ↔ ${c.sample_b} — expected ${c.expected_relationship}, observed ${c.inferred_relationship}`;

const mendelianTitle = (c: ApiSampleIntegrityMendelianCheck): string =>
  `${c.child} vs ${c.parents.join(' + ') || 'parent'} — ${(c.mendel_rate * 100).toFixed(2)}% errors`;

const paternityTitle = (c: ApiSampleIntegrityPaternityCheck): string =>
  `Father ${c.father} — ${c.cat7_transmitted} paternal-transmitted, ${c.cat8_absent} absent of ${c.informative_sites} sites`;

const FamilySampleQcPage: React.FC = () => {
  const { familyId } = useParams<{ familyId: string }>();

  const {
    data: qc,
    isLoading,
    isError,
  } = useQuery<ApiSampleIntegrityQc>({
    queryKey: ['family', familyId, 'sample-integrity-qc'],
    enabled: Boolean(familyId),
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}/qc/sample-integrity`);
      return res.data as ApiSampleIntegrityQc;
    },
  });

  if (!familyId) {
    return <PageState kicker="Sample QC" title="Family not specified" />;
  }

  if (isLoading) {
    return (
      <PageState
        kicker="Sample QC"
        title="Running sample-integrity checks"
        message="Estimating relatedness, Mendelian-error rate and genotype sex."
      />
    );
  }

  if (isError || !qc) {
    return (
      <PageState
        kicker="Sample QC"
        title="QC could not be computed"
        message="The genotypes for this family could not be analysed."
        action={
          <Link to={`/families/${familyId}`} className="button-secondary">
            Back to family
          </Link>
        }
      />
    );
  }

  return (
    <div className="page-shell space-y-6">
      <header className="surface-card report-header">
        <div className="space-y-1">
          <p className="page-kicker">Sample-integrity QC · {qc.application_label || qc.application}</p>
          <h1 className="page-state-title">Family {familyId}</h1>
          <p className="report-header-meta">
            {qc.genotype_source
              ? `${qc.genotype_source} genotypes · ${qc.autosomal_sites.toLocaleString()} autosomal sites`
              : 'cfDNA classification'}
          </p>
        </div>
        <div className="report-header-actions">
          <Link to={`/families/${familyId}`} className="button-secondary hover:no-underline">
            Back to family
          </Link>
        </div>
      </header>

      <section className={`surface-card qc-overall qc-overall--${qc.overall_status}`}>
        <div className="qc-overall-head">
          <StatusChip status={qc.overall_status} />
          <p className="report-paragraph">{OVERALL_COPY[qc.overall_status]}</p>
        </div>
        {qc.application_summary ? (
          <p className="table-subtle">{qc.application_summary}</p>
        ) : null}
        {qc.notes.length ? (
          <ul className="report-criteria-list">
            {qc.notes.map((note) => (
              <li key={note} className="table-subtle">
                {note}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      {qc.paternity_check ? (
        <section className="surface-card space-y-2">
          <h2 className="section-title">Paternity (cfDNA categories 7/8)</h2>
          <CheckRow
            status={qc.paternity_check.status}
            title={paternityTitle(qc.paternity_check)}
            message={qc.paternity_check.message}
          />
        </section>
      ) : null}

      {qc.fetal_sex_check ? (
        <section className="surface-card space-y-2">
          <h2 className="section-title">Fetal sex (paternal X transmission)</h2>
          <CheckRow
            status={qc.fetal_sex_check.status}
            title={`Fetus appears ${qc.fetal_sex_check.inferred_sex} — ${qc.fetal_sex_check.x_transmitted} paternal-X transmitted, ${qc.fetal_sex_check.x_not_transmitted} absent`}
            message={qc.fetal_sex_check.message}
          />
        </section>
      ) : null}

      {qc.sex_checks.length ? (
        <section className="surface-card space-y-2">
          <h2 className="section-title">Sex concordance</h2>
          {qc.sex_checks.map((check) => (
            <CheckRow
              key={check.sample_id}
              status={check.status}
              title={sexTitle(check)}
              message={check.message}
            />
          ))}
        </section>
      ) : null}

      {qc.relatedness_checks.length ? (
        <section className="surface-card space-y-2">
          <h2 className="section-title">
            {qc.application === 'pgt' ? 'Parentage (embryos ↔ parents)' : 'Relatedness vs pedigree'}
          </h2>
          {qc.relatedness_checks.map((check) => (
            <CheckRow
              key={`${check.sample_a}:${check.sample_b}`}
              status={check.status}
              title={relatednessTitle(check)}
              message={check.message}
            />
          ))}
        </section>
      ) : null}

      {qc.mendelian_checks.length ? (
        <section className="surface-card space-y-2">
          <h2 className="section-title">Mendelian-error rate</h2>
          {qc.mendelian_checks.map((check) => (
            <CheckRow
              key={check.child}
              status={check.status}
              title={mendelianTitle(check)}
              message={check.message}
            />
          ))}
        </section>
      ) : null}
    </div>
  );
};

export default FamilySampleQcPage;

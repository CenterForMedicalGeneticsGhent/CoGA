import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import api from '../../lib/api';
import type { ApiAnnotationManifest } from '../../lib/apiTypes';

/** Where the provenance came from — surfaced so a reviewer can judge its weight. */
const SOURCE_LABELS: Record<string, string> = {
  vcf_header: 'from VCF headers',
  manifest: 'from import manifest',
  manual: 'entered manually',
};

const COLLAPSED_COUNT = 6;

/**
 * Compact annotation-provenance summary: the tool/database versions a family's
 * data was built from (VEP, gnomAD, ClinVar, the variant callers, …), captured
 * from the VCF headers at import. Shown on the filter page so a reviewer always
 * sees which annotation versions they are filtering against. The full, frozen
 * record lives on the report ([[clinical-traceability]]).
 */
export default function AnnotationProvenanceSummary({ familyId }: { familyId: string }) {
  const [expanded, setExpanded] = useState(false);
  const { data } = useQuery<ApiAnnotationManifest>({
    queryKey: ['family', familyId, 'annotation-manifest'],
    enabled: Boolean(familyId),
    queryFn: async () =>
      (await api.get(`/families/${familyId}/annotation-manifest`)).data as ApiAnnotationManifest,
  });

  const modules = (data?.modules ?? []).filter((module) => module.version);
  if (!modules.length) {
    return null;
  }
  const shown = expanded ? modules : modules.slice(0, COLLAPSED_COUNT);
  const hidden = modules.length - shown.length;

  return (
    <footer
      className="surface-card annotation-provenance-footer"
      data-testid="annotation-provenance"
    >
      <span className="annotation-provenance-label">Annotation versions</span>
      {shown.map((module) => (
        <span
          key={module.key}
          className="badge-chip annotation-provenance-chip"
          title={module.detail ? `${module.label} — ${module.detail}` : module.label}
        >
          {module.label} <strong>{module.version}</strong>
        </span>
      ))}
      {hidden > 0 && (
        <button
          type="button"
          className="button-link annotation-provenance-toggle"
          onClick={() => setExpanded(true)}
        >
          +{hidden} more
        </button>
      )}
      {expanded && modules.length > COLLAPSED_COUNT && (
        <button
          type="button"
          className="button-link annotation-provenance-toggle"
          onClick={() => setExpanded(false)}
        >
          show less
        </button>
      )}
      {data?.source && (
        <span className="annotation-provenance-source">
          {SOURCE_LABELS[data.source] ?? data.source}
        </span>
      )}
    </footer>
  );
}

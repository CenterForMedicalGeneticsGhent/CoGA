import React, { useMemo, useState } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../lib/api';
import { cssVar } from '../../lib/colors';
import PageState from '../../components/PageState';
import type { ApiFamilyRecord } from '../../lib/apiTypes';

// Window padding either side of the ROI (the spec: ROI ± 1 Mb).
const ROI_FLANK = 1_000_000;
// Cap rendered columns so a dense window stays responsive; the rest is summarised.
const MAX_COLUMNS = 800;

// IGV-style nucleotide colours (match the haplotype track tooltip).
const NUCLEOTIDE_COLORS: Record<string, string> = {
  A: '#2e9e4f',
  C: '#2f6fe0',
  G: '#e8a33d',
  T: '#d6453d',
};

interface PhasedSite {
  pos: number;
  ref: string;
  alt: string;
  gts: string[]; // phased a|b per member, aligned to `samples` order
}
interface PhasedSample {
  sample: string;
  markers: { pos: number; hap1: number | null; hap2: number | null }[];
  reference?: boolean;
  qc?: { informative_sites: number; mendel_errors: number; mendel_rate: number } | null;
}
interface PhasedMarkerResponse {
  samples: PhasedSample[];
  sites: PhasedSite[];
  truncated?: boolean;
  covered?: [number, number] | null;
}
interface HapSegment {
  start: number;
  end: number;
  hap1: string;
  hap2: string;
  hap1_lineage?: string | null;
  hap2_lineage?: string | null;
}
interface HaplotypeResponse {
  samples: { sample: string; segments: HapSegment[] }[];
}

const laneColor = (seg: HapSegment | null, lane: 'hap1' | 'hap2'): string => {
  const grey = cssVar('--color-haplotype-unknown');
  if (!seg) return grey;
  const lineage = (lane === 'hap1' ? seg.hap1_lineage : seg.hap2_lineage) || '';
  const value = lane === 'hap1' ? seg.hap1 : seg.hap2;
  const shade = parseInt(value, 10);
  if (lineage === 'paternal') {
    return cssVar(shade === 1 ? '--color-haplotype-father-light' : '--color-haplotype-father-dark');
  }
  if (lineage === 'maternal') {
    return cssVar(shade === 1 ? '--color-haplotype-mother-light' : '--color-haplotype-mother-dark');
  }
  return grey; // untransmitted / unknown / donor
};

const coveringSegment = (segments: HapSegment[], pos: number): HapSegment | null => {
  let lo = 0;
  let hi = segments.length - 1;
  let found: HapSegment | null = null;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (segments[mid].start <= pos) {
      found = segments[mid];
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return found && pos < found.end ? found : null;
};

const alleleBase = (index: string, ref: string, alt: string): string => {
  if (index === '0') return ref;
  const n = parseInt(index, 10);
  if (Number.isNaN(n)) return '·';
  return alt.split(',')[n - 1] ?? '?';
};

const baseSpan = (base: string, key: number): React.ReactNode => (
  <span
    key={key}
    style={{ color: base.length === 1 ? NUCLEOTIDE_COLORS[base.toUpperCase()] ?? '#9ca3af' : '#94a3b8' }}
  >
    {base}
  </span>
);

const FamilyRoiMarkersPage: React.FC = () => {
  const { familyId = '' } = useParams();
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get('project_id');
  const [showAll, setShowAll] = useState(false);

  const { data: family, isLoading: familyLoading } = useQuery<ApiFamilyRecord>({
    queryKey: ['family', familyId],
    queryFn: async () => (await api.get(`/families/${familyId}`)).data as ApiFamilyRecord,
  });

  const roi = family?.roi ?? null;
  const window = useMemo(
    () =>
      roi ? { chr: roi.chr, start: Math.max(0, roi.start - ROI_FLANK), end: roi.end + ROI_FLANK } : null,
    [roi],
  );

  const { data: phased, isLoading: phasedLoading } = useQuery<PhasedMarkerResponse>({
    queryKey: ['phased-markers', familyId, window?.chr, window?.start, window?.end],
    enabled: !!window,
    queryFn: async () =>
      (
        await api.get(`/families/${familyId}/phased-markers`, {
          params: { chr: window!.chr, start: window!.start, end: window!.end },
        })
      ).data as PhasedMarkerResponse,
  });

  const { data: haplo } = useQuery<HaplotypeResponse>({
    queryKey: ['haplotypes', familyId, window?.chr, window?.start, window?.end],
    enabled: !!window,
    queryFn: async () =>
      (
        await api.get(`/families/${familyId}/haplotypes`, {
          params: { chr: window!.chr, start: window!.start, end: window!.end },
        })
      ).data as HaplotypeResponse,
  });

  const roleBySample = useMemo(() => {
    const map = new Map<string, string>();
    (family?.members ?? []).forEach((m) => map.set(m.sample_id, String(m.role || '').toLowerCase()));
    return map;
  }, [family?.members]);

  const segmentsBySample = useMemo(() => {
    const map = new Map<string, HapSegment[]>();
    (haplo?.samples ?? []).forEach((s) =>
      map.set(s.sample, [...s.segments].sort((a, b) => a.start - b.start)),
    );
    return map;
  }, [haplo?.samples]);

  // Positions where at least one EMBRYO has a determinable inherited homolog: the
  // markers that actually drive the segregation call.
  const embryoInformativePos = useMemo(() => {
    const set = new Set<number>();
    (phased?.samples ?? []).forEach((s) => {
      if (roleBySample.get(s.sample) !== 'embryo') return;
      s.markers.forEach((m) => {
        if (m.hap1 !== null || m.hap2 !== null) set.add(m.pos);
      });
    });
    return set;
  }, [phased?.samples, roleBySample]);

  const allSites = phased?.sites ?? [];
  const informativeSites = useMemo(
    () => allSites.filter((s) => embryoInformativePos.has(s.pos)),
    [allSites, embryoInformativePos],
  );

  const baseSites = showAll ? allSites : informativeSites;
  const shownSites = baseSites.slice(0, MAX_COLUMNS);
  const sampleOrder = (phased?.samples ?? []).map((s) => s.sample);
  const qcBySample = useMemo(
    () => new Map((phased?.samples ?? []).map((s) => [s.sample, s.qc])),
    [phased?.samples],
  );

  if (familyLoading || phasedLoading) {
    return <PageState title="Loading ROI markers…" />;
  }
  if (!roi || !window) {
    return (
      <PageState
        title="No region of interest"
        message="Set a region of interest for this family to review its markers."
        action={
          <Link to={`/families/${familyId}${projectId ? `?project_id=${projectId}` : ''}`}>← Back to family</Link>
        }
      />
    );
  }

  const inRoi = (pos: number) => pos >= roi.start && pos <= roi.end;
  const backLink = `/families/${familyId}${projectId ? `?project_id=${projectId}` : ''}`;

  return (
    <div className="page-shell roi-markers-page space-y-4">
      <div className="space-y-1">
        <Link to={backLink} className="family-roi-link">
          ← Back to {family?.family_id ?? 'family'}
        </Link>
        <h1 className="section-title">ROI marker review — {roi.label}</h1>
        <p className="segregation-note">
          All phased markers for every family member across {roi.chr}:{(roi.start - ROI_FLANK).toLocaleString()}–
          {(roi.end + ROI_FLANK).toLocaleString()} (ROI ± 1 Mb). Genotypes are derived from the phased
          imputed data; cell colours show the inherited haplotype (blue = paternal, green = maternal, grey
          = untransmitted/donor/uninformative), matching the chromosome view. Use it to re-check the ROI for
          errors, artefacts and recombination.
        </p>
      </div>

      <div className="roi-markers-summary">
        <span className="table-chip">{allSites.length.toLocaleString()} markers in window</span>
        <span className="table-chip">{informativeSites.length.toLocaleString()} informative for embryos</span>
        <span className="table-chip">
          {(allSites.length - informativeSites.length).toLocaleString()} uninformative
        </span>
        {phased?.truncated && (
          <span className="table-chip table-chip--critical">truncated — zoom in for the full set</span>
        )}
        <button type="button" className="button-ghost" onClick={() => setShowAll((v) => !v)}>
          {showAll ? 'Show informative only' : 'Show all markers'}
        </button>
      </div>

      {shownSites.length < baseSites.length && (
        <div className="segregation-note segregation-note--error">
          Showing the first {shownSites.length.toLocaleString()} of {baseSites.length.toLocaleString()} markers —
          narrow the region or filter to informative markers to see the rest.
        </div>
      )}

      <div className="roi-markers-table-wrap">
        <table className="roi-markers-table">
          <thead>
            <tr>
              <th className="roi-markers-corner">Member</th>
              {shownSites.map((site) => (
                <th
                  key={site.pos}
                  className={`roi-markers-poscol${inRoi(site.pos) ? ' roi-markers-poscol--roi' : ''}`}
                  title={`${roi.chr}:${site.pos.toLocaleString()} ${site.ref}>${site.alt}`}
                >
                  {site.pos.toLocaleString()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sampleOrder.map((sample, memberIdx) => {
              const segs = segmentsBySample.get(sample) ?? [];
              const role = roleBySample.get(sample);
              const qc = qcBySample.get(sample);
              return (
                <tr key={sample} className={role === 'embryo' ? 'roi-markers-row--embryo' : undefined}>
                  <th className="roi-markers-namecol" scope="row">
                    <span className="roi-markers-name">{sample}</span>
                    {role && <span className="roi-markers-role"> ({role})</span>}
                    {qc && qc.mendel_errors > 0 && (
                      <span
                        className="roi-markers-mendel"
                        title={`${qc.mendel_errors} Mendel-inconsistent sites of ${qc.informative_sites} informative (${(qc.mendel_rate * 100).toFixed(1)}%)`}
                      >
                        {' '}
                        ⚠{(qc.mendel_rate * 100).toFixed(1)}%
                      </span>
                    )}
                  </th>
                  {shownSites.map((site) => {
                    const seg = coveringSegment(segs, site.pos);
                    const gt = site.gts[memberIdx] ?? '';
                    const [a, b] = gt.includes('|') ? gt.split('|') : ['', ''];
                    const informative = embryoInformativePos.has(site.pos);
                    return (
                      <td
                        key={site.pos}
                        className={`roi-markers-cell${informative ? '' : ' roi-markers-cell--uninformative'}${
                          inRoi(site.pos) ? ' roi-markers-cell--roi' : ''
                        }`}
                      >
                        <span
                          className="roi-markers-lanes"
                          style={{
                            background: `linear-gradient(to bottom, ${laneColor(seg, 'hap1')} 0 50%, ${laneColor(
                              seg,
                              'hap2',
                            )} 50% 100%)`,
                          }}
                        />
                        <span className="roi-markers-gt">
                          {a ? baseSpan(alleleBase(a, site.ref, site.alt), 0) : '–'}
                          {b ? baseSpan(alleleBase(b, site.ref, site.alt), 1) : ''}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default FamilyRoiMarkersPage;

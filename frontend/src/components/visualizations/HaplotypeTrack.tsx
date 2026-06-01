import React, { useEffect, useMemo, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import * as d3 from 'd3';
import api from '../../lib/api';
import { cssVar } from '../../lib/colors';
import {
  defaultHaplotypeRiskRegion,
  diseaseHaplotypeKindForLane,
  getHaplotypeLaneSignature,
  getRenderableHaplotypeLanes,
  inferDiseaseHaplotypes,
  interpretSampleHaplotypeRisk,
  resolveHaplotypeInheritanceModel,
  type DiseaseHaplotypeKind,
  type HaplotypeLane,
  type HaplotypeMemberLike,
  type HaplotypeRiskRegion,
} from '../../lib/haplotypeRisk';
import VizLoadingOverlay from './VizLoadingOverlay';

interface Segment {
  start: number;
  end: number;
  hap1: string;
  hap2: string;
  ps?: number | null;
}

interface SampleSegments {
  sample: string;
  segments: Segment[];
}

interface HaplotypeResponse {
  chr: string;
  start: number;
  end: number;
  samples: SampleSegments[];
}

const isDeletedHaplotype = (value: string): boolean => value === '.';

interface Props {
  familyId: string;
  sampleId: string;
  chrom: string;
  regionStart: number;
  regionEnd: number;
  width: number;
  height: number;
  role: string;
  affected: boolean;
  sex?: string | null;
  carrierStatus?: boolean | null;
  carrierType?: string | null;
  highlightRiskHaplotype?: boolean;
  disorder?: 'dominant' | 'recessive';
  inheritanceModel?: string | null;
  familyMembers?: HaplotypeMemberLike[];
  riskRegion?: HaplotypeRiskRegion | null;
}

const HaplotypeTrack: React.FC<Props> = ({
  familyId,
  sampleId,
  chrom,
  regionStart,
  regionEnd,
  width,
  height,
  role,
  affected,
  sex,
  carrierStatus = false,
  carrierType,
  highlightRiskHaplotype,
  disorder = 'dominant',
  inheritanceModel,
  familyMembers = [],
  riskRegion,
}) => {
  const { data, isLoading } = useQuery<HaplotypeResponse>({
    queryKey: ['haplotypes', familyId, chrom, regionStart, regionEnd],
    queryFn: async () => {
      const params = { chr: chrom, start: regionStart, end: regionEnd };
      const res = await api.get(`/families/${familyId}/haplotypes`, { params });
      return res.data as HaplotypeResponse;
    },
    enabled: regionEnd > regionStart,
    staleTime: Infinity,
    gcTime: Infinity,
  });

  const svgRef = useRef<SVGSVGElement | null>(null);
  const effectiveInheritanceModel = inheritanceModel || (disorder === 'recessive' ? 'AR' : 'AD');
  const currentMember: HaplotypeMemberLike = useMemo(
    () => ({
      sample_id: sampleId,
      role,
      affected,
      sex,
      carrier_status: carrierStatus ? 'carrier' : 'unknown',
      carrier_type: carrierType,
    }),
    [affected, carrierStatus, carrierType, role, sampleId, sex],
  );
  const membersForRisk = familyMembers.length > 0 ? familyMembers : [currentMember];
  const analysisRegion = riskRegion || defaultHaplotypeRiskRegion(chrom, regionStart, regionEnd);
  const riskEnabled =
    highlightRiskHaplotype ?? membersForRisk.some((member) => member.affected || member.carrier_status === 'carrier');
  const diseaseModel = useMemo(
    () =>
      riskEnabled
        ? inferDiseaseHaplotypes({
            samples: data?.samples || [],
            members: membersForRisk,
            inheritanceModel: resolveHaplotypeInheritanceModel(effectiveInheritanceModel, membersForRisk),
            region: analysisRegion,
          })
        : inferDiseaseHaplotypes({
            samples: [],
            members: [],
            inheritanceModel: effectiveInheritanceModel,
            region: analysisRegion,
          }),
    [analysisRegion, data?.samples, effectiveInheritanceModel, membersForRisk, riskEnabled],
  );

  useEffect(() => {
    if (isLoading) {
      return;
    }

    if (!svgRef.current) return;
    const fatherColors = [cssVar('--color-haplotype-father-dark'), cssVar('--color-haplotype-father-light')];
    const motherColors = [cssVar('--color-haplotype-mother-dark'), cssVar('--color-haplotype-mother-light')];
    const riskColors: Record<DiseaseHaplotypeKind, string> = {
      dominant: cssVar('--color-haplotype-dominant'),
      'recessive-maternal': cssVar('--color-haplotype-recessive-maternal'),
      'recessive-paternal': cssVar('--color-haplotype-recessive-paternal'),
      'x-linked': cssVar('--color-haplotype-x-linked'),
    };
    const unknownColor = cssVar('--color-haplotype-unknown');
    const deletedFill = cssVar('--color-haplotype-deleted-fill');
    const deletedStroke = cssVar('--color-haplotype-deleted-stroke');

    const sample = data?.samples.find((sampleEntry) => sampleEntry.sample === sampleId);
    const segments = sample?.segments || [];
    const span = regionEnd - regionStart || 1;
    const half = height / 2;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const g = svg.append('g');

    const recombXs: number[] = [];

    const baseColorForLane = (seg: Segment, lane: HaplotypeLane): string => {
      const value = seg[lane];
      if (isDeletedHaplotype(value)) return deletedFill;
      const parsed = parseInt(value, 10);
      const signature = getHaplotypeLaneSignature(currentMember, seg, lane, chrom);
      if (!signature) return unknownColor;
      const palette = signature.origin === 'paternal' ? fatherColors : motherColors;
      return isNaN(parsed) ? unknownColor : palette[parsed] || unknownColor;
    };

    segments.forEach((seg: Segment, idx: number) => {
      const x1 = ((seg.start - regionStart) / span) * width;
      const x2 = ((seg.end - regionStart) / span) * width;
      const w = Math.max(x2 - x1, 1);
      if (idx > 0) {
        const prev = segments[idx - 1];
        if (seg.ps !== prev.ps || seg.hap1 !== prev.hap1 || seg.hap2 !== prev.hap2) {
          recombXs.push(x1);
        }
      }
      const grp = g.append('g');
      const lanes = getRenderableHaplotypeLanes(currentMember, seg, chrom);
      lanes.forEach((lane) => {
        const riskKind = diseaseHaplotypeKindForLane(diseaseModel, currentMember, seg, lane, chrom);
        const c = riskKind ? riskColors[riskKind] : baseColorForLane(seg, lane);
        const isSingleLane = lanes.length === 1;
        const y = isSingleLane ? 0 : lane === 'hap1' ? 0 : half + 1;
        const rectHeight = isSingleLane ? height : half - 1;
        grp.append('rect').attr('x', x1).attr('y', y).attr('width', w).attr('height', rectHeight).attr('fill', c);
        if (isDeletedHaplotype(seg[lane])) {
          grp
            .append('line')
            .attr('x1', x1 + 0.75)
            .attr('y1', y + 1)
            .attr('x2', x2 - 0.75)
            .attr('y2', y + rectHeight - 1)
            .attr('stroke', deletedStroke)
            .attr('stroke-width', 1);
        }
      });
    });

    recombXs.forEach((x) => {
      g.append('line')
        .attr('x1', x)
        .attr('x2', x)
        .attr('y1', 0)
        .attr('y2', height)
        .attr('stroke', cssVar('--color-axis'))
        .attr('stroke-dasharray', '4 2');
    });
  }, [
    data,
    sampleId,
    regionStart,
    regionEnd,
    width,
    height,
    role,
    affected,
    sex,
    carrierStatus,
    currentMember,
    diseaseModel,
    isLoading,
  ]);

  const sample = data?.samples.find((sampleEntry) => sampleEntry.sample === sampleId);
  const hasSegments = (sample?.segments.length || 0) > 0;
  const riskState =
    sample && hasSegments
      ? interpretSampleHaplotypeRisk({
          model: diseaseModel,
          samples: data?.samples || [],
          member: currentMember,
          region: analysisRegion,
        })
      : 'uninformative';

  return (
    <div
      className={`relative haplotype-track haplotype-track--${riskState}`}
      data-risk-state={riskState}
      style={{ width, height }}
    >
      <svg ref={svgRef} width={width} height={height} aria-label={`Haplotype risk state: ${riskState}`} />
      {isLoading && <VizLoadingOverlay message="Loading haplotypes" />}
      {!isLoading && !hasSegments && <div className="viz-empty-overlay">No haplotype data in this region</div>}
    </div>
  );
};

export default HaplotypeTrack;

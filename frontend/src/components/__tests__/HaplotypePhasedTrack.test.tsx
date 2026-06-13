import { fireEvent, render } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';

const { useQueryMock } = vi.hoisted(() => ({ useQueryMock: vi.fn() }));

vi.mock('@tanstack/react-query', () => ({ useQuery: useQueryMock }));
vi.mock('../../lib/api', () => ({ default: { get: vi.fn() } }));

import HaplotypePhasedTrack from '../visualizations/HaplotypePhasedTrack';

const members = [
  { sample_id: 'FATHER', role: 'father' },
  { sample_id: 'MOTHER', role: 'mother' },
  { sample_id: 'CHILD', role: 'proband', affected: false },
];

const segments = [
  { start: 0, end: 500, hap1: '0', hap2: '1', ps: 1 },
  { start: 500, end: 1000, hap1: '1', hap2: '1', ps: 1 },
];

// A paternal recombination, maternal side uninformative (mother homozygous).
const markers = [
  { pos: 100, paternal: 0, maternal: null },
  { pos: 300, paternal: 1, maternal: null },
];

const mockData = (opts: { segments?: typeof segments; markers?: typeof markers }) => {
  useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown[] }) => {
    if (queryKey[0] === 'phased-markers') {
      return { data: { samples: [{ sample: 'CHILD', markers: opts.markers ?? [] }] } };
    }
    if (queryKey[0] === 'haplotypes') {
      return {
        data: { chr: '1', start: 0, end: 1000, samples: [{ sample: 'CHILD', segments: opts.segments ?? [] }] },
        isLoading: false,
      };
    }
    return { data: undefined, isLoading: false };
  });
};

const renderTrack = (showMarkers: boolean) =>
  render(
    <HaplotypePhasedTrack
      familyId="F1"
      sampleId="CHILD"
      chrom="1"
      regionStart={0}
      regionEnd={1000}
      width={500}
      height={28}
      role="proband"
      affected={false}
      sex="male"
      highlightRiskHaplotype={false}
      familyMembers={members}
      inheritanceModel="AD"
      riskRegion={null}
      showMarkers={showMarkers}
    />,
  );

beforeEach(() => {
  useQueryMock.mockReset();
});

test('shows an empty message when there are no haplotype segments', () => {
  mockData({ segments: [] });
  const { container } = renderTrack(false);
  expect(container.textContent).toContain('No haplotype data in this region');
});

test('overlays markers: hovering a marker shows the parent-of-origin tooltip', () => {
  mockData({ segments, markers });
  const { container } = renderTrack(true);
  const canvas = container.querySelector('canvas') as Element;
  // x = 50 over width 500 across region 0–1000 → genomic pos 100 (the first marker).
  fireEvent.mouseMove(canvas, { clientX: 50, clientY: 10 });
  const tooltip = document.body.querySelector('.viz-tooltip');
  expect(tooltip?.textContent).toContain('1:100');
  expect(tooltip?.textContent).toContain('homolog 0');
});

test('does not fetch phased markers when the overlay is off', () => {
  mockData({ segments, markers });
  renderTrack(false);
  const phasedCall = useQueryMock.mock.calls.find(
    (call) => (call[0] as { queryKey: unknown[] }).queryKey[0] === 'phased-markers',
  );
  expect((phasedCall?.[0] as { enabled?: boolean } | undefined)?.enabled).toBe(false);
});

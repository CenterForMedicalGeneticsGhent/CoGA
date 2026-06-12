import { fireEvent, render } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';

const { useQueryMock } = vi.hoisted(() => ({ useQueryMock: vi.fn() }));

vi.mock('@tanstack/react-query', () => ({ useQuery: useQueryMock }));
vi.mock('../../lib/api', () => ({ default: { get: vi.fn() } }));

import PhasedMarkerTrack from '../visualizations/PhasedMarkerTrack';

const members = [
  { sample_id: 'FATHER', role: 'father' },
  { sample_id: 'MOTHER', role: 'mother' },
  { sample_id: 'CHILD', role: 'proband', affected: true },
];

// The genetics is server-side now; the endpoint returns oriented markers per
// child. A paternal recombination, maternal side uninformative.
const markers = [
  { pos: 100, paternal: 0, maternal: null },
  { pos: 200, paternal: 0, maternal: null },
  { pos: 300, paternal: 1, maternal: null },
  { pos: 400, paternal: 1, maternal: null },
];

const renderTrack = (regionEnd: number) =>
  render(
    <PhasedMarkerTrack
      familyId="F1"
      sampleId="CHILD"
      chrom="1"
      regionStart={0}
      regionEnd={regionEnd}
      width={500}
      height={24}
      member={{ sample_id: 'CHILD', role: 'proband', affected: true }}
      familyMembers={members}
      inheritanceModel="AD"
      riskRegion={null}
    />,
  );

beforeEach(() => {
  useQueryMock.mockReset();
  useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown[] }) => {
    if (queryKey[0] === 'phased-markers') {
      return { data: { samples: [{ sample: 'CHILD', markers }] } };
    }
    if (queryKey[0] === 'haplotypes') {
      return { data: { samples: [] } };
    }
    return { data: undefined };
  });
});

test('draws paternal markers on the top lane and none on the maternal lane', () => {
  const { container } = renderTrack(1000); // span < 5 Mb -> details shown
  // height 24 -> baseline 12; paternal ticks at y=0, maternal ticks at y=12
  const paternalTicks = container.querySelectorAll('rect[width="1"][y="0"]');
  const maternalTicks = container.querySelectorAll('rect[width="1"][y="12"]');
  expect(paternalTicks.length).toBe(4); // four informative paternal markers
  expect(maternalTicks.length).toBe(0); // mother homozygous -> uninformative
});

test('hovering a marker shows the parent-of-origin tooltip', () => {
  const { container } = renderTrack(1000);
  const hitbox = container.querySelector('rect[fill="transparent"]');
  expect(hitbox).not.toBeNull();
  fireEvent.mouseMove(hitbox as Element, { clientX: 20, clientY: 10 });
  const tooltip = document.body.querySelector('.viz-tooltip');
  expect(tooltip?.textContent).toContain('homolog');
  expect(tooltip?.textContent).toContain('1:100');
});

test('renders markers at wide windows (no 5 Mb span gate)', () => {
  const { container } = renderTrack(20_000_000);
  expect(container.textContent).not.toContain('Zoom');
  // server-bounded markers still render regardless of window size
  expect(container.querySelectorAll('rect[width="1"]').length).toBe(4);
});

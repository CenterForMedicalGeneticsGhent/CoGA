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

// A paternal recombination (mother homozygous -> maternal side uninformative):
// paternal homologs [0, 0, 1, 1].
const variants = [
  { start: 100, source: 'glimpse2', genotypes: [
    { sample: 'FATHER', gt: '0|1' }, { sample: 'MOTHER', gt: '0|0' }, { sample: 'CHILD', gt: '0|0' },
  ] },
  { start: 200, source: 'glimpse2', genotypes: [
    { sample: 'FATHER', gt: '0|1' }, { sample: 'MOTHER', gt: '0|0' }, { sample: 'CHILD', gt: '0|0' },
  ] },
  { start: 300, source: 'glimpse2', genotypes: [
    { sample: 'FATHER', gt: '0|1' }, { sample: 'MOTHER', gt: '0|0' }, { sample: 'CHILD', gt: '0|1' },
  ] },
  { start: 400, source: 'glimpse2', genotypes: [
    { sample: 'FATHER', gt: '0|1' }, { sample: 'MOTHER', gt: '0|0' }, { sample: 'CHILD', gt: '0|1' },
  ] },
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
      return { data: { variants, total: variants.length, total_is_estimated: false } };
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

test('hides detail and prompts to zoom when the region is larger than 5 Mb', () => {
  const { container } = renderTrack(6_000_000);
  expect(container.textContent).toContain('Zoom to ≤5 Mb');
  expect(container.querySelectorAll('rect[width="1"]').length).toBe(0);
});

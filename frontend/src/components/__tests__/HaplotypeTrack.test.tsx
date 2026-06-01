import { render, waitFor } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';

const { useQueryMock } = vi.hoisted(() => ({
  useQueryMock: vi.fn(),
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: useQueryMock,
}));

vi.mock('../../lib/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

import HaplotypeTrack from '../visualizations/HaplotypeTrack';

beforeEach(() => {
  useQueryMock.mockReset();
  document.documentElement.style.setProperty('--color-haplotype-father-dark', '#1d4ed8');
  document.documentElement.style.setProperty('--color-haplotype-father-light', '#93c5fd');
  document.documentElement.style.setProperty('--color-haplotype-mother-dark', '#047857');
  document.documentElement.style.setProperty('--color-haplotype-mother-light', '#86efac');
  document.documentElement.style.setProperty('--color-haplotype-dominant', '#b42318');
  document.documentElement.style.setProperty('--color-haplotype-recessive', '#e11d48');
  document.documentElement.style.setProperty('--color-haplotype-recessive-maternal', '#e11d48');
  document.documentElement.style.setProperty('--color-haplotype-recessive-paternal', '#ea580c');
  document.documentElement.style.setProperty('--color-haplotype-x-linked', '#991b1b');
  document.documentElement.style.setProperty('--color-haplotype-unknown', '#9ca3af');
  document.documentElement.style.setProperty('--color-haplotype-deleted-fill', '#fee2e2');
  document.documentElement.style.setProperty('--color-haplotype-deleted-stroke', '#b42318');
  document.documentElement.style.setProperty('--color-axis', '#111827');
});

test('draws inherited paternal and maternal haplotype switches for an embryo', async () => {
  useQueryMock.mockReturnValue({
    isLoading: false,
    data: {
      chr: '1',
      start: 0,
      end: 100,
      samples: [
        {
          sample: 'EMBRYO1',
          segments: [
            { start: 0, end: 50, hap1: '0', hap2: '1', ps: null },
            { start: 50, end: 100, hap1: '1', hap2: '0', ps: null },
          ],
        },
      ],
    },
  });

  const { container } = render(
    <HaplotypeTrack
      familyId="F1"
      sampleId="EMBRYO1"
      chrom="1"
      regionStart={0}
      regionEnd={100}
      width={100}
      height={20}
      role="embryo"
      affected={false}
    />,
  );

  await waitFor(() => expect(container.querySelectorAll('rect')).toHaveLength(4));
  const rects = Array.from(container.querySelectorAll('rect'));
  expect(rects[0]).toHaveAttribute('fill', '#1d4ed8');
  expect(rects[1]).toHaveAttribute('fill', '#86efac');
  expect(rects[2]).toHaveAttribute('fill', '#93c5fd');
  expect(rects[3]).toHaveAttribute('fill', '#047857');
  expect(container.querySelector('line[stroke-dasharray="4 2"]')).toBeInTheDocument();
});

test('colors inferred recessive maternal and paternal risk haplotypes in embryos', async () => {
  useQueryMock.mockReturnValue({
    isLoading: false,
    data: {
      chr: '1',
      start: 0,
      end: 100,
      samples: [
        {
          sample: 'PROBAND',
          segments: [{ start: 0, end: 100, hap1: '1', hap2: '0', ps: null }],
        },
        {
          sample: 'EMBRYO1',
          segments: [{ start: 0, end: 100, hap1: '1', hap2: '0', ps: null }],
        },
      ],
    },
  });

  const { container } = render(
    <HaplotypeTrack
      familyId="F1"
      sampleId="EMBRYO1"
      chrom="1"
      regionStart={0}
      regionEnd={100}
      width={100}
      height={20}
      role="embryo"
      affected={false}
      highlightRiskHaplotype
      inheritanceModel="AR"
      familyMembers={[
        {
          sample_id: 'PROBAND',
          role: 'proband',
          affected: true,
          sex: 'female',
        },
        {
          sample_id: 'EMBRYO1',
          role: 'embryo',
          affected: false,
          sex: 'female',
        },
      ]}
    />,
  );

  await waitFor(() => expect(container.querySelectorAll('rect')).toHaveLength(2));
  const rects = Array.from(container.querySelectorAll('rect'));
  expect(rects[0]).toHaveAttribute('fill', '#ea580c');
  expect(rects[1]).toHaveAttribute('fill', '#e11d48');
  expect(container.querySelector('.haplotype-track')).toHaveAttribute('data-risk-state', 'affected_or_at_risk');
});

test('does not color a dominant haplotype without a deterministic shared block', async () => {
  useQueryMock.mockReturnValue({
    isLoading: false,
    data: {
      chr: '1',
      start: 0,
      end: 100,
      samples: [
        {
          sample: 'PROBAND',
          segments: [{ start: 0, end: 100, hap1: '1', hap2: '1', ps: null }],
        },
      ],
    },
  });

  const { container } = render(
    <HaplotypeTrack
      familyId="F1"
      sampleId="PROBAND"
      chrom="1"
      regionStart={0}
      regionEnd={100}
      width={100}
      height={20}
      role="proband"
      affected
      highlightRiskHaplotype
      inheritanceModel="AD"
      familyMembers={[
        {
          sample_id: 'PROBAND',
          role: 'proband',
          affected: true,
          sex: 'female',
        },
      ]}
    />,
  );

  await waitFor(() => expect(container.querySelectorAll('rect')).toHaveLength(2));
  const rects = Array.from(container.querySelectorAll('rect'));
  expect(rects[0]).toHaveAttribute('fill', '#93c5fd');
  expect(rects[1]).toHaveAttribute('fill', '#86efac');
  expect(container.querySelector('.haplotype-track')).toHaveAttribute('data-risk-state', 'uninformative');
});

test('renders a single disease-associated X haplotype for affected males', async () => {
  useQueryMock.mockReturnValue({
    isLoading: false,
    data: {
      chr: 'X',
      start: 0,
      end: 100,
      samples: [
        {
          sample: 'SON',
          segments: [{ start: 0, end: 100, hap1: '0', hap2: '1', ps: null }],
        },
      ],
    },
  });

  const { container } = render(
    <HaplotypeTrack
      familyId="F1"
      sampleId="SON"
      chrom="X"
      regionStart={0}
      regionEnd={100}
      width={100}
      height={20}
      role="proband"
      affected
      sex="male"
      highlightRiskHaplotype
      inheritanceModel="XLR"
      familyMembers={[{ sample_id: 'SON', role: 'proband', affected: true, sex: 'male' }]}
    />,
  );

  await waitFor(() => expect(container.querySelectorAll('rect')).toHaveLength(1));
  const rects = Array.from(container.querySelectorAll('rect'));
  expect(rects[0]).toHaveAttribute('fill', '#991b1b');
  expect(rects[0]).toHaveAttribute('height', '20');
});

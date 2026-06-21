import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import FamilyRoiMarkersPage from '../FamilyRoiMarkersPage';
import api from '../../../lib/api';
import { createTestQueryClient } from '../../../test/createTestQueryClient';

vi.mock('../../../lib/api', () => ({ default: { get: vi.fn() } }));

const family = {
  family_id: 'co1',
  members: [
    { sample_id: 'FATHER', role: 'father', affected: true, sex: 'male' },
    { sample_id: 'MOTHER', role: 'mother', affected: false, sex: 'female' },
    { sample_id: 'EMBRYO', role: 'embryo', affected: false, sex: 'female' },
  ],
  roi: { chr: '1', start: 1_000_000, end: 1_001_000, label: 'GENEX', source: 'gene', query: 'GENEX' },
  metadata: { pgt: { inheritance_model: 'AD' } },
};

// One informative (in-ROI, embryo has a marker) and one uninformative (out-of-ROI) site.
const phased = {
  samples: [
    { sample: 'FATHER', markers: [{ pos: 1_000_500, hap1: 0, hap2: 1 }], reference: true, qc: null },
    { sample: 'MOTHER', markers: [{ pos: 1_000_500, hap1: 0, hap2: 0 }], reference: true, qc: null },
    {
      sample: 'EMBRYO',
      markers: [{ pos: 1_000_500, hap1: 1, hap2: 0 }],
      reference: false,
      qc: { informative_sites: 10, mendel_errors: 0, mendel_rate: 0 },
    },
  ],
  sites: [
    { pos: 1_000_500, ref: 'G', alt: 'A', gts: ['0|1', '0|0', '1|0'] }, // in ROI, informative
    { pos: 1_500_000, ref: 'C', alt: 'T', gts: ['0|0', '0|0', '0|0'] }, // out of ROI, uninformative
  ],
  truncated: false,
};

const hapSeg = (hap1: string, hap2: string, l1: string, l2: string) => [
  { start: 0, end: 2_000_000, hap1, hap2, hap1_lineage: l1, hap2_lineage: l2 },
];
const haplo = {
  samples: [
    { sample: 'FATHER', segments: hapSeg('0', '1', 'paternal', 'paternal') },
    { sample: 'MOTHER', segments: hapSeg('0', '1', 'maternal', 'maternal') },
    { sample: 'EMBRYO', segments: hapSeg('1', '0', 'paternal', 'maternal') },
  ],
};

const renderPage = () =>
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter initialEntries={['/families/co1/roi-markers']}>
        <Routes>
          <Route path="/families/:familyId/roi-markers" element={<FamilyRoiMarkersPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

beforeEach(() => {
  (api.get as Mock).mockReset();
  (api.get as Mock).mockImplementation((url: string) => {
    if (url === '/families/co1') return Promise.resolve({ data: family });
    if (url.endsWith('/phased-markers')) return Promise.resolve({ data: phased });
    if (url.endsWith('/haplotypes')) return Promise.resolve({ data: haplo });
    return Promise.resolve({ data: {} });
  });
});

describe('FamilyRoiMarkersPage', () => {
  it('renders the member-by-marker genotype table with derived colour-coded cells and counts', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText(/ROI marker review/)).toBeTruthy());

    // Every family member is a row.
    expect(screen.getByText('FATHER')).toBeTruthy();
    expect(screen.getByText('MOTHER')).toBeTruthy();
    expect(screen.getByText('EMBRYO')).toBeTruthy();

    // Marker counts: 2 in window, 1 informative for embryos, 1 uninformative.
    expect(screen.getByText(/2 markers in window/)).toBeTruthy();
    expect(screen.getByText(/1 informative for embryos/)).toBeTruthy();
    expect(screen.getByText(/1 uninformative/)).toBeTruthy();

    // Default view (informative only) shows the in-ROI site's decoded genotypes:
    // father 0|1 -> G,A ; embryo 1|0 -> A,G.
    const table = document.querySelector('.roi-markers-table') as HTMLElement;
    expect(table.textContent).toContain('GA');
    expect(table.textContent).toContain('AG');

    // It is clearly framed as derived, not user-entered.
    expect(screen.getByText(/derived from the phased imputed data/i)).toBeTruthy();
  });
});

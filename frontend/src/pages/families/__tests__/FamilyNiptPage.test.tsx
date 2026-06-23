import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import FamilyNiptPage from '../FamilyNiptPage';
import { createTestQueryClient } from '../../../test/createTestQueryClient';

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../../../lib/api', () => ({
  default: apiMock,
}));

const FETAL_FRACTION = {
  ff: 0.1,
  ff_computed: 0.1,
  ff_external: null,
  ff_median: 0.1,
  ci_low: 0.095,
  ci_high: 0.105,
  n_sites: 40,
  method: 'category7_pooled',
  low_confidence: false,
  disagreement: false,
};

const renderPage = (familyId: string) => {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/families/${familyId}/nipt`]}>
        <Routes>
          <Route path="/families/:familyId/nipt" element={<FamilyNiptPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe('FamilyNiptPage', () => {
  it('renders the fetal fraction, funnel, categories, and classified variants', async () => {
    apiMock.get.mockImplementation((url: string) => {
      if (url === '/families/NIPT001') {
        return Promise.resolve({
          data: {
            family_id: 'NIPT001',
            members: [],
            metadata: { analysis_type: 'monogenic_nipt' },
          },
        });
      }
      if (url === '/families/NIPT001/nipt/summary') {
        return Promise.resolve({
          data: {
            family_id: 'NIPT001',
            fetal_fraction: FETAL_FRACTION,
            category_counts: { '1': 1, '3': 2, '7': 40 },
            filter_counts: { total_in: 100, failed_quality: 5, failed_artifact: 3, passed: 92 },
          },
        });
      }
      if (url === '/families/NIPT001/nipt/coverage') {
        return Promise.resolve({
          data: {
            family_id: 'NIPT001',
            overall_median_on_target: 120,
            target_region_count: 1,
            per_region: [
              {
                label: 'ROI',
                chr: '1',
                start: 100,
                end: 200,
                median_coverage: 118,
                covered_bases: 100,
                target_bases: 100,
              },
            ],
          },
        });
      }
      if (url === '/families/NIPT001/nipt/variants') {
        return Promise.resolve({
          data: {
            family_id: 'NIPT001',
            total: 1,
            fetal_fraction: FETAL_FRACTION,
            variants: [
              {
                variant_id: '1-100-A-G',
                chr: '1',
                pos: 100,
                ref: 'A',
                alt: 'G',
                gene: 'BRCA1',
                impact: 'HIGH',
                consequence: 'missense_variant',
                category: 7,
                category_label: 'paternal, transmitted to fetus',
                maternal_state: 'hom_ref',
                fetal_inheritance: 'paternal_transmitted',
                expected_vaf: 0.05,
                observed_vaf: 0.05,
                confidence: 0.97,
                flags: [],
              },
            ],
          },
        });
      }
      return Promise.resolve({ data: {} });
    });

    renderPage('NIPT001');

    expect(
      await screen.findByRole('heading', { name: /monogenic nipt analysis — NIPT001/i }),
    ).toBeInTheDocument();

    // Fetal fraction and the filter funnel come from the summary query.
    expect(await screen.findByText('10.0%')).toBeInTheDocument();
    expect(screen.getByText('Analysed')).toBeInTheDocument();
    expect(screen.getByText('92')).toBeInTheDocument();

    // On-target coverage comes from the coverage query.
    expect(await screen.findByText('120x')).toBeInTheDocument();
    expect(screen.getByText('On-target coverage')).toBeInTheDocument();

    // The classified variant row comes from the variants query.
    expect(await screen.findByText('BRCA1')).toBeInTheDocument();
    expect(screen.getByText('missense_variant')).toBeInTheDocument();
    expect(screen.getByText('1 variant · page 1 of 1')).toBeInTheDocument();
  });

  it('shows a not-configured message for a non-NIPT family', async () => {
    apiMock.get.mockResolvedValue({
      data: { family_id: 'FAM001', members: [], metadata: {} },
    });

    renderPage('FAM001');

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /not a monogenic nipt family/i }),
      ).toBeInTheDocument();
    });
  });
});

import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import FamilySampleQcPage from '../FamilySampleQcPage';
import { createTestQueryClient } from '../../../test/createTestQueryClient';

const apiMock = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock('../../../lib/api', () => ({ default: apiMock }));

const renderPage = () => {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/families/FAM1/qc']}>
        <Routes>
          <Route path="/families/:familyId/qc" element={<FamilySampleQcPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe('FamilySampleQcPage', () => {
  it('renders the three QC sections and surfaces a failing swap', async () => {
    apiMock.get.mockResolvedValue({
      data: {
        family_id: 'FAM1',
        overall_status: 'fail',
        autosomal_sites: 90000,
        notes: [],
        sex_checks: [
          {
            sample_id: 'CHILD',
            recorded_sex: 'male',
            inferred_sex: 'female',
            x_het_rate: 0.3,
            x_sites: 500,
            status: 'fail',
            message: 'Recorded male but genotypes indicate female — possible sample swap.',
          },
        ],
        relatedness_checks: [
          {
            sample_a: 'CHILD',
            sample_b: 'FATHER',
            expected_relationship: 'parent-child',
            inferred_relationship: 'unrelated',
            kinship: 0.01,
            ibs0_rate: 0.18,
            informative_sites: 80000,
            status: 'fail',
            message: 'Recorded parent-child but genotypes look unrelated.',
          },
        ],
        mendelian_checks: [
          {
            child: 'CHILD',
            parents: ['FATHER', 'MOTHER'],
            informative_sites: 80000,
            mendel_errors: 12000,
            mendel_rate: 0.15,
            status: 'fail',
            message: 'High Mendelian-error rate — likely swap or wrong parent.',
          },
        ],
      },
    });

    renderPage();

    expect(
      await screen.findByRole('heading', { name: /family FAM1/i }),
    ).toBeInTheDocument();
    // The three section headings render.
    expect(screen.getByText('Sex concordance')).toBeInTheDocument();
    expect(screen.getByText('Relatedness vs pedigree')).toBeInTheDocument();
    expect(screen.getByText('Mendelian-error rate')).toBeInTheDocument();
    // The swap surfaces across all three checks.
    expect(screen.getAllByText('Fail').length).toBeGreaterThanOrEqual(3);
    expect(
      screen.getByText(/CHILD ↔ FATHER — expected parent-child, observed unrelated/),
    ).toBeInTheDocument();
    expect(screen.getByText(/CHILD vs FATHER \+ MOTHER — 15\.00% errors/)).toBeInTheDocument();
  });

  it('shows an all-clear overall status when checks pass', async () => {
    apiMock.get.mockResolvedValue({
      data: {
        family_id: 'FAM1',
        overall_status: 'pass',
        autosomal_sites: 90000,
        notes: [],
        sex_checks: [],
        relatedness_checks: [],
        mendelian_checks: [],
      },
    });

    renderPage();

    expect(
      await screen.findByText(/All sample-integrity checks passed/),
    ).toBeInTheDocument();
  });
});

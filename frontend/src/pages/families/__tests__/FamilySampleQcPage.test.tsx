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
        application: 'wgs',
        application_label: 'Long-read WGS family',
        application_summary: 'Full pedigree QC on the SNV call set.',
        genotype_source: 'clair3',
        paternity_check: null,
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
        application: 'wgs',
        application_label: 'Long-read WGS family',
        application_summary: 'Full pedigree QC on the SNV call set.',
        genotype_source: 'clair3',
        paternity_check: null,
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

  it('adapts to the NIPT application: shows paternity, hides genotype sections', async () => {
    apiMock.get.mockResolvedValue({
      data: {
        family_id: 'FAM1',
        overall_status: 'pass',
        application: 'nipt',
        application_label: 'Monogenic NIPT (cfDNA)',
        application_summary: 'Paternity is confirmed from paternal-transmitted sites (categories 7/8).',
        genotype_source: null,
        sex_checks: [],
        relatedness_checks: [],
        mendelian_checks: [],
        paternity_check: {
          father: 'FATHER',
          cat7_transmitted: 40,
          cat8_absent: 2,
          informative_sites: 42,
          status: 'pass',
          message: 'Paternity supported: paternal transmission observed.',
        },
        fetal_sex_check: {
          inferred_sex: 'female',
          x_transmitted: 12,
          x_not_transmitted: 0,
          informative_sites: 12,
          status: 'pass',
          message: 'Fetal sex appears female: paternal X transmitted.',
        },
        autosomal_sites: 0,
        notes: [],
      },
    });

    renderPage();

    expect(await screen.findByText('Paternity (cfDNA categories 7/8)')).toBeInTheDocument();
    expect(screen.getByText(/Father FATHER — 40 paternal-transmitted/)).toBeInTheDocument();
    expect(screen.getByText('Fetal sex (paternal X transmission)')).toBeInTheDocument();
    expect(screen.getByText(/Fetus appears female — 12 paternal-X transmitted/)).toBeInTheDocument();
    // Genotype-based sections are not rendered for the cfDNA application.
    expect(screen.queryByText('Sex concordance')).not.toBeInTheDocument();
    expect(screen.queryByText('Relatedness vs pedigree')).not.toBeInTheDocument();
    expect(screen.queryByText('Mendelian-error rate')).not.toBeInTheDocument();
  });
});

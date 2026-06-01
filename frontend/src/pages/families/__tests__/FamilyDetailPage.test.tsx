import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, it, vi } from 'vitest';

import FamilyDetailPage from '../FamilyDetailPage';
import { createTestQueryClient } from '../../../test/createTestQueryClient';
import api from '../../../lib/api';

const mockApiState = vi.hoisted(() => ({
  smallVariantTotal: 1,
  structuralVariantTotal: 1,
}));

vi.mock('../../../lib/api', () => ({
  default: {
    get: vi.fn((url: string) => {
      if (url === '/families/F1') {
        return Promise.resolve({
          data: {
            _id: 'fam1',
            family_id: 'F1',
            members: [{ sample_id: 'S1', role: 'proband', affected: true, sex: 'male' }],
            pedigree: null,
            projects: ['p1'],
            metadata: {},
            roi: {
              query: 'GENE1',
              label: 'GENE1',
              source: 'gene',
              assembly_id: 'asm1',
              chr: '17',
              start: 43044295,
              end: 43125482,
            },
          },
        });
      }
      if (url.startsWith('/families/F1/structural-variants')) {
        return Promise.resolve({ data: { total: mockApiState.structuralVariantTotal, variants: [] } });
      }
      if (url.startsWith('/families/F1/small-variants')) {
        return Promise.resolve({ data: { total: mockApiState.smallVariantTotal, variants: [] } });
      }
      if (url === '/families/F1/small-variant-review-summary') {
        return Promise.resolve({
          data: {
            reviewed_variant_count: 3,
            note_count: 2,
            tag_counts: {
              review: 2,
              send_for_validation: 1,
              acmg_class_4: 1,
            },
          },
        });
      }
      if (url === '/families/F1/small-variant-tags') {
        return Promise.resolve({
          data: [
            {
              key: 'review',
              label: 'Review',
              group: 'collaboration',
              color: '#2563eb',
              sort_order: 10,
              scope: 'system',
              is_custom: false,
            },
            {
              key: 'send_for_validation',
              label: 'Send for validation',
              group: 'collaboration',
              color: '#b7791f',
              sort_order: 20,
              scope: 'system',
              is_custom: false,
            },
            {
              key: 'acmg_class_4',
              label: 'Likely Pathogenic - class 4',
              group: 'classification',
              color: '#ea580c',
              sort_order: 120,
              scope: 'system',
              is_custom: false,
            },
          ],
        });
      }
      if (url === '/families/F1/structural-variant-review-summary') {
        return Promise.resolve({
          data: {
            reviewed_variant_count: 2,
            note_count: 1,
            tag_counts: {
              review: 1,
              needs_segmentation_review: 1,
            },
          },
        });
      }
      if (url === '/families/F1/structural-variant-tags') {
        return Promise.resolve({
          data: [
            {
              key: 'review',
              label: 'Review',
              group: 'collaboration',
              color: '#2563eb',
              sort_order: 10,
              scope: 'system',
              is_custom: false,
            },
            {
              key: 'needs_segmentation_review',
              label: 'Needs segmentation review',
              group: 'collaboration',
              color: '#7c3aed',
              sort_order: 25,
              scope: 'family',
              is_custom: true,
            },
          ],
        });
      }
      if (url === '/projects') {
        return Promise.resolve({
          data: [{ _id: 'p1', name: 'Oncology pilot', species_id: 'sp1', assembly_id: 'asm1' }],
        });
      }
      if (url === '/species') {
        return Promise.resolve({
          data: [{ _id: 'sp1', name: 'Homo sapiens', common_name: 'human' }],
        });
      }
      if (url === '/assemblies/sp1') {
        return Promise.resolve({
          data: [{ _id: 'asm1', assembly_name: 'GRCh38', version: 'p14' }],
        });
      }
      return Promise.resolve({ data: [] });
    }),
    put: vi.fn(),
  },
}));

describe('FamilyDetailPage', () => {
  beforeEach(() => {
    localStorage.clear();
    mockApiState.smallVariantTotal = 1;
    mockApiState.structuralVariantTotal = 1;
    vi.mocked(api.put).mockReset();
  });

  it('shows the current family ROI summary and project links without edit controls', async () => {
    localStorage.setItem('role', 'admin');
    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/families/F1']}>
          <Routes>
            <Route path="/families/:familyId" element={<FamilyDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText(/Family F1/i)).toBeInTheDocument());
    expect(screen.getByText(/GENE1/i)).toBeInTheDocument();
    expect(screen.getByText(/chr17:43,044,295-43,125,482/i)).toBeInTheDocument();
    expect(screen.getByText(/Oncology pilot/i)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /structural variants/i })
    ).toHaveAttribute('href', '/families/F1/structural-variants?project_id=p1');
    expect(
      screen.getByRole('link', { name: /small variants/i })
    ).toHaveAttribute('href', '/families/F1/small-variants?project_id=p1');
    expect(
      screen.queryByPlaceholderText(/BRCA1 or chr17:43044295-43125482/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /save roi/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Carrier status for S1')).not.toBeInTheDocument();
    expect(screen.getByLabelText(/variant curation summary/i)).toBeInTheDocument();
    const smallVariantCuration = screen.getByLabelText(/small variant review summary/i);
    const structuralVariantCuration = screen.getByLabelText(/structural variant review summary/i);
    expect(within(smallVariantCuration).getByText('Small variants')).toBeInTheDocument();
    expect(within(structuralVariantCuration).getByText('Structural variants')).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getByText((_, element) => element?.textContent?.trim() === 'Reviewed 3'),
      ).toBeInTheDocument();
      expect(
        screen.getByText((_, element) => element?.textContent?.trim() === 'Notes 2'),
      ).toBeInTheDocument();
      expect(
        screen.getByText((_, element) => element?.textContent?.trim() === 'Review 2'),
      ).toBeInTheDocument();
      expect(
        screen.getByText((_, element) => element?.textContent?.trim() === 'Send for validation 1'),
      ).toBeInTheDocument();
      expect(
        screen.getByText((_, element) => element?.textContent?.trim() === 'Reviewed 2'),
      ).toBeInTheDocument();
      expect(
        screen.getByText((_, element) => element?.textContent?.trim() === 'Needs segmentation review 1'),
      ).toBeInTheDocument();
    });
  });

  it('keeps variant workspace navigation visible when no variant records are loaded', async () => {
    mockApiState.smallVariantTotal = 0;
    mockApiState.structuralVariantTotal = 0;
    localStorage.setItem('role', 'viewer');
    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/families/F1']}>
          <Routes>
            <Route path="/families/:familyId" element={<FamilyDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText(/Family F1/i)).toBeInTheDocument());
    expect(
      screen.getByRole('link', { name: /structural variants/i })
    ).toHaveAttribute('href', '/families/F1/structural-variants?project_id=p1');
    expect(
      screen.getByRole('link', { name: /small variants/i })
    ).toHaveAttribute('href', '/families/F1/small-variants?project_id=p1');
    await waitFor(() =>
      expect(screen.getByText(/No family variant data is loaded yet/i)).toBeInTheDocument(),
    );
  });

  it('preserves the selected project in variant workspace links', async () => {
    localStorage.setItem('role', 'viewer');
    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/families/F1?project_id=p1']}>
          <Routes>
            <Route path="/families/:familyId" element={<FamilyDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText(/Family F1/i)).toBeInTheDocument());
    expect(
      screen.getByRole('link', { name: /structural variants/i })
    ).toHaveAttribute('href', '/families/F1/structural-variants?project_id=p1');
    expect(
      screen.getByRole('link', { name: /small variants/i })
    ).toHaveAttribute('href', '/families/F1/small-variants?project_id=p1');
  });

  it('saves family structure edits with carrier state and explicit couples', async () => {
    localStorage.setItem('role', 'admin');
    vi.mocked(api.put).mockResolvedValueOnce({
      data: {
        family: {
          _id: 'fam1',
          family_id: 'F1',
          members: [
            {
              sample_id: 'S1',
              role: 'proband',
              affected: true,
              sex: 'male',
              clinical_status: 'affected',
              carrier_status: 'carrier',
              carrier_type: 'proven',
            },
            {
              sample_id: 'S2',
              role: 'relative',
              affected: false,
              sex: 'female',
              clinical_status: 'unknown',
              carrier_status: 'unknown',
            },
          ],
          relationships: [
            {
              id: 'r1',
              relationship_type: 'couple',
              sample_id_a: 'S1',
              sample_id_b: 'S2',
              role_a: 'partner',
              role_b: 'partner',
              metadata: {},
            },
          ],
          structure_version: { version: 2 },
          pedigree: null,
          projects: ['p1'],
          metadata: {},
          roi: null,
        },
        warnings: ['Relationship-dependent analyses should be rerun before clinical review.'],
      },
    });
    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/admin/data/families/F1/structure']}>
          <Routes>
            <Route path="/admin/data/families/:familyId/structure" element={<FamilyDetailPage editable />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText(/Family F1/i)).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Carrier status for S1'), { target: { value: 'carrier' } });
    fireEvent.change(screen.getByLabelText('Carrier type for S1'), { target: { value: 'proven' } });
    fireEvent.change(screen.getByLabelText('New member sample ID'), { target: { value: 'S2' } });
    fireEvent.change(screen.getByLabelText('New member sex'), { target: { value: 'female' } });
    fireEvent.click(screen.getByRole('button', { name: /add member/i }));
    fireEvent.click(screen.getByRole('button', { name: /add couple/i }));
    fireEvent.click(screen.getByRole('button', { name: /save family structure/i }));

    await waitFor(() => expect(api.put).toHaveBeenCalledWith(
      '/families/F1/structure',
      expect.objectContaining({
        clear_existing_genomic_data: false,
        add_members: [
          expect.objectContaining({
            sample_id: 'S2',
            sex: 'female',
          }),
        ],
        members: [
          expect.objectContaining({
            sample_id: 'S1',
            carrier_status: 'carrier',
            carrier_type: 'proven',
          }),
        ],
        relationships: expect.objectContaining({
          couples: [
            expect.objectContaining({
              partners: ['S1', 'S2'],
            }),
          ],
        }),
      }),
    ));
    expect(await screen.findByText(/Family structure saved/i)).toBeInTheDocument();
  });
});

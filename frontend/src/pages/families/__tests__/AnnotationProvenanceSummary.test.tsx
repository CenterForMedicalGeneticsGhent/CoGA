import { QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import AnnotationProvenanceSummary from '../AnnotationProvenanceSummary';
import { createTestQueryClient } from '../../../test/createTestQueryClient';

const apiMock = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('../../../lib/api', () => ({ default: apiMock }));

function renderSummary() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <AnnotationProvenanceSummary familyId="FAM1" />
    </QueryClientProvider>,
  );
}

const MODULE = (key: string, label: string, version: string, detail: string | null = null) => ({
  key,
  label,
  version,
  detail,
  layer: 'pipeline',
});

describe('AnnotationProvenanceSummary', () => {
  it('shows tool/db versions, the source, and a working show-more toggle', async () => {
    apiMock.get.mockResolvedValue({
      data: {
        family_id: 'FAM1',
        assembly: 'GRCh38',
        source: 'vcf_header',
        recorded_at: null,
        recorded_by: null,
        modules: [
          MODULE('vep', 'VEP', '110', '110_GRCh38'),
          MODULE('gnomad', 'gnomAD', 'r2.1.1'),
          MODULE('clinvar', 'ClinVar', '202301'),
          MODULE('deepvariant', 'DeepVariant', '1.6.0', 'snv caller'),
          MODULE('sniffles', 'Sniffles', '2.2', 'sv caller'),
          MODULE('trgt', 'TRGT', '0.7.0', 'repeats caller'),
          MODULE('dbnsfp', 'dbNSFP', '4.3a'),
          MODULE('spliceai', 'SpliceAI', '1.3'),
        ],
      },
    });

    renderSummary();

    await waitFor(() => expect(screen.getByText('110')).toBeInTheDocument());
    // Versions from across modalities are present (SNV caller + SV caller + repeats).
    expect(screen.getByText('1.6.0')).toBeInTheDocument();
    expect(screen.getByText('2.2')).toBeInTheDocument();
    expect(screen.getByText('from VCF headers')).toBeInTheDocument();

    // 8 modules collapse to 6; the last two are hidden until expanded.
    expect(screen.queryByText('1.3')).toBeNull();
    fireEvent.click(screen.getByText('+2 more'));
    expect(screen.getByText('1.3')).toBeInTheDocument();
  });

  it('renders nothing when no versioned modules are recorded', async () => {
    apiMock.get.mockResolvedValue({
      data: {
        family_id: 'FAM1',
        assembly: null,
        source: null,
        recorded_at: null,
        recorded_by: null,
        modules: [],
      },
    });

    const { container } = renderSummary();
    await waitFor(() => expect(apiMock.get).toHaveBeenCalled());
    expect(container.querySelector('[data-testid="annotation-provenance"]')).toBeNull();
  });
});

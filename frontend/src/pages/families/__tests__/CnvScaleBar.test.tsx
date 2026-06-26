// ClinGen CNV points-scale readout — REQ-UI-003 (risk H3).

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import CnvScaleBar from '../CnvScaleBar';
import type { CnvClassification } from '../../../lib/cnvAcmg';

describe('CnvScaleBar', () => {
  it('shows the CNV class label and signed point total', () => {
    const classification: CnvClassification = {
      pointTotal: 0.99,
      classKey: 'pathogenic',
      classLabel: 'Pathogenic',
    };
    render(<CnvScaleBar classification={classification} />);

    // Disambiguate the readout label from the identical legend label.
    expect(screen.getByText('Pathogenic', { selector: '.acmg-scalebar-class' })).toBeInTheDocument();
    expect(screen.getByText('+0.99 pts')).toBeInTheDocument();
    expect(screen.getByRole('img')).toHaveAttribute(
      'aria-label',
      expect.stringContaining('Pathogenic, +0.99 points'),
    );
  });

  it('formats a negative (benign) total without a plus sign', () => {
    const classification: CnvClassification = {
      pointTotal: -0.9,
      classKey: 'benign',
      classLabel: 'Benign',
    };
    render(<CnvScaleBar classification={classification} />);

    expect(screen.getByText('-0.9 pts')).toBeInTheDocument();
  });
});

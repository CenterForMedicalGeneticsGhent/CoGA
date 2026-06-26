// ACMG points-scale readout — REQ-UI-003 (risk H3).
// The bar must show the class, the signed point total, the VUS sub-tier, and a
// BA1 stand-alone-benign override, with an accessible aria-label describing them.

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import AcmgScaleBar from '../AcmgScaleBar';
import type { AcmgClassification } from '../../../lib/acmg';

describe('AcmgScaleBar', () => {
  it('shows the class label and signed point total for a pathogenic call', () => {
    const classification: AcmgClassification = {
      points: 12,
      classKey: 'acmg_class_5',
      label: 'Pathogenic - class 5',
      standAloneBenign: false,
      vusTier: null,
    };
    render(<AcmgScaleBar classification={classification} />);

    expect(screen.getByText('Pathogenic - class 5')).toBeInTheDocument();
    expect(screen.getByText('+12 pts')).toBeInTheDocument();
    expect(screen.getByRole('img')).toHaveAttribute(
      'aria-label',
      expect.stringContaining('+12 points'),
    );
  });

  it('surfaces the VUS sub-tier chip and aria-label', () => {
    const classification: AcmgClassification = {
      points: 5,
      classKey: 'acmg_class_3',
      label: 'VUS - class 3',
      standAloneBenign: false,
      vusTier: 'hot',
    };
    render(<AcmgScaleBar classification={classification} />);

    expect(screen.getByText('Hot VUS')).toBeInTheDocument();
    expect(screen.getByRole('img')).toHaveAttribute(
      'aria-label',
      expect.stringContaining('(Hot VUS)'),
    );
  });

  it('renders the BA1 stand-alone benign override', () => {
    const classification: AcmgClassification = {
      points: -3,
      classKey: 'acmg_class_1',
      label: 'Benign - class 1',
      standAloneBenign: true,
      vusTier: null,
    };
    render(<AcmgScaleBar classification={classification} />);

    expect(screen.getByText('BA1 pts')).toBeInTheDocument();
    expect(screen.getByRole('img')).toHaveAttribute(
      'aria-label',
      expect.stringContaining('BA1 points'),
    );
  });
});

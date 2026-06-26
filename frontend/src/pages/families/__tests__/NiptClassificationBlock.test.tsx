// NIPT per-variant classification display — REQ-UI-001 (risk H6).
// The analyst reads the fetal category, confidence and observed/expected VAF off
// this block, so the numbers must render faithfully (confidence 2 dp, VAF as %,
// em dash for missing) and QC flags must be visible.

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import NiptClassificationBlock from '../NiptClassificationBlock';
import type { NiptClassification } from '../smallVariantSearch';

const base: NiptClassification = {
  category: 7,
  category_label: 'Paternal transmitted',
  maternal_state: 'hom_ref',
  fetal_inheritance: 'paternal',
  expected_vaf: 0.05,
  observed_vaf: 0.048,
  confidence: 0.873,
  flags: [],
};

describe('NiptClassificationBlock', () => {
  it('shows the category, label and confidence to two decimals', () => {
    render(<NiptClassificationBlock nipt={base} />);
    expect(screen.getByText('Category 7')).toBeInTheDocument();
    expect(screen.getByText('Paternal transmitted')).toBeInTheDocument();
    expect(screen.getByText('confidence 0.87')).toBeInTheDocument();
  });

  it('formats observed/expected VAF as percentages', () => {
    render(<NiptClassificationBlock nipt={{ ...base, observed_vaf: 0.123, expected_vaf: 0.05 }} />);
    expect(screen.getByText('12.3% / 5.0%')).toBeInTheDocument();
  });

  it('renders an em dash for a missing observed VAF', () => {
    render(<NiptClassificationBlock nipt={{ ...base, observed_vaf: null }} />);
    expect(screen.getByText('— / 5.0%')).toBeInTheDocument();
  });

  it('shows "Unclassified" when no category and renders QC flags', () => {
    render(
      <NiptClassificationBlock
        nipt={{ ...base, category: null, flags: ['low_depth', 'dropout'] }}
      />,
    );
    expect(screen.getByText('Unclassified')).toBeInTheDocument();
    expect(screen.getByText('low_depth')).toBeInTheDocument();
    expect(screen.getByText('dropout')).toBeInTheDocument();
  });
});

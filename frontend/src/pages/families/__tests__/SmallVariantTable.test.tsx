import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import SmallVariantTable from '../SmallVariantTable';

describe('SmallVariantTable', () => {
  it('keeps long allele values constrained while preserving the full value in the tooltip', () => {
    const longAlt = `A${'C'.repeat(120)}T`;

    render(
      <MemoryRouter>
        <SmallVariantTable
          variants={[
            {
              _id: 'long-indel',
              chr: '1',
              start: 123,
              end: 123,
              type: 'INDEL',
              gene: 'GENE1',
              ref: 'G',
              alt: longAlt,
              impact: 'MODERATE',
              effect: 'frameshift_variant',
              genotypes: [],
            },
          ]}
          members={[]}
          familyId="F1"
          projectId="P1"
          locationSearch=""
          tags={[]}
          onEditReview={vi.fn()}
          onToggleReviewTag={vi.fn(async () => undefined)}
        />
      </MemoryRouter>,
    );

    const allele = screen.getByTitle(longAlt);
    expect(allele).toHaveClass('variant-allele-value');
    expect(allele.textContent?.length).toBeLessThan(longAlt.length);
    expect(allele.closest('td')).toHaveClass('variant-allele-cell');
    expect(allele.closest('table')).toHaveClass('small-variant-table');
  });
});

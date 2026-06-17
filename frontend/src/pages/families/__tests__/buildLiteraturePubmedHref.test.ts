import { describe, expect, it } from 'vitest';

import { buildLiteraturePubmedHref } from '../smallVariantResultUtils';

function decodeTerm(href: string): string {
  const term = new URL(href).searchParams.get('term') ?? '';
  return term;
}

describe('buildLiteraturePubmedHref', () => {
  it('returns null without a gene', () => {
    expect(buildLiteraturePubmedHref({ gene: '' })).toBeNull();
  });

  it('anchors on the gene and ORs the protein change', () => {
    const href = buildLiteraturePubmedHref({ gene: 'SCN1A', proteinChange: 'p.Arg100Ter' })!;
    expect(decodeTerm(href)).toBe('(SCN1A OR p.Arg100Ter)');
  });

  it('ANDs an OR group of quoted HPO phenotype terms', () => {
    const href = buildLiteraturePubmedHref({
      gene: 'SCN1A',
      hpoLabels: ['Seizure', 'Intellectual disability', 'Seizure'],
    })!;
    expect(decodeTerm(href)).toBe('SCN1A AND ("Seizure" OR "Intellectual disability")');
  });
});

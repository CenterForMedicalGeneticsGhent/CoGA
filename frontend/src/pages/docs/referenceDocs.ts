// In-depth reference docs, authored as Markdown and bundled so they render in-app
// (the repository is private, so external links to the .md files are not usable).
// Add a new doc by dropping a .md under src/content/docs and registering it here.
import sampleQc from '../../content/docs/sample-qc.md?raw';

export interface ReferenceDoc {
  slug: string;
  title: string;
  summary: string;
  markdown: string;
}

export const referenceDocs: ReferenceDoc[] = [
  {
    slug: 'sample-qc',
    title: 'Sample-integrity QC',
    summary:
      'Application-aware sample QC: sex, relatedness / consanguinity, Mendelian-error rate, and the monogenic-NIPT cfDNA checks — with thresholds and data sources.',
    markdown: sampleQc,
  },
];

export const referenceDocBySlug = new Map(referenceDocs.map((doc) => [doc.slug, doc]));

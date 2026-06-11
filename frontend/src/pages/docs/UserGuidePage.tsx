import React from 'react';
import { Link } from 'react-router-dom';

type GuideHighlight = {
  title: string;
  description: string;
};

type GuideLink = {
  label: string;
  to: string;
  note?: string;
};

type GuideSection = {
  id: string;
  title: string;
  summary: string;
  quickLinks?: GuideLink[];
  content: React.ReactNode;
};

const guideHighlights: GuideHighlight[] = [
  {
    title: 'Phenotype-driven, family-based review',
    description:
      'Start from the pedigree and the patient phenotype (HPO), then prioritise variants in the context of the whole family rather than isolated files.',
  },
  {
    title: 'Inheritance-aware prioritisation',
    description:
      'Apply de novo / dominant, recessive (homozygous and compound heterozygous), X-linked, and carrier-screening logic to small-variant searches.',
  },
  {
    title: 'Evidence-rich interpretation',
    description:
      'See ClinVar, gnomAD frequencies, CADD / REVEL / SpliceAI, and MANE / canonical transcript context next to each candidate, then record an ACMG class, tags, and notes.',
  },
  {
    title: 'Cohort and internal-frequency context',
    description:
      'Use the Global Small Variant Explorer to ask how often a variant or gene is seen across every project you can access, and which families carry it.',
  },
  {
    title: 'Multi-assay genomic review',
    description:
      'Bring small variants, structural variants, repeat expansions (TRGT), Paraphase, mitochondrial DNA, coverage, and IGV together for one family.',
  },
  {
    title: 'Reusable, auditable review state',
    description:
      'Classifications, tags, notes, and filter presets persist across sessions and analysts, and administrative actions are captured in audit logs.',
  },
];

const guideSections: GuideSection[] = [
  {
    id: 'orientation',
    title: 'How CoGA is organised',
    summary:
      'Understand the scoped data model — projects, families, samples, assemblies, and review state — before you start interpreting.',
    quickLinks: [
      { label: 'Dashboard', to: '/dashboard', note: 'Start here' },
      { label: 'Families', to: '/families', note: 'Case catalog' },
    ],
    content: (
      <>
        <p>
          CoGA is an integrated review environment for clinical genomics. Like other family-based
          platforms, it keeps the pedigree, the assay layers, and your interpretation together so a
          case is reviewed as a whole rather than as a pile of files. Almost everything you do is
          scoped: getting the scope right is what makes the rest of the system behave predictably.
        </p>
        <div className="user-guide-callout">
          <strong>Mental model:</strong> a <em>project</em> controls access and assembly, a
          <em> family</em> is the case, <em>samples</em> carry the assay data, and
          <em> review state</em> (classifications, tags, notes) is the interpretation layer on top.
        </div>

        <h3>The objects you work with</h3>
        <ul>
          <li>
            <strong>Projects</strong> define who can see the data and which reference assembly
            applies. Your access — and every cohort count you see — is scoped to the projects you
            belong to (administrators see everything).
          </li>
          <li>
            <strong>Families</strong> are the unit of case review. They group related samples and
            carry pedigree meaning (relationships, roles, affected status).
          </li>
          <li>
            <strong>Samples</strong> hold per-sample assay layers: genotypes, coverage, segments,
            repeat expansions, Paraphase, and more.
          </li>
          <li>
            <strong>Reference data</strong> (genes, transcripts, cytobands, ClinVar, gnomAD,
            blacklist, clinical CNVs) is assembly-scoped and shared across projects on that assembly.
          </li>
          <li>
            <strong>Review state</strong> — ACMG classifications, tags, notes, and saved filter
            presets — is layered on top of the raw data and is what survives between sessions.
          </li>
        </ul>

        <h3>The analyst journey</h3>
        <ol>
          <li>Confirm the project, assembly, and family.</li>
          <li>Capture or review the phenotype (HPO terms) and the pedigree.</li>
          <li>Prioritise candidates with inheritance-aware, evidence-rich filtering.</li>
          <li>Interpret each candidate and record an ACMG class, tags, and notes.</li>
          <li>Put findings in cohort context and follow up visually (genome views, IGV).</li>
        </ol>
      </>
    ),
  },
  {
    id: 'quick-start',
    title: 'Quick start',
    summary: 'Two common entry points: open an existing case, or set up a new one.',
    quickLinks: [
      { label: 'Dashboard', to: '/dashboard', note: 'Search' },
      { label: 'Family Builder', to: '/family-builder', note: 'New case' },
      { label: 'Package Import', to: '/package-import', note: 'Bulk import' },
      { label: 'Gene explorer', to: '/genes', note: 'Locus-first' },
      { label: 'Variant explorer', to: '/variant-explorer', note: 'Cross-cohort' },
    ],
    content: (
      <>
        <h3>Reviewing an existing case</h3>
        <ol>
          <li>From the dashboard, search by project, family ID, or sample ID.</li>
          <li>Open the family to land on its workspace.</li>
          <li>
            Pick the analysis that matches the question — small variants, structural variants,
            repeats, and so on. Buttons appear only for data types the family actually has.
          </li>
          <li>Build a candidate shortlist in the variant table before opening dense viewers.</li>
          <li>Record interpretation as you go with classifications, tags, and notes.</li>
        </ol>

        <h3>Setting up a new case</h3>
        <ol>
          <li>Confirm (or create) the target project and its assembly.</li>
          <li>
            Build the family and samples in <strong>Family Builder</strong>, or bulk-import a
            prepared folder package via <strong>Package Import</strong> (admin).
          </li>
          <li>Import or attach the assay layers for the family.</li>
          <li>Open the family workspace to confirm the expected tables and tracks appear.</li>
        </ol>

        <div className="user-guide-callout">
          <strong>Not finding a variant you expect?</strong> The most common causes are the wrong
          project/assembly, a frequency or quality filter that is too strict, or imputed calls being
          hidden. Clear filters and re-check scope before assuming the data is missing.
        </div>
      </>
    ),
  },
  {
    id: 'case-setup',
    title: 'Case setup and data import',
    summary:
      'Create families and samples, import data packages, and understand what each assay layer unlocks.',
    quickLinks: [
      { label: 'Family Builder', to: '/family-builder', note: 'Manual pedigree' },
      { label: 'Package Import', to: '/package-import', note: 'Folder packages' },
      { label: 'Upload sample data', to: '/upload-data', note: 'Assays' },
      { label: 'Reference data', to: '/reference-data', note: 'Assembly layers' },
    ],
    content: (
      <>
        <p>
          Intake is split into two focused pages. Use whichever matches how your data arrives.
        </p>
        <div className="user-guide-mini-grid">
          <div className="user-guide-mini-card">
            <p className="user-guide-mini-card-title">Family Builder</p>
            <p className="user-guide-mini-card-copy">
              Build a pedigree by hand or from a PED file: add samples, set sex and roles, assign
              parents and couples, and set phenotype and carrier status. Available to all users.
            </p>
          </div>
          <div className="user-guide-mini-card">
            <p className="user-guide-mini-card-title">Package Import</p>
            <p className="user-guide-mini-card-copy">
              Admins point at a backend-visible folder, discover a manifest, run a dry-run
              validation, then import the family and all of its assay layers in one job.
            </p>
          </div>
        </div>

        <h3>What each data type unlocks</h3>
        <ul>
          <li><strong>Small variants (SNV/indel)</strong> enable the small-variant workbench and review.</li>
          <li><strong>Structural variants</strong> enable the SV table, review, and CNV detail.</li>
          <li><strong>Repeat expansions (TRGT)</strong> enable the repeat-expansion view.</li>
          <li><strong>Paraphase</strong> enables segmental-duplication / paralogue resolution.</li>
          <li><strong>Mitochondrial calls</strong> enable the mtDNA heteroplasmy analysis.</li>
          <li><strong>Coverage, segments, APCAD, haplotypes</strong> populate the genome and chromosome track viewers.</li>
        </ul>

        <div className="user-guide-callout">
          <strong>Assembly and reference first.</strong> Genes, cytobands, ClinVar, and gnomAD are
          loaded per assembly. If a viewer cannot resolve coordinates or a gene lookup is empty, check
          that the reference layers for that assembly are present.
        </div>
      </>
    ),
  },
  {
    id: 'phenotypes-and-panels',
    title: 'Phenotypes and gene panels',
    summary:
      'Anchor interpretation in the patient phenotype with HPO, and constrain searches with reusable gene panels.',
    quickLinks: [
      { label: 'HPO browser', to: '/hpo', note: 'Phenotype terms' },
      { label: 'Panel catalog', to: '/panels', note: 'Gene sets' },
    ],
    content: (
      <>
        <p>
          Phenotype-led analysis is central to modern interpretation. Capture the patient&apos;s
          clinical features as HPO terms and curate gene sets so the same prioritisation can be
          reused across cases.
        </p>

        <h3>HPO phenotypes</h3>
        <ul>
          <li>Browse and search the HPO ontology from the HPO page.</li>
          <li>
            Annotate individuals with HPO terms in the family workspace; phenotype annotations are
            stored per individual and travel with the family.
          </li>
          <li>Use the phenotype to decide which genes and inheritance models to prioritise.</li>
        </ul>

        <h3>Gene panels</h3>
        <ul>
          <li>The panel catalog holds reusable gene lists for recurring indications.</li>
          <li>
            Apply a panel directly in the small-variant filter to restrict a search to a curated set
            of genes — a fast way to focus a broad genome on the clinically relevant loci.
          </li>
          <li>Panels are managed centrally so a team shares the same definitions.</li>
        </ul>
      </>
    ),
  },
  {
    id: 'family-workspace',
    title: 'The family workspace',
    summary:
      'The case dashboard: pedigree, review summaries, an editable region of interest, and one entry point per analysis.',
    quickLinks: [{ label: 'Families', to: '/families', note: 'Open a family' }],
    content: (
      <>
        <p>
          The family page is the hub of interpretation. It shows the pedigree, curation summaries,
          and a set of analysis buttons that link out to each review surface.
        </p>

        <h3>What you will find there</h3>
        <ul>
          <li>
            <strong>Analysis buttons that reflect the data.</strong> Small variants, structural
            variants, variant summary, repeat expansions, Paraphase, and mtDNA only appear when that
            data type is actually loaded for the family — so an empty button never sends you to an
            empty page.
          </li>
          <li>
            <strong>Visualisation buttons</strong> for the genome overview, chromosome view, Circos
            plot, and IGV.
          </li>
          <li>
            <strong>Review summaries</strong> for small and structural variants: how many are
            reviewed, noted, and tagged.
          </li>
          <li>
            <strong>Region of interest (ROI).</strong> Admins can set a gene or locus of interest
            directly from the family dashboard and open it in the chromosome view.
          </li>
        </ul>

        <h3>Pedigree and member management</h3>
        <p>
          Sex, role, parentage, phenotype, and carrier status are edited per member. Phenotype
          (clinical status: unknown / unaffected / affected) and carrier status (unknown / carrier /
          non-carrier) are <strong>independent axes</strong> — an individual can be both affected and
          a carrier — and are set with separate controls. These edits are metadata-only: they update
          the pedigree and mark phenotype-dependent views as needing recomputation, but they never
          delete or reimport raw data.
        </p>
      </>
    ),
  },
  {
    id: 'small-variant-filtering',
    title: 'Small-variant prioritisation',
    summary:
      'The filter workbench: location, inheritance, consequence, ClinVar, frequency, in-silico scores, transcripts, and tags — with reusable presets.',
    quickLinks: [{ label: 'Families', to: '/families', note: 'Per-family search' }],
    content: (
      <>
        <p>
          The small-variant page is where most candidate-finding happens. Filters are grouped so you
          can move from a broad genome to a short candidate list quickly, then save the recipe as a
          preset.
        </p>

        <h3>Filter dimensions</h3>
        <ul>
          <li><strong>Location</strong> — gene symbols, genomic regions/intervals, or a gene panel.</li>
          <li>
            <strong>Inheritance</strong> — de novo / dominant, recessive (homozygous), compound
            heterozygous, and X-linked models, plus expanded carrier screening for couples.
          </li>
          <li><strong>Variant type</strong> — SNV, indel, or MNV.</li>
          <li>
            <strong>Consequence and impact</strong> — HIGH / MODERATE / LOW / MODIFIER and specific
            effects (missense, frameshift, stop gained, splice, and so on).
          </li>
          <li>
            <strong>ClinVar and classification</strong> — pathogenic through benign, conflicting
            interpretations, and your own ACMG classifications.
          </li>
          <li>
            <strong>Population frequency</strong> — gnomAD exomes/genomes/popmax and TOPMed
            allele frequencies, allele counts, and homozygote/hemizygote caps.
          </li>
          <li>
            <strong>In-silico evidence</strong> — CADD, REVEL, SpliceAI, SIFT, and PolyPhen
            thresholds.
          </li>
          <li>
            <strong>Transcript scope</strong> — restrict to canonical, MANE, or loss-of-function
            transcripts.
          </li>
          <li><strong>Tags and notes</strong> — include or exclude review tags, or require notes.</li>
        </ul>

        <h3>Compound heterozygotes and per-sample genotypes</h3>
        <p>
          Compound-heterozygous candidates are grouped as pairs so you can assess both hits in a gene
          together. Per-sample genotype and quality thresholds (genotype, QUAL, DP, AF, AD) let you
          encode segregation expectations across the family directly in the search.
        </p>

        <div className="user-guide-callout">
          <strong>Presets save the recipe, not the result.</strong> Built-in presets cover common
          patterns (dominant, recessive, compound het, carrier screening, ClinVar review); save your
          own to standardise how your team searches.
        </div>
      </>
    ),
  },
  {
    id: 'interpretation-and-review',
    title: 'Interpretation and review state',
    summary:
      'Record an ACMG classification, tags, and notes per variant, and keep that review state consistent across the team.',
    content: (
      <>
        <p>
          Once a candidate is in focus, open its review dialog to record an interpretation. Review
          state is stored per family and is what makes a case auditable and resumable.
        </p>

        <h3>What you can record</h3>
        <ul>
          <li>
            <strong>ACMG classification</strong> — benign, likely benign, VUS, likely pathogenic, or
            pathogenic (classes 1–5).
          </li>
          <li>
            <strong>Tags</strong> — collaboration tags (e.g. for review, send for validation,
            validated, excluded), classification tags, and project- or globally-defined custom tags.
            Tags are how you flag reported, candidate, research, or solved variants.
          </li>
          <li><strong>Notes</strong> — free-text rationale that stays attached to the variant.</li>
        </ul>

        <h3>Evidence at hand</h3>
        <p>
          Each variant row surfaces the context you need to classify: gene and consequence, the most
          relevant transcript, ClinVar status, population frequency, and in-silico scores. Use the
          Gene Explorer for deeper gene-level context and the Variant Explorer for cohort context.
        </p>

        <h3>Structural-variant review</h3>
        <p>
          Structural variants have their own review surface with the same idea: classify, tag, and
          note, with a dedicated tag for segmentation review. SV and small-variant review state are
          tracked separately and summarised on the family page.
        </p>

        <div className="user-guide-callout">
          <strong>Review state is scoped to the family</strong> and preserved through metadata edits.
          The same variant interpreted in two families carries two independent review records — which
          is exactly what the cohort views aggregate.
        </div>
      </>
    ),
  },
  {
    id: 'specialised-analyses',
    title: 'Structural variants, repeats, Paraphase, and mtDNA',
    summary:
      'Specialised review surfaces for events that small-variant tables do not capture.',
    quickLinks: [{ label: 'Families', to: '/families', note: 'Open a family' }],
    content: (
      <>
        <div className="user-guide-mini-grid">
          <div className="user-guide-mini-card">
            <p className="user-guide-mini-card-title">Structural variants</p>
            <p className="user-guide-mini-card-copy">
              Review CNVs and other SVs with genotype context, classification, and tagging; jump to
              CNV detail and the genome/Circos views for breakpoint context.
            </p>
          </div>
          <div className="user-guide-mini-card">
            <p className="user-guide-mini-card-title">Repeat expansions (TRGT)</p>
            <p className="user-guide-mini-card-copy">
              Inspect per-sample repeat-locus calls against the catalog to assess expansions in the
              family.
            </p>
          </div>
          <div className="user-guide-mini-card">
            <p className="user-guide-mini-card-title">Paraphase</p>
            <p className="user-guide-mini-card-copy">
              Resolve paralogous / segmental-duplication regions where standard short-read calling is
              unreliable.
            </p>
          </div>
          <div className="user-guide-mini-card">
            <p className="user-guide-mini-card-title">Mitochondrial DNA</p>
            <p className="user-guide-mini-card-copy">
              Review mtDNA variants with heteroplasmy and homoplasmy thresholds and per-sample
              coverage.
            </p>
          </div>
        </div>
        <p>
          A combined <strong>variant summary</strong> view rolls up small and structural variant
          counts for the family when you want a single overview before diving into a specific table.
        </p>
      </>
    ),
  },
  {
    id: 'visualization',
    title: 'Genome visualisation and follow-up',
    summary:
      'Move from a candidate row into whole-genome, per-chromosome, Circos, and IGV views.',
    quickLinks: [{ label: 'Families', to: '/families', note: 'Viewers live per family' }],
    content: (
      <>
        <p>
          Tables are for finding candidates; viewers are for confirming them. Each viewer reads the
          tracks that were imported for the family.
        </p>
        <ul>
          <li><strong>Genome overview</strong> — whole-genome context for variants and tracks.</li>
          <li>
            <strong>Chromosome view</strong> — a single chromosome with coverage, segments, and
            variant tracks; the ROI opens here with flanking context.
          </li>
          <li><strong>Circos plot</strong> — genome-wide structural relationships at a glance.</li>
          <li>
            <strong>IGV</strong> — read-level confirmation against the reference for a specific
            locus.
          </li>
          <li><strong>CNV detail</strong> — focused inspection of a structural event.</li>
        </ul>
        <div className="user-guide-callout">
          <strong>Viewers only show what was imported.</strong> Coverage, segment, APCAD, and
          haplotype tracks appear when the corresponding sample data exists; an empty track usually
          means that layer was not loaded, not that the viewer failed.
        </div>
      </>
    ),
  },
  {
    id: 'gene-explorer',
    title: 'Gene Explorer',
    summary:
      'A locus-first gene profile: transcript overview with clinical badges, constraint metrics, and disease associations.',
    quickLinks: [{ label: 'Gene explorer', to: '/genes', note: 'Search a gene' }],
    content: (
      <>
        <p>
          When the question is about a gene rather than a single case, the Gene Explorer gives a
          consolidated profile, similar to the gene pages in dedicated interpretation platforms.
        </p>
        <h3>Transcript overview</h3>
        <p>
          The transcript table badges the clinically relevant transcripts so you can pick the right
          one at a glance:
        </p>
        <ul>
          <li><strong>MANE Select</strong> — the agreed default clinical transcript.</li>
          <li><strong>MANE Plus Clinical</strong> — additional transcripts needed for clinical reporting.</li>
          <li><strong>RefSeq Select</strong> — the representative RefSeq transcript.</li>
          <li><strong>Ensembl Canonical</strong> — the Ensembl canonical transcript.</li>
        </ul>
        <h3>Gene-level context</h3>
        <ul>
          <li>Constraint metrics (e.g. pLI, LOEUF, missense constraint) for dosage sensitivity.</li>
          <li>Disease and phenotype associations, ClinGen / GenCC evidence, and OMIM links.</li>
          <li>External links out to the major knowledge resources for the gene.</li>
        </ul>
      </>
    ),
  },
  {
    id: 'variant-explorer',
    title: 'Global Small Variant Explorer',
    summary:
      'A variant-centric, cross-project view: how often a variant occurs, in which families, and with what review state.',
    quickLinks: [{ label: 'Variant explorer', to: '/variant-explorer', note: 'Cross-cohort' }],
    content: (
      <>
        <p>
          The variant explorer answers cohort-level questions that a single family cannot:
          <em> in how many samples does this pathogenic variant occur? which families carry a variant
          in this gene? which reported variants exist across the database?</em> Each row is a unique
          variant aggregated across every project you can access.
        </p>
        <h3>What each row shows</h3>
        <ul>
          <li>Gene, variant, consequence, most-severe classification, and aggregated tags.</li>
          <li>
            Total carrier samples with a heterozygous / homozygous split, and the number of distinct
            families.
          </li>
        </ul>
        <h3>How you use it</h3>
        <ul>
          <li>
            Filter with the same dimensions as the family search — gene, consequence, ClinVar,
            frequency, in-silico — plus tags and ACMG classification to surface, for example, every
            variant tagged <em>Reported</em>.
          </li>
          <li>
            Click a heterozygous, homozygous, or family count to drill into the carriers, grouped by
            family, and link straight to the family workspace.
          </li>
          <li>Optionally add a per-sample genotype filter to find variants a specific sample carries.</li>
          <li>Switch the assembly, and choose whether imputed calls are included.</li>
        </ul>
        <div className="user-guide-callout">
          <strong>Counts are relative to your access.</strong> Aggregations only span the projects
          you can see, so internal-frequency context reflects your accessible cohort.
        </div>
      </>
    ),
  },
  {
    id: 'administration',
    title: 'Administration',
    summary:
      'Projects and access, data management, reference sync, storage maintenance, tag/preset configuration, and audit logs.',
    quickLinks: [
      { label: 'Data management', to: '/admin/data', note: 'Families & uploads' },
      { label: 'Projects', to: '/projects', note: 'Access' },
      { label: 'Users', to: '/admin/users', note: 'Accounts' },
      { label: 'Gene reference sync', to: '/admin/gene-reference', note: 'Reference' },
      { label: 'Audit logs', to: '/admin/monitoring/audit-logs', note: 'Activity' },
    ],
    content: (
      <>
        <p>
          Administrative tooling lives behind admin access and keeps the platform healthy and
          governed.
        </p>
        <ul>
          <li>
            <strong>Projects and access</strong> — define projects, their assembly, and which users
            can see them. Access here is what scopes every query and cohort count.
          </li>
          <li>
            <strong>Data management</strong> — inventory families and samples, run imports, and
            handle deletion workflows.
          </li>
          <li>
            <strong>Reference and gene sync</strong> — manage assemblies and reference layers and
            queue gene-reference refreshes.
          </li>
          <li>
            <strong>Storage maintenance</strong> — inspect and repair the per-assembly ClickHouse
            variant tables (ensure / optimise).
          </li>
          <li>
            <strong>Tags and presets</strong> — define the variant tags and shared filter presets
            your team relies on.
          </li>
          <li>
            <strong>Audit logs</strong> — review who changed what, when.
          </li>
        </ul>
        <p>
          Display preferences live on the <Link to="/settings">Settings</Link> page; release notes
          are on the <Link to="/new-features">New features</Link> page.
        </p>
      </>
    ),
  },
  {
    id: 'glossary',
    title: 'Glossary',
    summary: 'Quick definitions for the terms used throughout CoGA.',
    content: (
      <>
        <ul>
          <li><strong>Assembly</strong> — the reference genome build (e.g. GRCh38) a project uses.</li>
          <li><strong>ROI</strong> — region of interest: a gene or locus pinned to a family.</li>
          <li>
            <strong>ACMG class</strong> — five-tier variant classification: benign, likely benign,
            VUS, likely pathogenic, pathogenic.
          </li>
          <li><strong>ClinVar</strong> — public archive of variant–condition interpretations.</li>
          <li><strong>gnomAD / TOPMed</strong> — population allele-frequency references.</li>
          <li>
            <strong>CADD / REVEL / SpliceAI / SIFT / PolyPhen</strong> — in-silico predictors of
            deleteriousness or splicing impact.
          </li>
          <li>
            <strong>MANE Select / MANE Plus Clinical</strong> — agreed reference transcripts for
            clinical reporting; <strong>RefSeq Select</strong> and <strong>Ensembl Canonical</strong>
            {' '}are the representative transcripts from each database.
          </li>
          <li><strong>Compound heterozygous</strong> — two different variants in one gene, one per allele.</li>
          <li><strong>TRGT</strong> — tandem-repeat genotyping used for repeat-expansion calls.</li>
          <li><strong>Paraphase</strong> — caller for paralogous / segmental-duplication regions.</li>
          <li><strong>Heteroplasmy</strong> — the fraction of mitochondrial genomes carrying a variant.</li>
          <li>
            <strong>Carrier vs phenotype</strong> — carrier status describes genotype; phenotype
            (clinical status) describes the individual. They are tracked independently.
          </li>
        </ul>
      </>
    ),
  },
];

const formatSectionIndex = (index: number) => String(index + 1).padStart(2, '0');

const WorkspaceLinkRow: React.FC<{ links: GuideLink[] }> = ({ links }) => (
  <div className="user-guide-link-row">
    {links.map((link) => (
      <Link key={`${link.to}:${link.label}`} to={link.to} className="user-guide-link-chip">
        <span>{link.label}</span>
        {link.note ? <span className="user-guide-link-note">{link.note}</span> : null}
      </Link>
    ))}
  </div>
);

const UserGuidePage: React.FC = () => (
  <div className="page-shell content-shell user-guide-page">
    <header className="user-guide-hero">
      <p className="page-kicker">Documentation</p>
      <h1 className="user-guide-title">CoGA user guide</h1>
      <p className="user-guide-lede">
        An in-app manual for analysts and administrators. It follows the clinical-genomics workflow
        — orient, capture phenotype, prioritise, interpret, put in cohort context, and visualise —
        and maps each step to the page that does the job.
      </p>
    </header>

    <section className="user-guide-highlights" aria-label="Capabilities">
      <p className="user-guide-eyebrow">What you can do in CoGA</p>
      <div className="user-guide-highlight-grid">
        {guideHighlights.map((highlight) => (
          <div key={highlight.title} className="user-guide-highlight">
            <p className="user-guide-highlight-title">{highlight.title}</p>
            <p className="user-guide-highlight-copy">{highlight.description}</p>
          </div>
        ))}
      </div>
    </section>

    <div className="user-guide-layout">
      <aside id="user-guide-contents" className="user-guide-toc">
        <p className="user-guide-eyebrow">On this page</p>
        <nav aria-label="User guide contents">
          <ol className="user-guide-toc-list">
            {guideSections.map((section, index) => (
              <li key={section.id}>
                <a href={`#${section.id}`} className="user-guide-toc-link">
                  <span className="user-guide-toc-index">{formatSectionIndex(index)}</span>
                  <span className="user-guide-toc-title">{section.title}</span>
                </a>
              </li>
            ))}
          </ol>
        </nav>
      </aside>

      <div className="user-guide-content">
        {guideSections.map((section, index) => (
          <section key={section.id} id={section.id} className="user-guide-section">
            <div className="user-guide-section-header">
              <span className="user-guide-section-index">{formatSectionIndex(index)}</span>
              <h2 className="user-guide-section-title">{section.title}</h2>
              <p className="user-guide-section-summary">{section.summary}</p>
            </div>
            {section.quickLinks?.length ? <WorkspaceLinkRow links={section.quickLinks} /> : null}
            <div className="content-prose user-guide-section-prose">{section.content}</div>
            <a href="#user-guide-contents" className="subtle-link user-guide-backlink">
              Back to top
            </a>
          </section>
        ))}
      </div>
    </div>
  </div>
);

export default UserGuidePage;

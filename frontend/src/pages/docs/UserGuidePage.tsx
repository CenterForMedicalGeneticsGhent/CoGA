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
    title: 'Phenotype-driven, family-based analysis',
    description:
      'Start from the pedigree and the patient phenotype (HPO), then prioritise variants in the context of the whole family.',
  },
  {
    title: 'Inheritance-aware prioritisation',
    description:
      'Apply de novo / dominant, recessive (homozygous and compound heterozygous), X-linked, and carrier-screening logic to variant searches.',
  },
  {
    title: 'Phenotype matching and automatic ranking',
    description:
      'Match the patient’s HPO phenotypes to genes and diseases through the Monarch Initiative knowledge graph, and rank a family’s variants with an Exomiser-style score that blends phenotype fit, impact, rarity, and segregation.',
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
    title: 'Comprehensive genomic review',
    description:
      'Bring small variants, structural variants, repeat expansions (TRGT), Paraphase, and mitochondrial DNA together for one family.',
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
          CoGA is an integrated review environment for clinical genomic analysis. Like other family-based
          platforms, it keeps the pedigree, the assay layers, and your interpretation together so a
          case is reviewed as a whole rather than as a set of disconnected tests.
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
            blacklist, clinical CNVs, DGV) is assembly-scoped and shared across projects on that assembly.
          </li>
          <li>
            <strong>Review state</strong> — ACMG classifications, tags, notes, and saved filter
            presets — is layered on top of the raw data and is what survives between sessions.
          </li>
        </ul>

        <h3>The analyst journey</h3>
        <ol>
          <li>Search for families, cases, or individuals through the dashboard.</li>
          <li>Capture or review the pedigree and associated phenotype (HPO terms).</li>
          <li>Examine small variants, structural variants, recombinations, mtDNA variants, (triplet) repeat expansions, and complex genomic regions through one family-based workspace.</li>
          <li>Prioritise candidates with inheritance-aware, evidence-rich filtering.</li>
          <li>Interpret each candidate and record an ACMG class, tags, and notes.</li>
          <li>Put findings in cohort context and follow up visually (genome views, IGV).</li>
          <li>Automatically report interesting variants.</li>
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
          <strong>Not finding a variant you expect?</strong> The most common causes are a frequency or quality filter that is too strict, or imputed calls being
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
          <li><strong>Mitochondrial calls</strong> enable the mtDNA homo- and heteroplasmy analysis.</li>
          <li><strong>Coverage, segments, APCAD, haplotypes, and recombination</strong> populate the genome and chromosome track viewers.</li>
        </ul>

        <div className="user-guide-callout">
          <strong>Assembly and reference first.</strong> Genes, cytobands, ClinVar, DGV, and gnomAD annotations are
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
          <li>The gene panel catalog holds reusable gene lists for recurring indications.</li>
          <li>
            Apply a panel directly in the small-variant or structural-variant filter to restrict a search to a curated set
            of genes — a fast way to focus a broad genome on the clinically relevant loci.
          </li>
          <li>Panels can be imported automatically from PanelApp or custom-made, and are managed centrally so a team shares the same definitions.</li>
        </ul>
      </>
    ),
  },
  {
    id: 'phenotype-matching',
    title: 'Phenotype matching (Monarch Initiative)',
    summary:
      'Connect the patient’s HPO phenotypes to genes and diseases through the Monarch knowledge graph — on the gene profile and as a ranked “candidate genes” panel in the family.',
    quickLinks: [
      { label: 'Gene explorer', to: '/genes', note: 'Gene–disease & phenotypes' },
      { label: 'Families', to: '/families', note: 'Candidate-gene panel' },
    ],
    content: (
      <>
        <p>
          CoGA integrates the{' '}
          <a href="https://monarchinitiative.org/" target="_blank" rel="noreferrer">
            Monarch Initiative
          </a>{' '}
          knowledge graph, which links <strong>genes ↔ diseases ↔ HPO phenotypes</strong> from
          curated sources (OMIM, ClinGen, Orphanet, and the Human Phenotype Ontology Annotations).
          This turns the patient’s recorded phenotype into an active signal: it tells you which genes
          and diseases are phenotypically relevant, and it powers the automatic variant ranking
          described in the next section.
        </p>
        <div className="user-guide-callout">
          <strong>The loop in one sentence.</strong> Observed phenotypes → candidate genes → each
          gene’s diseases → which of the patient’s phenotypes those diseases explain → ranked
          variants.
        </div>

        <h3>On the gene profile</h3>
        <p>The Gene Explorer profile gains two phenotype-aware blocks:</p>
        <ul>
          <li>
            <strong>Monarch gene–disease associations</strong> — the curated diseases linked to the
            gene, each labelled with the relationship (<em>causes</em>, <em>associated</em>,{' '}
            <em>contributes&nbsp;to</em>) and its source(s), and linking out to the Monarch page for
            the disease. Causal associations are listed first.
          </li>
          <li>
            <strong>Expected phenotypes and patient overlap</strong> — each disease carries the HPO
            phenotypes expected for it. When you open a gene <em>in the context of a family</em>{' '}
            (for example by clicking a gene from a variant), CoGA highlights the expected phenotypes
            the family actually exhibits. Matching is <strong>ancestor-aware</strong>: a patient’s
            specific term (e.g. a particular seizure type) still matches a disease’s more general
            expected term (e.g. <em>Seizure</em>) through the HPO hierarchy.
          </li>
        </ul>

        <h3>In the family: ranked candidate genes</h3>
        <p>
          The family workspace has a <strong>Phenotype match (Monarch)</strong> panel. Press{' '}
          <em>Find candidate genes</em> and CoGA sends the affected individuals’ observed HPO terms
          to Monarch’s semantic-similarity service, which returns a list of genes ranked by how well
          their phenotype profile matches the patient. Genes that exist in your platform link
          straight to the gene profile (where the gene–disease and overlap blocks above are waiting),
          so you can move from “these phenotypes” to “this gene” to “this variant” without leaving
          the case.
        </p>
        <div className="user-guide-callout">
          <strong>It runs on demand.</strong> The candidate-gene panel calls Monarch only when you
          press the button, so it never slows down opening a family. Results are cached briefly.
        </div>

        <h3>Where the data comes from</h3>
        <p>
          The gene–disease and disease–phenotype tables are loaded by an administrator from the
          monthly Monarch release (see <a href="#administration">Administration</a>); the
          candidate-gene panel is a live call to Monarch. If the tables have not been loaded yet, the
          profile blocks show an empty state rather than an error.
        </p>
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
            <strong>Region of interest (ROI).</strong> Users can set a gene or locus of interest
            directly from the family dashboard and open it in the chromosome view.
          </li>
        </ul>

        <h3>Pedigree and member management</h3>
        <p>
          Sex, role, parentage, phenotype, and carrier status are edited per member. Phenotype
          (clinical status: unknown / unaffected / affected) and carrier status (unknown / carrier /
          non-carrier) are <strong>independent axes</strong> — an individual can be unaffected but
          still a carrier — and are set with separate controls. These edits are metadata-only: they update
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
            thresholds, amongst others.
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

        <h3>Bi-sample partner analysis</h3>
        <p>
          A special case is the coupled partner analysis — a dedicated filter for (expanded) preconception
          carrier screening. Only genes where both partners carry a variant meeting the filter criteria are returned.
        </p>

        <div className="user-guide-callout">
          <strong>Presets save the recipe, not the result.</strong> Built-in presets cover common
          patterns (dominant, recessive, compound het, carrier screening, ClinVar review, and{' '}
          <em>phenotype priority</em> — see the next section); save your own to standardise variant
          filtration.
        </div>
      </>
    ),
  },
  {
    id: 'variant-prioritisation',
    title: 'Phenotype-driven variant prioritisation (Exomiser-style)',
    summary:
      'One click ranks a family’s rare, impactful, segregating variants by how well each gene matches the patient’s phenotypes — with a transparent, explainable score.',
    quickLinks: [{ label: 'Families', to: '/families', note: 'Apply the preset' }],
    content: (
      <>
        <p>
          Filtering narrows the genome to a candidate list; prioritisation puts that list in order.
          The <strong>Phenotype priority (Exomiser-style)</strong> preset combines the Monarch
          phenotype signal with the usual variant evidence to rank candidates the way tools such as
          Exomiser do — so the most likely causal variant tends to rise to the top instead of being
          buried in a long, position-sorted list.
        </p>

        <h3>Turning it on</h3>
        <p>
          Apply the <strong>Phenotype priority (Exomiser-style)</strong> preset. It sets a sensible
          starting point — rare (gnomAD popmax &lt; 0.1%) and HIGH/MODERATE impact — and switches the
          result list into ranked mode. A <strong>Score</strong> column appears (sortable), the rows
          come back ordered best-first, and a small <span aria-hidden>✦</span> marks variants whose
          gene matches the patient’s phenotypes. You can still adjust any filter; prioritisation
          re-ranks whatever passes.
        </p>

        <h3>What the score blends</h3>
        <p>Each variant gets a single priority score in <code>[0, 1]</code> built from four parts:</p>
        <ul>
          <li>
            <strong>Pathogenicity</strong> — variant impact and loss-of-function, ClinVar
            assertions (a pathogenic ClinVar record dominates), and the in-silico predictors
            (CADD, REVEL, SpliceAI, and AlphaMissense). Gene constraint (gnomAD pLI for
            loss-of-function, missense-Z for missense) raises confidence for the relevant variant
            class.
          </li>
          <li>
            <strong>Rarity</strong> — rarer variants score higher, using the gnomAD population-max
            frequency.
          </li>
          <li>
            <strong>Segregation</strong> — whether the variant fits an inheritance pattern in the
            pedigree (see below).
          </li>
          <li>
            <strong>Phenotype fit</strong> — how well the gene’s Monarch phenotype profile matches
            the affected individuals’ HPO, computed locally with a Phenomizer-style
            information-content similarity (rarer, more specific shared phenotypes count more).
          </li>
        </ul>
        <p>
          Pathogenicity, rarity, and segregation form a <em>variant score</em>; phenotype fit then{' '}
          <strong>reorders</strong> candidates so a gene that matches the patient can rise above an
          equally damaging variant in an unrelated gene. Genes Monarch knows nothing about are not
          penalised on the variant axis — their raw variant score is shown separately, so a strong
          candidate in a novel gene stays findable (sort by the variant score to surface them).
        </p>

        <h3>Segregation modes</h3>
        <p>Using the pedigree (affected status, sex, and parent–child links), each variant is tagged with the inheritance patterns it is compatible with:</p>
        <ul>
          <li>
            <strong>De novo</strong> — heterozygous in an affected child and confidently absent in{' '}
            <em>both</em> genotyped parents (a true trio is required; a parent with a missing or
            low-coverage genotype does not qualify).
          </li>
          <li><strong>Homozygous recessive</strong> — affected individuals homozygous-alt, no unaffected homozygous-alt.</li>
          <li><strong>Compound heterozygous</strong> — two heterozygous hits in the same gene that segregate as a pair.</li>
          <li><strong>X-linked recessive</strong> — sex-aware X-chromosome pattern.</li>
          <li><strong>Dominant</strong> — affected carry the variant, unaffected do not (covers inherited-dominant and no-trio cases).</li>
        </ul>

        <h3>The score breakdown</h3>
        <p>
          Open a variant’s review dialog to see exactly <em>why</em> it ranked where it did: the
          combined score and rank, the variant / pathogenicity / rarity / phenotype sub-scores, the
          compatible inheritance modes, the gene constraint values, and — most usefully — the
          specific patient phenotypes that drove the gene’s phenotype match. This explainability is
          the point: the ranking is a transparent aid, not a black box.
        </p>

        <h3>Export</h3>
        <p>
          With the preset active, <em>Download CSV</em> exports the variants in ranked order with{' '}
          <strong>Priority</strong> and <strong>Rank</strong> columns, so the file matches what you
          see on screen.
        </p>

        <div className="user-guide-callout">
          <strong>Read the scores as a ranking, not a verdict.</strong> Priority scores order
          candidates <em>within a family</em>; they are not calibrated probabilities of
          pathogenicity. Phenotype matching needs HPO recorded on the affected individuals — without
          it, ranking falls back to impact/rarity/segregation only. If the result list shows a{' '}
          <em>“ranking is incomplete”</em> warning, more candidates matched than the ranker handles
          at once: tighten the filters (frequency, impact, a gene panel, or an inheritance mode) so
          the full set is ranked.
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
    id: 'acmg-classification',
    title: 'Semi-automatic ACMG classification',
    summary:
      'A guided ACMG/AMP classifier that pre-evaluates criteria from the variant, trio and gene data, scores them on a points scale, and stays fully overridable.',
    content: (
      <>
        <p>
          From any small-variant card or table row, <strong>ACMG classify</strong> opens a dedicated
          modal that helps you apply the ACMG/AMP 2015 criteria. It reads the data already attached to
          the variant — molecular consequence, gnomAD frequency, in-silico predictions, ClinVar — plus
          the gene profile (ClinGen dosage, GenCC inheritance, gene–phenotype HPO terms) and the family
          genotypes, and pre-positions each criterion accordingly. Nothing is final: every criterion
          can be toggled and re-graded by you.
        </p>

        <h3>How the score and class are computed</h3>
        <p>
          Scoring follows the Tavtigian/ClinGen Bayesian <strong>points</strong> system. Each
          <em> applied</em> criterion contributes points by its strength; the signed total maps onto
          the five ACMG classes and drives the green→red scale bar and arrow at the top of the modal.
        </p>
        <div className="content-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Strength</th>
                <th>Pathogenic</th>
                <th>Benign</th>
              </tr>
            </thead>
            <tbody>
              <tr><td>Supporting (PP/BP)</td><td>+1</td><td>−1</td></tr>
              <tr><td>Moderate (PM)</td><td>+2</td><td>−2</td></tr>
              <tr><td>Strong (PS/BS)</td><td>+4</td><td>−4</td></tr>
              <tr><td>Very strong (PVS1)</td><td>+8</td><td>—</td></tr>
            </tbody>
          </table>
        </div>
        <p>
          Class bands over the point total: <strong>≥ 10</strong> Pathogenic ·{' '}
          <strong>6–9</strong> Likely Pathogenic · <strong>0–5</strong> VUS ·{' '}
          <strong>−1…−6</strong> Likely Benign · <strong>≤ −7</strong> Benign. <code>BA1</code>
          {' '}(allele frequency ≥ 5%) is a stand-alone override that classifies the variant Benign
          regardless of any other evidence. The class is also recomputed on the server when you save,
          so a stored classification never depends on the browser.
        </p>

        <h3>The four states a criterion can be in</h3>
        <p>Auto-evaluation positions every criterion into one of four states (all overridable):</p>
        <ul>
          <li>
            <strong>Applied (checked, green)</strong> — the data clearly supports the criterion, so it
            is pre-checked and already counts toward the score.
          </li>
          <li>
            <strong>Consider (●, amber)</strong> — there is a relevant but not decisive signal. The
            criterion is surfaced unchecked; you confirm it if appropriate.
          </li>
          <li>
            <strong>Argues against (✕, red)</strong> — the data points the other way (e.g. an
            in-silico tool calls it benign when you are looking at PP3). Left unchecked and flagged.
          </li>
          <li>
            <strong>Not applicable (greyed, struck-through)</strong> — the criterion cannot apply to
            this variant given its type, frequency band or family configuration. Greyed as a clear
            hint, but still clickable so you can override it.
          </li>
        </ul>
        <p>
          Hover any criterion for the exact evidence string behind its state. Criterion families are
          laid out benign-left to pathogenic-right to mirror the scale bar.
        </p>

        <h3>Pre-check rules (positive evidence)</h3>
        <p>
          These rules decide which criteria are pre-checked or flagged <em>consider</em> from the
          variant, gene and family data:
        </p>
        <div className="content-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Criterion</th>
                <th>State</th>
                <th>Rule / data source</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>PVS1</strong></td>
                <td>Applied (Very strong / Strong) or Consider</td>
                <td>
                  Predicted-null consequence (nonsense, frameshift, canonical ±1,2 splice, start-loss,
                  transcript ablation). Applied at <em>Very strong</em> when LOFTEE is high-confidence
                  and ClinGen lists the gene as haploinsufficient (“Sufficient evidence”); at
                  <em> Strong</em> otherwise. If the LOF disease mechanism is unconfirmed it is shown
                  as <em>Consider</em> rather than auto-applied.
                </td>
              </tr>
              <tr>
                <td><strong>PM2</strong></td>
                <td>Applied (Supporting)</td>
                <td>Absent from gnomAD, or popmax allele frequency &lt; 1×10⁻⁴.</td>
              </tr>
              <tr>
                <td><strong>BA1</strong></td>
                <td>Applied (Stand-alone)</td>
                <td>gnomAD allele frequency ≥ 5% — stand-alone benign override.</td>
              </tr>
              <tr>
                <td><strong>BS1</strong></td>
                <td>Applied (Strong)</td>
                <td>gnomAD allele frequency ≥ 1% (and &lt; 5%) — higher than expected for a Mendelian disorder.</td>
              </tr>
              <tr>
                <td><strong>BS2</strong></td>
                <td>Applied (Strong) / Consider</td>
                <td>
                  Homozygotes observed in gnomAD. Strong when the gene is recessive-associated (GenCC);
                  otherwise <em>Consider</em> pending inheritance-mode confirmation.
                </td>
              </tr>
              <tr>
                <td><strong>PM4</strong></td>
                <td>Consider (Moderate)</td>
                <td>In-frame indel or stop-loss (protein-length change) — confirm it is outside a repeat region.</td>
              </tr>
              <tr>
                <td><strong>PP2</strong></td>
                <td>Applied (Supporting)</td>
                <td>Missense in a missense-constrained gene (gnomAD missense Z ≥ 3.09).</td>
              </tr>
              <tr>
                <td><strong>PP3 / BP4</strong></td>
                <td>Applied (strength-scaled)</td>
                <td>
                  In-silico predictions. REVEL drives the call with ClinGen-calibrated thresholds —
                  PP3: ≥ 0.644 Supporting, ≥ 0.773 Moderate, ≥ 0.932 Strong; BP4: ≤ 0.290 Supporting,
                  ≤ 0.183 Moderate, ≤ 0.016 Strong. SpliceAI (max Δ ≥ 0.2 / ≥ 0.5) and AlphaMissense
                  class are also used. The opposing criterion is flagged <em>argues against</em>.
                </td>
              </tr>
              <tr>
                <td><strong>BP7</strong></td>
                <td>Applied (Supporting)</td>
                <td>Synonymous variant with no predicted splice impact (SpliceAI max Δ &lt; 0.1).</td>
              </tr>
              <tr>
                <td><strong>PP5 / BP6</strong></td>
                <td>Applied (Supporting)</td>
                <td>ClinVar reports this exact variant pathogenic (→ PP5) or benign (→ BP6).</td>
              </tr>
              <tr>
                <td><strong>PP4</strong></td>
                <td>Applied (Supporting)</td>
                <td>The proband’s “present” HPO terms overlap the gene’s HPO associations.</td>
              </tr>
              <tr>
                <td><strong>PM6</strong></td>
                <td>Applied (Moderate)</td>
                <td>
                  Trio: variant present in the proband and absent in both sequenced parents (de novo).
                  Applied as <em>assumed</em> de novo (PM6); upgrade to PS2 manually if parentage is
                  molecularly confirmed.
                </td>
              </tr>
              <tr>
                <td><strong>PP1</strong></td>
                <td>Consider (Supporting)</td>
                <td>Cosegregation: the variant is carried by ≥ 2 affected family members.</td>
              </tr>
              <tr>
                <td><strong>BS4</strong></td>
                <td>Consider (Strong)</td>
                <td>Lack of segregation: an affected relative does not carry the variant.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <h3>Exclusion rules (greyed as “not applicable”)</h3>
        <p>
          Criteria that cannot apply to the variant in front of you are greyed out, so the working set
          stays honest. They remain clickable for the rare case where you need to override.
        </p>
        <div className="content-table-wrap">
          <table>
            <thead>
              <tr>
                <th>When…</th>
                <th>Greyed as not applicable</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Missense variant</td>
                <td>PVS1, PM4, BP3, BP7</td>
              </tr>
              <tr>
                <td>Loss-of-function variant</td>
                <td>PP2, PM5, BP1, BP7, BP3</td>
              </tr>
              <tr>
                <td>Synonymous variant</td>
                <td>PVS1, PM4, PP2, PM5, BP1, BP3</td>
              </tr>
              <tr>
                <td>In-frame / length-changing variant</td>
                <td>PVS1, PP2, PM5, BP1, BP7</td>
              </tr>
              <tr>
                <td>Splice-region variant</td>
                <td>PVS1, PP2, PM5, BP1, PM4</td>
              </tr>
              <tr>
                <td>Allele frequency does not match a band</td>
                <td>The frequency criteria that do not fit — only the matching one of PM2 / BS1 / BA1 stays active</td>
              </tr>
              <tr>
                <td>No homozygotes in gnomAD</td>
                <td>BS2</td>
              </tr>
              <tr>
                <td>No in-silico prediction available</td>
                <td>PP3, BP4</td>
              </tr>
              <tr>
                <td>No complete trio / parental genotypes</td>
                <td>PS2, PM6</td>
              </tr>
              <tr>
                <td>Variant inherited from a parent</td>
                <td>PS2, PM6 (it is not de novo)</td>
              </tr>
              <tr>
                <td>No additional affected carrier</td>
                <td>PP1 (cosegregation cannot be shown)</td>
              </tr>
              <tr>
                <td>No affected relative lacking the variant</td>
                <td>BS4 (lack of segregation cannot be shown)</td>
              </tr>
            </tbody>
          </table>
        </div>

        <h3>What is not auto-evaluated</h3>
        <p>
          Criteria that need information CoGA does not hold are always left for you to apply manually:
          <strong> PS1</strong> and <strong>PM5</strong> (a different/known variant at the same amino-acid
          residue — needs a residue-level ClinVar index), <strong>PS3 / BS3</strong> (functional studies),
          <strong> PS4</strong> (case–control prevalence), <strong>PM1</strong> (hotspot / functional
          domain) and <strong>PM3 / BP2</strong> (in-trans phasing).
        </p>

        <h3>External evidence links</h3>
        <p>
          The modal header carries quick links for the variant — <strong>gnomAD</strong>,{' '}
          <strong>ClinVar</strong>, <strong>DECIPHER</strong> — plus a smart <strong>PubMed</strong>
          {' '}search that combines the gene/variant with the patient’s HPO terms, to check whether the
          gene–phenotype association has been published.
        </p>

        <div className="user-guide-callout">
          <strong>Decision support, not an autoclassifier.</strong> Suggestions are pre-positioned from
          the data, but you confirm, adjust strengths, and add a rationale note. On save, the resulting
          class is written back as the variant’s ACMG classification (and class tag), and the full
          per-criterion rationale is stored for audit and reuse.
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
              Inspect per-sample repeat-locus calls against the catalog to assess repeat expansions in the
              family.
            </p>
          </div>
          <div className="user-guide-mini-card">
            <p className="user-guide-mini-card-title">Paraphase</p>
            <p className="user-guide-mini-card-copy">
              Resolve paralogous / complex regions where standard variant calling is
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
          Tables are for finding candidates; viewers are for confirming and inspecting them and diving deeper into their genomic context. Each viewer reads the
          tracks that were imported for the family.
        </p>
        <ul>
          <li><strong>Genome overview</strong> — whole-genome context for variants and tracks.</li>
          <li>
            <strong>Chromosome view</strong> — a single chromosome with coverage, segments, and
            variant tracks; the ROI opens here with ±1 Mb of flanking context.
          </li>
          <li><strong>Circos plot</strong> — genome-wide structural relationships at a glance.</li>
          <li>
            <strong>IGV</strong> — read-level confirmation against the reference for a specific
            locus.
          </li>
        </ul>
        <h3>Small-variant track: colours and rows</h3>
        <p>
          In the Chromosome view, each small variant is drawn as a dot. Its colour encodes the
          predicted consequence, with ClinVar taking precedence:
        </p>
        <ul>
          <li>
            <strong>Functional impact</strong> — high impact is <strong>light orange</strong>,
            medium (moderate) is <strong>light green</strong>, and low / modifier is{' '}
            <strong>light gray</strong>.
          </li>
          <li>
            <strong>ClinVar overrides the impact colour</strong> — benign / likely benign is{' '}
            <strong>light blue</strong>, and pathogenic / likely pathogenic is <strong>red</strong>.
            Other ClinVar states (uncertain, conflicting) keep the impact colour.
          </li>
          <li>
            <strong>A review tag colour</strong>, when you have tagged the variant, takes priority
            over both of the above.
          </li>
        </ul>
        <p>
          When the displayed sample is a child with a parent in the family (or phasing is
          available), the track splits into three rows by parental origin:
        </p>
        <ul>
          <li><strong>Top row</strong> — variants on the paternal haplotype (hap1).</li>
          <li><strong>Middle row</strong> — undetermined / unknown parental origin.</li>
          <li><strong>Bottom row</strong> — variants on the maternal haplotype (hap2).</li>
        </ul>
        <p>
          Origin is read from the parent genotypes (Mendelian inheritance) when both parents are
          present, falling back to the phased haplotype order of the variant otherwise. Homozygous,
          de-novo, and ambiguous variants stay in the middle row. These are the <em>raw</em> calls —
          hover any dot to see its impact, ClinVar significance, and parental origin.
        </p>

        <h3>Haplotype track</h3>
        <p>
          The haplotype track enables visual inspection of recombinations. Raw (imputed) informative
          markers are shown, and the (imputed) haplotype blocks are colour-coded according to the
          pedigree information. For individuals affected by a dominant disorder, the shared haplotype
          blocks are colour-coded in red. Individuals affected by a recessive disorder have two
          affected haplotypes (coloured orange), while carrier parents — or other carriers in the
          pedigree — carry a single affected (orange) haplotype.
        </p>

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
          <li>
            <strong>Monarch gene–disease associations</strong> and each disease’s expected HPO
            phenotypes, with patient overlap when opened in a family context — see{' '}
            <a href="#phenotype-matching">Phenotype matching</a>.
          </li>
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
            variant tagged <em>Reported</em>, or every individual with a pathogenic variant in a certain gene.
          </li>
          <li>
            Click a heterozygous, homozygous, or family count to drill into the carriers, grouped by
            family, and link straight to the family workspace.
          </li>
          <li>Optionally add a per-sample genotype filter to find variants a specific sample carries.</li>
          <li>Imputed calls are left out by default but can be included with a toggle.</li>
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
            <strong>Monarch knowledge graph</strong> — load the monthly Monarch release (gene–disease
            and disease–phenotype associations) that powers{' '}
            <a href="#phenotype-matching">phenotype matching</a> and{' '}
            <a href="#variant-prioritisation">variant prioritisation</a>. Run it once after deploy and
            roughly monthly to stay current; until it is run, the phenotype blocks show an empty state.
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
            <strong>Audit logs</strong> — a full activity trail for inspection and platform
            optimisation, split into two views. <strong>API requests</strong> records every backend
            call: who, what, when, the response and duration, inferred data updates, and which search
            filters a query used. <strong>UI interactions</strong> records client-side activity that
            never reaches the backend — every button and link click and each in-app navigation.
            Identifiers are masked (paths reduced to <em>:id</em>, query strings to their filter
            names), so the trail shows <em>how</em> the platform is used without exposing patient
            data.
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
            <strong>CADD / REVEL / SpliceAI / SIFT / PolyPhen / AlphaMissense</strong> — in-silico
            predictors of deleteriousness or splicing impact (AlphaMissense scores missense
            variants).
          </li>
          <li><strong>HPO</strong> — Human Phenotype Ontology: a structured vocabulary of clinical phenotypes, organised as a hierarchy (specific terms inherit from more general ones).</li>
          <li>
            <strong>Monarch Initiative</strong> — a knowledge graph linking genes, diseases, and HPO
            phenotypes from curated sources; CoGA uses it for phenotype matching and ranking.
          </li>
          <li>
            <strong>Phenotype similarity (Phenomizer / semantic similarity)</strong> — a score for how
            well two sets of HPO terms match, weighting rarer, more specific shared phenotypes
            (information content) more heavily.
          </li>
          <li>
            <strong>pLI / LOEUF</strong> — gene-level constraint metrics: how intolerant a gene is to
            loss-of-function variation (high pLI / low LOEUF = constrained).
          </li>
          <li>
            <strong>De novo (trio)</strong> — a variant present in an affected child but absent in
            both parents; confirming it needs a genotyped, well-covered trio.
          </li>
          <li>
            <strong>Priority score</strong> — the Exomiser-style ranking score blending phenotype fit,
            impact, rarity, and segregation; orders candidates within a family rather than giving an
            absolute probability.
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

import React from 'react';
import { Link } from 'react-router-dom';

type AdminModule = {
  label: string;
  to: string;
  description: string;
};

type AdminGroup = {
  title: string;
  description: string;
  modules: AdminModule[];
};

const adminGroups: AdminGroup[] = [
  {
    title: 'Reference Data',
    description: 'System-wide reference datasets and annotations.',
    modules: [
      {
        label: 'Organisms & Assemblies',
        to: '/admin/reference/assemblies',
        description: 'Species, assemblies, chromosomes, genes, and reference intervals.',
      },
      {
        label: 'Gene Panels',
        to: '/admin/reference/gene-panels',
        description: 'Panel catalog, source metadata, and panel membership.',
      },
      {
        label: 'Gene Reference Sync',
        to: '/admin/reference/gene-reference',
        description: 'Refresh cached human gene summaries and external annotations.',
      },
      {
        label: 'HPO Terminology',
        to: '/admin/reference/hpo',
        description: 'Ontology terms, synonyms, relationships, release status, and sync.',
      },
    ],
  },
  {
    title: 'User & Access Management',
    description: 'Users, permissions, projects, and access assignments.',
    modules: [
      {
        label: 'Users',
        to: '/admin/access/users',
        description: 'User accounts, roles, and activation status.',
      },
      {
        label: 'Projects & Access',
        to: '/admin/access/projects',
        description: 'Project catalog and family/sample access assignments.',
      },
    ],
  },
  {
    title: 'Data Management',
    description: 'Imported and stored family, sample, and assay data.',
    modules: [
      {
        label: 'Family & Sample Data',
        to: '/admin/data/families',
        description: 'Inventory, project assignment, and deletion workflows.',
      },
      {
        label: 'Package Import',
        to: '/admin/data/upload',
        description: 'Validate manifests and run package-based initial or incremental imports.',
      },
    ],
  },
  {
    title: 'Variant Configuration',
    description: 'Interpretation labels and reusable variant filters.',
    modules: [
      {
        label: 'Variant Tags',
        to: '/admin/variants/tags',
        description: 'Review tag definitions and project-scoped tag configuration.',
      },
      {
        label: 'Preset Filters',
        to: '/admin/variants/presets',
        description: 'Saved small-variant filter presets for consistent review.',
      },
    ],
  },
  {
    title: 'Database & Operations',
    description: 'Technical storage and operational controls.',
    modules: [
      {
        label: 'ClickHouse Tables',
        to: '/admin/operations/clickhouse',
        description: 'Assembly table status, ensure actions, optimize, and index rebuilds.',
      },
      {
        label: 'Variant Operations',
        to: '/admin/operations/variants',
        description: 'Variant-storage maintenance and ClickHouse-backed operations.',
      },
    ],
  },
  {
    title: 'Monitoring & Audit',
    description: 'Traceability for operational and administrative activity.',
    modules: [
      {
        label: 'Audit Logs',
        to: '/admin/monitoring/audit-logs',
        description: 'Request, user, status, and update-event history.',
      },
    ],
  },
];

const AdminDashboardPage: React.FC = () => (
  <div className="page-shell space-y-8">
    <section className="surface-card page-top-card">
      <div className="page-header">
        <div className="space-y-2">
          <p className="page-kicker">Administration</p>
          <h1 className="catalog-card-title">Admin dashboard</h1>
          <p className="catalog-card-copy">
            All administrative workspaces are grouped by operational domain and reachable from this page.
          </p>
        </div>
      </div>
    </section>

    <div className="grid gap-5 xl:grid-cols-2">
      {adminGroups.map((group) => (
        <section key={group.title} className="surface-card-flat catalog-card">
          <div className="space-y-2">
            <h2 className="section-title">{group.title}</h2>
            <p className="section-copy">{group.description}</p>
          </div>
          <div className="hpo-term-grid">
            {group.modules.map((module) => (
              <Link key={module.to} to={module.to} className="hpo-term-card">
                <span className="font-semibold text-[var(--color-heading)]">
                  {module.label}
                </span>
                <span className="table-subtle">{module.description}</span>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  </div>
);

export default AdminDashboardPage;

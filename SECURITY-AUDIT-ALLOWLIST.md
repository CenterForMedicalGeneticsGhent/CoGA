# Security-audit suppression register

_Companion to the automated security gates in [`.github/workflows/security.yml`](.github/workflows/security.yml)
(dependency-audit, secret-scan, SAST). Every suppression those gates apply is recorded
here so it is **code-reviewed**, justified, and dated, rather than buried in a CI flag.
This is direct evidence for the cybersecurity technical-file item (TF-13)._

> **Policy:** suppress only what genuinely cannot be fixed, scope the justification to
> why the device is not exposed, name an owner, and record a flip/review date. Anything
> with an available non-breaking fix is **fixed**, not suppressed.

Owner: ‹CMGG software lead› · Review cadence: each release, and on every Dependabot alert.

---

## 1. Dependency audit (`pip-audit` / `npm audit`)

### 1a. Backend — `ecdsa` Minerva timing attack (suppressed)

| Field | Value |
| --- | --- |
| Advisory | **GHSA-wj6h-64fc-37mp** — Minerva timing attack on P-256 in `python-ecdsa` |
| Package | `ecdsa==0.19.2` (transitive, `# via python-jose[cryptography]`) |
| Severity | High |
| Fix available | **None** — no upstream patch exists; `python-ecdsa` maintainers consider constant-timeness out of scope |
| Mechanism | `pip-audit --ignore-vuln GHSA-wj6h-64fc-37mp` (exact ID; any other advisory still fails) |
| Why CoGA is not exposed | CoGA mints/verifies JWTs via `python-jose` using the **cryptography** backend (HS256 symmetric in the local-auth path; RS256 for Azure). The pure-Python **ECDSA P-256** code path in `ecdsa` that the timing attack targets is **not exercised** by the device. The advisory is also GHSA-only (not in OSV/PyPI), which is why `pip-audit` itself reports clean — the ignore is an explicit, future-proof record of the Dependabot alert. |
| Flip action | Remove the `--ignore-vuln` when `ecdsa` ships a constant-time fix **or** when JWT handling is migrated off `python-jose`/`ecdsa` (e.g. to PyJWT, which uses `cryptography` directly and drops the `ecdsa` dependency — tracked as a follow-up). |

### 1b. Frontend production tree — **fixed, not suppressed**

`vite` (high) and `yaml` (moderate) advisories were resolved in this change by a
non-major lockfile bump (`vite ^7.0.6 → ^7.3.6`, `yaml` pinned `^2.8.3` via
`overrides`). `npm audit --omit=dev` reports **0 vulnerabilities**; the gate blocks any
new production high/critical.

### 1c. Frontend dev/build tree — report-only (dated flip)

| Advisories | `glob`, `minimatch`, `picomatch`, `ws`, `ajv`, `brace-expansion` (via the `vitest`/`eslint` toolchain) |
| --- | --- |
| Exposure | **Build/test-only** — none are in the deployed runtime artifact (`npm audit --omit=dev` is clean). |
| Mechanism | Non-blocking `npm audit --audit-level=high` step that surfaces them as a CI `::warning::`. |
| Flip action | Convert that step to **blocking** once the `eslint 8→9` / `vitest` toolchain upgrade lands (next dependency-maintenance sprint). |

---

## 2. Secret scanning (`gitleaks`)

Allowlisted in [`.gitleaks.toml`](.gitleaks.toml) — all **non-secrets**:

| Entry | Why it is not a secret |
| --- | --- |
| `ci-smoke-not-a-real-secret`, `ci-admin-not-a-real-secret` | Deliberate placeholder values used only by the CI smoke job (`.github/workflows/ci.yml`); not valid for any real environment. |
| `.env.example` (path) | The template operators copy and fill in; ships `change-me`-style placeholders by design. |
| `sbom/*.cdx.json` (path) | Generated dependency inventories (names + hashes), not credentials. |

The gate fires on any **new** secret outside these documented entries.

---

## 3. SAST (CodeQL)

No file-based allowlist. CodeQL's per-PR **diff baseline** is the mechanism: on a pull
request the Code Scanning check fails only on alerts **introduced by the PR**;
pre-existing alerts on `main` are recorded in the Security tab without blocking. Triage
of the existing backlog happens in the Security tab, not via suppression here.

---

## 4. Branch-protection action required (not code)

For these gates to actually block merges, add **`deps`**, **`secret-scan`**, and the
**`codeql`** checks to the required status checks for `main` in branch protection — the
same step needed for the existing `backend`/`frontend`/`smoke` checks. Until then the
gates are advisory.

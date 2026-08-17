# Publication Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a complete Chinese user guide, an evidence-grounded Chinese project paper in Markdown and PDF, reproducible paper figures, and the verified repository on GitHub.

**Architecture:** Public result files remain the only numerical source of truth. Small Python scripts generate static figures and the PDF without mutating evidence inputs; Markdown remains the editable source, while tests enforce claims, links, required sections, and build reproducibility. Publication uses the approved public repository name under the authenticated GitHub account.

**Tech Stack:** Python 3.11/3.12, pandas, matplotlib, ReportLab, pypdf, pdfplumber, pytest, Ruff, Git, GitHub CLI.

## Global Constraints

- Default results must be read from `reports/metrics/default_summary.json`; robustness results must be read from committed CSV/JSON evidence.
- Report 24 transformers, 5 actual ledger errors, F1 0.167, PR-AUC 0.378, Top-1 0.2, and Top-2 0.4 without inflating performance.
- Do not claim real-grid data, field deployment, production accuracy, 90% accuracy, industrial readiness, or digital signatures.
- DTW, Isolation Forest, GNN, and other unimplemented methods may appear only as future work.
- Paper PDF must be A4, visually inspected page by page, and committed at `paper/line-transformer-verification-paper.pdf`.
- GitHub repository must be public at `liyukki/distribution-network-line-transformer-verification` with `main` as the default branch.

---

### Task 1: Documentation and paper test contracts

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/unit/test_publication_docs.py`

**Interfaces:**
- Consumes: committed metrics and evidence files.
- Produces: executable requirements for the guide, paper, bibliography, figures, PDF, and prohibited claims.

- [ ] **Step 1: Add documentation build dependencies**

Add a `docs` optional dependency group containing `matplotlib>=3.9,<4`, `reportlab>=4,<5`, `pypdf>=5,<7`, and `pdfplumber>=0.11,<1`.

- [ ] **Step 2: Write failing publication tests**

Tests must assert that:

```python
GUIDE = ROOT / "docs/user-guide.md"
PAPER = ROOT / "paper/line-transformer-verification-paper.md"
PDF = ROOT / "paper/line-transformer-verification-paper.pdf"

assert GUIDE.exists()
assert PAPER.exists()
assert PDF.exists()
assert "0.167" in PAPER.read_text(encoding="utf-8")
assert "0.378" in PAPER.read_text(encoding="utf-8")
```

They must also check required headings, local links, bibliography DOI fields, at least four figure paths, the absence of prohibited claims, PDF page count greater than five, extractable Chinese title text, and A4 page dimensions within tolerance.

- [ ] **Step 3: Run the tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_publication_docs.py -q`

Expected: failure because guide and paper artifacts do not exist.

- [ ] **Step 4: Install the docs extra and lint the test**

Run: `.venv\Scripts\python.exe -m pip install -e ".[dev,docs]"` and Ruff on the new test.

- [ ] **Step 5: Commit the contract**

Commit message: `test: define publication package contract`.

### Task 2: Evidence-derived paper figures

**Files:**
- Create: `scripts/generate_paper_figures.py`
- Create: `paper/figures/README.md`
- Create: `paper/figures/system-workflow.png`
- Create: `paper/figures/baseline-comparison.png`
- Create: `paper/figures/confusion-matrix.png`
- Create: `paper/figures/robustness-ablation.png`
- Modify: `tests/unit/test_publication_docs.py`

**Interfaces:**
- Consumes: `reports/metrics/default_summary.json`, `reports/evidence/default_run/confusion_matrix.csv`, and `reports/metrics/robustness_aggregates.csv`.
- Produces: `generate_figures(root: Path) -> list[Path]` and four deterministic PNG artifacts.

- [ ] **Step 1: Add failing provenance tests**

Test that `generate_figures(tmp_path)` writes four non-empty PNGs, leaves SHA-256 of every source input unchanged, and that the baseline bar heights equal the JSON values rather than duplicated constants.

- [ ] **Step 2: Run focused tests and verify RED**

Run the two new figure tests; expected failure is an import error for `scripts.generate_paper_figures`.

- [ ] **Step 3: Implement deterministic generation**

Use `matplotlib` with `Microsoft YaHei`/`SimHei` fallback, 160 dpi or greater, explicit source captions, and a non-interactive backend. Build the workflow diagram from labeled boxes; read all result values from evidence files. Use a two-panel robustness figure: representative missing-rate sensitivity and six ablation variants summarized across seeds.

- [ ] **Step 4: Generate figures and verify PNG metadata**

Run: `.venv\Scripts\python.exe scripts/generate_paper_figures.py`.

Open each PNG with the local image viewer and verify readable Chinese text, legends, axes, and no clipping.

- [ ] **Step 5: Run tests and commit**

Run focused tests plus Ruff. Commit message: `docs: add evidence-derived paper figures`.

### Task 3: Complete user guide

**Files:**
- Create: `docs/user-guide.md`
- Modify: `README.md`
- Modify: `tests/unit/test_publication_docs.py`

**Interfaces:**
- Consumes: the actual CLI exposed by `src/ltverify/cli.py`, configuration files, current Streamlit pages, and manifest verifiers.
- Produces: a standalone operating manual and concise README links.

- [ ] **Step 1: Add failing guide-content tests**

Require headings for prerequisites, installation, quick start, CLI, dashboard, outputs, evidence reproduction, robustness, notebooks, troubleshooting, limitations, and interview demo. Extract every relative Markdown link and assert its target exists.

- [ ] **Step 2: Verify RED**

Run the guide tests and confirm they fail because the guide is absent.

- [ ] **Step 3: Write the guide against real commands**

Document exact Windows and POSIX commands, `LTVERIFY_RUN_DIR`, bilingual selector, each dashboard page, artifact schema-v2 behavior, SHA-256 limits, strict experiment verification, and common failures including stale Streamlit module cache.

- [ ] **Step 4: Link from README and verify**

Add prominent links to the guide, paper Markdown, and paper PDF near Quick Start. Run documentation tests and inspect rendered Markdown structure.

- [ ] **Step 5: Commit**

Commit message: `docs: add complete user guide`.

### Task 4: Evidence-grounded Chinese project paper

**Files:**
- Create: `paper/line-transformer-verification-paper.md`
- Create: `paper/references.bib`
- Modify: `tests/unit/test_publication_docs.py`

**Interfaces:**
- Consumes: approved design, methodology docs, public summary, robustness aggregates, generated figures, and verified primary literature metadata.
- Produces: the authoritative paper source and bibliography.

- [ ] **Step 1: Add failing paper-structure and claim tests**

Require the approved sections, figure references, equations for standardization/correlation/fusion score/gates, a result table matching JSON metrics, a 130-case experiment statement matching the manifest, and DOI-bearing references. Reject prohibited phrases unless they occur in an explicit negation such as “不代表现场部署”.

- [ ] **Step 2: Verify RED**

Run paper tests; expected failure is a missing Markdown paper and bibliography.

- [ ] **Step 3: Write methods and system sections**

Explain the 110/10/0.4 kV synthetic network, 30-day 15-minute simulation, corruption separation, preprocessing, feature definitions, weighted scoring, coverage and margin gates, evaluation metrics, software modules, and evidence chain.

- [ ] **Step 4: Write results, limitations, and references**

Report the weak default result without euphemism, compare against the baseline, analyze same/cross-feeder residual correlation failure boundary, summarize robustness/ablation from aggregates, and separate implemented work from future work. Add DOI-verifiable references for voltage-correlation topology identification, asynchronous TTU topology identification, pandapower, DTW, and Isolation Forest.

- [ ] **Step 5: Run numerical claim audit and commit**

Programmatically compare all headline numbers in the paper with source JSON/CSV, run tests, then commit with `docs: add evidence-grounded project paper`.

### Task 5: Reproducible PDF build and visual verification

**Files:**
- Create: `scripts/build_paper.py`
- Create: `paper/line-transformer-verification-paper.pdf`
- Modify: `tests/unit/test_publication_docs.py`

**Interfaces:**
- Consumes: paper Markdown, references, and four PNGs.
- Produces: `build_pdf(source: Path, output: Path) -> Path`, an A4 PDF with Chinese fonts, table of contents, figures, tables, links, footer, and page numbers.

- [ ] **Step 1: Add failing PDF tests**

Require a build to a temporary path, more than five pages, A4 media boxes, extractable Chinese title, all expected section titles, page-number footer text, and no missing image references.

- [ ] **Step 2: Verify RED**

Run PDF tests; expected failure is an import error or missing output.

- [ ] **Step 3: Implement the ReportLab builder**

Register `C:/Windows/Fonts/msyh.ttc` and bold variant when available, with `SimHei` fallback. Parse the controlled Markdown subset into ReportLab flowables, build a table of contents, render fenced equations/code as styled blocks, constrain images to page width, and add page numbers.

- [ ] **Step 4: Build and render every page**

Run the builder, then `pdftoppm -png paper/line-transformer-verification-paper.pdf tmp/pdfs/paper-page`. Use contact sheets or page images to inspect every page for clipping, overlap, unreadable text, broken tables, blank pages, and malformed references.

- [ ] **Step 5: Iterate until visual and automated checks pass**

After each layout fix, rebuild, rerender, and rerun focused tests. Commit with `docs: publish project paper PDF` only after zero visual defects.

### Task 6: Release audit and GitHub publication

**Files:**
- Modify: `README.md` only if final online link fixes are needed.
- Delete: `docs/superpowers/specs/2026-08-17-publication-package-design.md`
- Delete: `docs/superpowers/plans/2026-08-17-publication-package.md`

**Interfaces:**
- Consumes: complete repository and authenticated `gh` session.
- Produces: clean local `main` and public GitHub repository whose remote HEAD matches local HEAD.

- [ ] **Step 1: Run publication-specific checks**

Run documentation tests, rebuild figures and PDF, compare regenerated hashes or bytes as appropriate, validate PDF text and page dimensions, and scan Markdown/PDF-extracted text for prohibited claims and local absolute paths.

- [ ] **Step 2: Run project release gates**

Run full pytest with `--cov=ltverify --cov-fail-under=90`, Ruff on source/application/tests/scripts, wheel build, manifest verification, strict robustness manifest verification, byte-for-byte report reproduction, notebook execution, secret/path scans, and `git diff --check`.

- [ ] **Step 3: Remove internal planning artifacts and make final commit**

Delete this spec and plan from the public tree, rerun documentation tests, and commit `docs: finalize public release package`.

- [ ] **Step 4: Create and publish the repository**

Confirm `gh auth status`, then create the public repository with `gh repo create liyukki/distribution-network-line-transformer-verification --public --source . --remote origin --push`. Set description and topics using `gh repo edit`.

- [ ] **Step 5: Verify GitHub state**

Use `gh repo view` and the GitHub API to prove public visibility, default branch `main`, remote commit equality, accessible README/guide/paper/PDF, MIT license detection, topics, and absence of secrets or ignored runtime outputs. Open the repository URL and inspect the rendered README.

- [ ] **Step 6: Complete the active goal**

Only after every requirement is proven, mark the persistent goal complete and report the GitHub URL, paper links, verification counts, and any honest limitations.

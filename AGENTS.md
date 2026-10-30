# DSIP Research Repository — Agent Instructions

> Scope: IEEE Transactions on Intelligent Transportation Systems (IEEE T-ITS) revision of **“DSIP: A Dynamic Coordination Planner for Signal-Free Intersections Using Diffusion-Model-Based Multi-Agent Motion Planning”** (manuscript **T-ITS-26-05-2776**).
>
> This file governs coding agents working in this repository. Read it before making changes. If a task conflicts with these rules, stop and explain the conflict instead of silently proceeding.

## 1. Mission and non-negotiable constraints

The mission is to prepare a **traceable, scientifically defensible R&R resubmission**. The work includes auditing and editing the Overleaf LaTeX project, recovering SUMO scenarios, independently implementing or adapting two autonomous intersection management (AIM) baselines, and conducting narrowly scoped supplementary experiments.

**Do not turn this revision into a new DSIP algorithm-development project.**

1. **Preserve the submitted record.** Never overwrite the submitted PDF, the imported Overleaf snapshot, original SUMO map files, or any historical results. Keep a separate editable revision copy or branch. Do not rewrite Git history to erase provenance.
2. **Do not claim the old DSIP implementation has been recovered.** The original DSIP source code, model checkpoints, raw trajectory logs, and experiment CSV files were deleted. The author confirms that **the original SUMO maps, `.sumocfg`, traffic/route `.rou.xml`, and other experiment XML files are retained**, and the original random-seed values are known. The old DSIP source/checkpoints and run-level CSV/trajectory/time-series logs are unavailable. A reconstruction from the paper and upstream MMD is a **new reconstruction**, not the historical executable.
3. **No unsolicited method changes.** Do not redesign diffusion guidance, CBS, vehicle coordination rules, or other planning logic. The prior work largely retained MMD's CBS and contributed traffic-specific online decision making and road adaptation. Preserve that division of responsibility.
4. **No ablation study by default.** The reviewers did not explicitly request one, and the author has excluded it from the present scope. Do not add, propose as mandatory, or implement ablations without an explicit new instruction.
5. **No fabricated evidence.** Do not invent simulation results, model weights, data, code availability, statistical significance, citations, reviewer responses, or validation outcomes. Flag missing assets, dependencies, and unverifiable claims.
6. **Avoid destructive commands.** Do not delete or overwrite research assets, force-push, reset branches destructively, or replace original configurations. Ask before irreversible operations. Never commit large generated simulation outputs or pretrained weights without a deliberate storage plan.
7. **Never silently change the scientific meaning.** An English edit, page compression, plot redesign, or baseline adapter must not alter formulas, assumptions, numerical findings, traffic rules, or interpretations without an explicit explanation and approval.

## 2. Project facts and revision boundaries

### Submission and editorial context

- Journal: **IEEE Transactions on Intelligent Transportation Systems (T-ITS)**.
- Manuscript ID: **T-ITS-26-05-2776**.
- Decision: **Revise and Resubmit**, with a **90-day revision window** according to the Editor-in-Chief's letter. The exact editorial deadline is not established by this file; verify it from the decision date or submission portal.
- The EIC suggested a **Regular Paper of approximately 10 Transactions pages, including biographies**. Treat this as a recommendation, **not as a confirmed hard page limit**. Preserve scientific completeness when shortening the manuscript.

### What DSIP actually claims

- The methodological foundation is **MMD [41]**, combining diffusion-based planning with conflict-based search (CBS).
- The author confirms that DSIP **did not substantially change CBS**.
- DSIP's own work focuses on **road adaptation**, **dynamic traffic decision-making**, integration with SUMO/TraCI, repeated replanning, and step-wise execution.
- The submitted manuscript reports experiments on isolated four-leg intersections with **4/6/8 lanes**, **five traffic-demand levels**, **left:straight:right = 1:2:1**, **SUMO step 0.1 s**, **planning update 0.4 s**, **1000 s simulation duration**, and **30 seeds per tested configuration**. These are descriptions from the submitted paper, not confirmation of recovered configurations.
- The published/submitted historical results are **not to be numerically rewritten** based on newly reconstructed code. Distinguish historical results from new supplementary results.

### Agreed supplementary work

- **AIM baseline 1:** FCFS reservation-based intersection management, referencing the Dresner–Stone / AIM4 approach.
- **AIM baseline 2:** CCAM-DI, evaluating feasibility of adaptation from its existing SUMO-based environment.
- **Literature:** add and discuss Klimke et al., *“A Real-World Evaluation of Two Cooperative Intersection Management Approaches,”* DOI **10.1109/MITS.2025.3643199**. No official drop-in reproduction code has yet been established; do not assert definitively that no code exists. Do not claim DSIP empirically outperforms that method without matched experiments.
- **Traffic-turning-demand sensitivity:** supplementary DSIP tests with varying left/straight/right movement ratios, **only after reconstruction has been validated**.
- **Small optional/targeted studies:** CBS planning-time distribution/timeouts, modest communication latency/jitter, and trajectory feasibility checks when the recovered system supports valid tests.
- **Out of scope unless explicitly authorized:** new diffusion architecture, changed CBS search, new traffic-planning mechanism, full-scale mixed-traffic deployment, broad ablation matrices.

## 3. Repository layout and provenance

The layout below is a **target**, not an excuse to rename existing files before inventory. First examine the actual tree, then propose changes.

```text
DSIP-Research/
├── AGENTS.md                   # Canonical agent instructions
├── AGENT.md                    # Optional mirror for tools expecting this name
├── README.md
├── paper/
│   ├── submitted/              # Immutable submitted PDF / Overleaf snapshot
│   ├── revision/               # Editable LaTeX sources, figures, bibliography
│   └── reviews/                # EIC letter and reviewer comments
├── scenarios/                  # Original SUMO .sumocfg/.net.xml/.rou.xml/.add.xml
├── third_party/                # Pinned upstream MMD, AIM4, CCAM-DI repositories
├── src/dsip_reconstructed/     # New, clearly identified reconstruction
├── baselines/                  # Independent SUMO interfaces / adapters
├── experiments/                # Named scenarios, seeds, configurations, launchers
├── evaluation/                 # Shared metrics and plotting (no result fabrication)
├── tests/
├── results/                    # Clearly separated historical/new artifacts
└── docs/
    ├── audits/
    ├── experiments/
    └── decisions/
```

Record upstream repository URLs, exact pinned commits, license obligations, dependency versions, and all deviations from each upstream implementation. Do not silently patch `third_party/`; put adaptations in separate modules or document each necessary change.

The working LaTeX revision must be traceable to a **frozen submitted-source snapshot**. If the Overleaf export cannot be conclusively matched to the submitted PDF, document the mismatch instead of assuming they are identical.

## 4. FIRST TASK: LaTeX and manuscript audit (audit-only pass)

**The first pass must inspect and report. Do not modify the paper until the author approves the findings or issues an explicit edit task.** The LaTeX files may not yet be present; if they are absent, report that and do not invent them.

### 4.1 Inventory and build

1. Identify the root `.tex` file, subfiles, `*.bib`, custom `.sty`/`.cls`, figures, external tables, build scripts, and bibliography toolchain.
2. Identify whether the repository contains the submitted PDF and source snapshot. Note missing figures, bibliography entries, packages, or fonts.
3. Create a clean reproducible build using the project's original engine/toolchain where possible (`latexmk` or equivalent). Record exact commands and compiler/package versions. Do not auto-upgrade the IEEE template or dependencies.
4. Capture compilation warnings and errors: undefined references, missing citations, multiply defined labels, overfull/underfull boxes, float placement, missing graphics, bibliography problems, and unexpected page breaks.
5. Compare rendered equations/figures/tables against the actual submitted PDF when available. A PDF text extractor's symbol errors are **not sufficient evidence** of a LaTeX error: the rendered output is authoritative.

### 4.2 Reviewer-specific verification checklist

For each issue, record **source location**, **rendered PDF page**, **what the reviewer reported**, **what is actually observed**, **whether a change is necessary**, and **the proposed minimal fix**:

| Review item | Audit question |
|---|---|
| R1 — CBS acronym | Is “conflict-based search (CBS)” introduced at its first use? |
| R1 — theoretical method vs SUMO implementation | Are generic formulations and tool-specific TraCI/implementation details mixed? Identify exact paragraphs to relocate without altering methods. |
| R1 — Table II, right turns | Does “Always Green” describe a representative fixed-time baseline? Verify that the manuscript explains mainland China's permissive right-turn practice and that the actual SUMO signal/yield rules support the explanation. **Do not change the signal program or past data.** |
| R1/R2 — Fig. 8 | Are vehicles, paths, and conflict-zone details legible at IEEE column width? Suggest an enlarged or redesigned figure without manipulating data. |
| R2 — Figs. 2–4 | Are square-root delay axes clearly labeled, with interpretable physical units (seconds) available? |
| R2 — Eq. (20) | Is the time-index set consistently rendered as `\mathcal{H}_b` (rather than an inconsistent subscript)? Compare source and compiled PDF. |
| R2 — Eq. (23) | Are the equality sign, constraint tuple, indices, commas, and interval brackets correct in source and PDF? |
| R2 — Eq. (24) | Is the velocity variable shown and defined correctly? Distinguish step-wise displacement-derived speed from average traffic speed. |
| Experimental notation | Check lane-count descriptions, demand units, symbols, equations, figure/table references, and definitions for consistency. |
| Contributions vs MMD [41] | Identify passages that inaccurately imply the combination of diffusion + CBS was invented by DSIP. Suggest accurate attribution; do not invent mechanisms. |
| Claims vs evidence | Flag claims about physical feasibility, zero collisions, V2X realism, and real-time deployment that exceed the evidence in the submitted manuscript. |

Check whether the reported defects appear in the **actual source and compiled PDF**. If Eq. (20)/(23)/(24) already appear correct, mark **“not reproduced in current source/build”**, then propose a calm factual reviewer response rather than introducing unnecessary mathematical changes.

### 4.3 Deliverables of the initial audit

Write these files, with no manuscript edits in the first pass:

- `docs/audits/latex-audit.md` — build status, warnings, exact file/line evidence, screenshots or page references where useful.
- `docs/audits/reviewer-issue-matrix.md` — every R1/R2 item, priority, paper location, action, evidence needed, proposed response status.
- `docs/audits/page-budget.md` — measured page count including references/biographies, where space is used, safe compression opportunities, possible tradeoffs.
- `docs/audits/repo-inventory.md` — found/missing source, SUMO files, environments, weights, logs, seeds, and upstream dependencies.

Conclude the report with a **minimal change list** divided into: `safe copy-edit`, `needs author judgment`, `needs new experiment`, and `cannot verify from available assets`.

## 5. Editing the LaTeX manuscript — ONLY after authorization

Use small, reviewable patches. Keep one type of change per commit or logical patch; state before/after effects.

### Preferred order

1. Fix **confirmed** LaTeX typos, acronym introductions, broken cross-references, inconsistent symbols, bibliography issues, and build failures.
2. Separate **generic methodology** from **SUMO-specific implementation**, preserving algorithm behavior and mathematical meaning.
3. Clarify the method's actual relationship to MMD [41]; distinguish *adaptation/system contribution* from previously published diffusion/CBS components.
4. Clarify Table II's representative fixed-time baseline and right-turn rule without asserting unconditional right-of-way or changing old experiments.
5. Improve figure legibility and unit presentation; keep charts based on verifiable data only.
6. **Compress the paper only after correctness issues are fixed.** Remove repeated explanations, shorten related-work prose cautiously, consolidate redundant algorithm descriptions, and improve floats/figures. Do not delete a reviewer-relevant explanation merely to save a page.

### Compression guardrails

- Record page count before/after **using the same verified TeX toolchain**; include author biographies when assessing the EIC's suggested length.
- Prioritize substantive concision over template hacks; do not shrink fonts, violate IEEE formatting, or bury important reviewer-facing details in unreadably small figures.
- Preserve all essential assumptions, equations, citations, experiment settings, baselines, limitations, and numerical results. Do not compress away important attribution to MMD or other AIM work.
- New baseline results may require room: reserve a page budget for them. The editor's ~10 pages is guidance; request a tradeoff decision if reaching it would damage completeness.
- After edits, compile; verify citation consistency, table readability, rendered formulas, figure quality, and final page count. Produce a concise diff summary.


## 6. Plotting and figure-generation rules

All new figures for the revision must be generated by scripts in a traceable plotting pipeline (for example under `evaluation/` or `scripts/plotting/`). Do not hand-edit final charts in PowerPoint, Illustrator, or image editors in ways that change numerical content. If aesthetic post-processing is necessary, preserve the script-generated original and document what changed.

### 6.0 Critical limitation: historical DSIP raw data no longer exist

**The author no longer has the original DSIP run-level CSVs, raw trajectories, per-seed metrics, or time-series logs.** The full original SUMO experiment XML/route inputs and remembered random seeds *are* available. The submitted manuscript PDF and imported Overleaf figure assets may preserve already-rendered historical plots, but a rendered image does not restore the underlying observations.

**Before plotting, inventory and classify every input as one of:**

- `HISTORICAL_FIGURE`: original chart/snapshot asset from Overleaf or submitted PDF, without the underlying data;
- `HISTORICAL_EXACT_SUMMARY`: exact numbers actually preserved in submitted text, tables or figure source (if machine-readable and verified);
- `NEW_BASELINE_RAW`: per-run FCFS/CCAM-DI experimental outputs;
- `RECONSTRUCTED_DSIP_RAW`: per-run outputs from a separately validated reconstructed DSIP implementation.

Do **not** digitize old image curves/boxes to invent run-level measurements, synthesize 30 random-seed observations from averages/confidence intervals, or manufacture a historical DSIP distribution. Even vector graphics do not on their own certify the original metric provenance. If raw data do not exist, **do not redraw historical DSIP box plots or recompute uncertainty**. Reuse original figure assets as historical visual evidence (preserving their content) and improve the caption/legibility without changing plotted values.

**The original manuscript's historical figures remain valid published-submission evidence to discuss and improve visually; they are not a substitute for raw per-run data in a new joint statistical box plot.** Keep a `docs/audits/figure-source-inventory.md` specifying every existing figure, its source path, whether it has exact underlying numbers, and what edits are safe. Assess Overleaf assets (`.pdf`, `.eps`, `.svg`, `.png`, `.pgf`, `.tex`, external tables) before deciding data have to be regenerated.

### 6.1 Purpose-driven figure selection

Use figures selectively. Do not create a large number of loosely motivated plots. Default mapping:

- **Box plots**: use for **cross-method performance comparison across repeated runs**. This is the default for newly added baseline comparisons and turning-ratio sensitivity experiments.
- **Line plots**: use for **temporal evolution over simulation time**. Reserve them for questions where dynamic behavior matters, such as queue buildup, time-loss evolution, or speed stabilization.
- **Tables**: use when the key message is a small number of aggregate statistics, especially if a plot would be visually crowded.

### 6.2 Recommended figure strategy for this revision

Figure plans **depend on data availability**, not on appearance alone:

1. **Keep and improve original historical figures** (Figs. 2–7 and Fig. 8 as available) using the original assets from Overleaf. Preserve their numbers and uncertainty bands/boxes. For Figs. 2–4, address the reviewer concern about square-root time-loss axes with accurate label/caption explanation or verified physical-unit tick annotations; **do not invent raw second-by-second values**. For Fig. 8, use original resolution/vector assets to enlarge/crop the intersection/vehicles; do not create fake vehicle positions or traffic trajectories.
2. **Baseline-first figures**: once FCFS and CCAM-DI have new per-seed outputs, plot their own box plots (run-level average delay/speed) and selected temporal curves in the same saved original SUMO route scenarios. Label clearly which algorithms are present. Never insert a historical DSIP box in this new group without historical run-level data.
3. **If exact historical aggregate DSIP numbers exist**, an explicitly labeled table can show *historical manuscript DSIP aggregate* alongside *new baseline aggregate*, with the two source vintages, different code versions and caveats stated. Do not present as same-run paired statistical inference. If only rough values can be read from a plot, refrain from a precise numerical table.
4. **For a true three-method DSIP–FCFS–CCAM-DI box plot**, obtain **new raw DSIP runs** from a validated *reconstructed DSIP* implementation on the same saved XML routes/metrics, then plot those new three sets as the new experiment. Label this method `DSIP (reconstructed)` and disclose equivalence limitations. Keep historical DSIP results distinct. Do not claim validation of reconstructed DSIP solely because its averages happen to resemble the paper.
5. **Turning-ratio sensitivity**: if reconstructed DSIP cannot be validated or run, mark this reviewer request as unresolved; a box plot of other methods alone cannot establish DSIP's adaptation.
6. **Paper vs supplement**: reserve the main paper for the clearest original figure fixes, a compact credible baseline comparison, and only essential new results. Put full sweep figures in supplementary material when appropriate. Never create a composite that conceals incompatible evidence sources.

### 6.3 Box-plot rules

Use box plots only when **real per-run observations are available** for every distribution shown. In the immediate baseline-first phase this means FCFS and CCAM-DI, not the lost historical DSIP runs; later it may include validated reconstructed DSIP.

1. Plot one value per run/seed; do not pre-average away the distribution.
2. Use a consistent metric definition across methods.
3. Preferred organization:
   - x-axis: traffic density or turning-ratio condition;
   - grouped boxes within each x-axis category: methods;
   - separate panels or separate figures: lane configuration and/or metric.
4. Show median and quartiles by default. Means may be overlaid only if clearly distinguished.
5. If outliers are numerous, do not hide them without explanation; consider plotting them lightly or documenting the rule used.
6. Keep the **method ordering identical** across all figures.
7. **Do not put historical DSIP "boxes" into a new FCFS/CCAM box plot without raw historical runs.** Use exact historical summaries only as clearly distinguished annotations/tables where justified. New DSIP box plots require newly generated run-level data and the label `DSIP (reconstructed)`.

### 6.4 Line-plot rules

Use line plots only when showing temporal behavior is necessary.

1. For **new experiments with repeated runs**, plot the **mean or median over runs** and add a reproducibly computed uncertainty display (confidence band, interquartile band, or error bars). State which one is used. Do not manufacture or recreate a historical DSIP line/band from a rendered manuscript image.
2. Do not overload a line plot with too many methods, lane settings, and densities at once.
3. Prefer one controlling variable per figure:
   - fixed lane count + varying methods;
   - or fixed density + varying methods.
4. For **new raw-data figures**, prefer average time loss in seconds. In historical Figs. 2–4, do not change the underlying scale unless the exact underlying plot data/coordinates are demonstrably available; clarify the sqrt scale and units in captions, or convert tick labels only with a verified reversible mapping.
5. Axis labels must use interpretable units. Avoid reviewer confusion about transformed axes.

### 6.5 Styling and readability rules

1. Prioritize readability at IEEE final print size.
2. Use clear legends, concise captions, and sufficiently large axis labels and tick labels.
3. Avoid low-contrast color choices. Ensure methods remain distinguishable in grayscale when possible, using markers/linestyles if needed.
4. Multi-panel figures must have consistent axis scales when direct comparison is intended.
5. For traffic snapshots or trajectory visualizations (for example, revised Fig. 8), enlarge vehicles/paths and consider insets for the conflict zone.
6. Every figure caption should state:
   - scenario subset;
   - metric;
   - number of runs/seeds;
   - whether values are per-run aggregates or time-resolved averages;
   - what uncertainty display is shown.

### 6.6 Reproducibility and file outputs

1. Save each **newly generated** figure in both **vector format** (`.pdf`) and a quick-view raster format (`.png`); do not pretend an original historical raster was created from source observations.
2. Store the plotting script, input data path, and output path together.
3. Write a `plot_manifest.md` with data provenance (`HISTORICAL_FIGURE`, `HISTORICAL_EXACT_SUMMARY`, `NEW_BASELINE_RAW`, or `RECONSTRUCTED_DSIP_RAW`), method/version, metric computation, experiment run IDs, scenario XML checksums, seed lists, plot script, and output paths. Original historical assets should point to their immutable source instead of a made-up plotting script.
4. Never manually relabel methods, axes, or units after export without updating the script.

### 6.7 Revision-specific plotting priorities and stop conditions

1. **Audit original Overleaf figure assets first.** Keep original Figs. 2–7 if the data behind them are not available; make only verified presentation fixes.
2. **FCFS + CCAM-DI:** generate clean, comparable new per-run box plots and selected temporal curves under the preserved SUMO XML routes. Store CSV/Parquet for every new seed; never discard run-level outputs.
3. **Comparison to the manuscript's historical DSIP:** use existing submitted figures and, where available, exact textual/table summaries, with provenance prominently stated. If a reviewer-facing claim requires direct statistical comparison, flag that the missing historical DSIP per-run data prevent a rigorous combined box plot.
4. **If scientifically essential and feasible, after baseline work:** reproduce the required subset using validated reconstructed DSIP so all compared boxes/lines come from a new matched protocol. Never merge reconstructed DSIP output into historical experiments without identification.
5. **Turning-ratio and optional robustness studies:** only plot results that were actually run; record run count, metric definitions, and scenario changes.

**Stop and notify the author** if a requested figure requires nonexistent historical DSIP samples, hidden metrics, or unverified reconstruction. Suggest either (a) preserve old figures plus add separate baseline plots, (b) use an explicitly qualified exact-summary table, or (c) run validated reconstructed DSIP for a limited matched subset. Never fill gaps with artificial sample values or pixels digitized from graphs.

## 7. Experiment and reconstruction rules

1. **Scenario-first.** The author confirms all original SUMO experiment XML files, including route/flow XML, are available. Inventory and hash every `.sumocfg` and referenced `.net.xml`, `.rou.xml`, `.add.xml`; inspect vehicle types, traffic-light programs, speed limits, junction priorities, step lengths, seeds, and demand-generator assumptions. Never infer missing values from filenames. Do not generate replacements unless a file is actually missing or a new sensitivity condition requires it.
2. **Baseline-first, DSIP reconstruction secondary.** Prioritize FCFS and CCAM-DI experiments. Upstream MMD has previously run locally for the author; do not spend revision time re-proving this without a concrete need. Pin MMD and reconstruct only the paper-described DSIP functionality needed for specific supplement tests, after assessing baseline status. Keep reconstruction in `src/dsip_reconstructed/`; never label it the original DSIP implementation or redesign the CBS core.
3. **Validate before using reconstructed DSIP as evidence.** First test original 1:2:1 scenarios for route legality, traffic behavior, safety, metrics, and broad agreement with the paper. Report deviations explicitly. Do not promise an exact match when checkpoint, code, and old route-generation history are unavailable.
4. **Baseline fidelity.** Implement FCFS reservation logic based on the cited method; verify CCAM-DI on its native environment before adapting to DSIP maps. Record each adaptation and any retraining. Do not call a loose approximation an exact reproduction.
5. **Fairness.** Run methods on the same saved route/departure files and common seeds when feasible; compare lane geometry, CAV assumptions, input demand, horizon, definitions of time loss, evaluated vehicle populations, and control/actuation differences. Identical seed numbers **do not** guarantee identical random streams across implementations.
6. **Separate original and new evidence.** Label output by implementation, upstream commit, experiment configuration, SUMO version, seed, date, and metric definition. Preserve historical manuscript numbers as historical claims, not newly verified results.
7. **Safety and feasibility.** GUI observation or absent SUMO collision warnings alone does not establish non-holonomic vehicle feasibility. If additional safety evidence is requested, inspect trajectories and junction detection configuration; report what is measured and what remains unverified.
8. **Prioritized experiments:** (a) FCFS + CCAM-DI baselines, (b) turning-ratio sensitivity using validated reconstructed DSIP, (c) compact CBS latency/timeout statistics, (d) optional limited V2X delay/jitter analysis if technically meaningful. No ablations unless newly authorized.

## 8. Research integrity, references, and reviewer responses

- Keep the complete EIC letter, R1 comments, and R2 attachment accessible in `paper/reviews/` if supplied. Do not silently drop any reviewer item.
- Do not represent Reviewer 1's suggested Klimke paper as reproduced, and do not claim the code is definitively unavailable based only on a search. Cite it correctly and contrast **scope, assumptions, and contributions** rather than inventing benchmark superiority.
- Do not infer from a reference that a claim is proven: verify bibliographic details and DOI before editing `.bib`.
- Track each reviewer response back to a concrete manuscript edit, equation, table, figure, or experiment. Never write “we have conducted ...” before a successful run is recorded.
- Treat the submitted manuscript as a historical snapshot. New experimental results belong to the revision only when produced and documented; if they conflict with old results, escalate rather than concealing the discrepancy.
- Do not disclose private credentials, Overleaf tokens, unpublished reviewer correspondence, or user-specific paths in public repo commits. Recommend private-repo staging until permission to publish research artifacts is confirmed.

## 9. Workflow and agent reporting format

**First action in a new repository:** inventory what exists. **First manuscript action:** perform the audit in Section 4. Do not start modifying algorithms, paper contents, or baselines automatically.

For every task, report:

1. **Goal and scope** — exactly what was requested.
2. **Files inspected** — concrete paths and relevant locations.
3. **Evidence** — what the source, build, code, or experiment actually demonstrates.
4. **Changes made** — path-level summary, distinguishing source edits from generated files.
5. **Validation** — exact commands run, pass/fail, page count, plots/log paths, or reasons validation could not run.
6. **Uncertainty and blockers** — missing assets, suspected mismatch with submitted paper, baseline fidelity limitations, and risks.
7. **Next minimal action** — one bounded recommendation, not a speculative major expansion.

On uncertainty, prefer **audit → document → ask** over guessing or making broad changes. The goal is a focused, defensible 90-day revision, not maximal code production.

## 4.2.0 - 2026-08-11

### Features
- track-ai-plans: Restructure the dashboard information architecture — Plan identity and risk badge first, then handoff next-action hero, summary, tasks, module impact, and collapsible change/audit detail
- track-ai-plans: Add a manual light/dark/auto theme toggle for the dashboard, defaulting to light instead of always following the OS/browser color scheme
- track-ai-plans: Add `planctl.py serve` to start a loopback-only HTTP server and open the dashboard automatically, instead of requiring a manually started server every time (the dashboard's `fetch()` calls are blocked under `file://`)

### Refactor
- track-ai-plans: Separate color tokens for task status (blue/green/amber/red) vs module impact (purple), and render handoff portability with neutral text plus icons instead of reused status colors
- track-ai-plans: Deduplicate module/file impact counts out of the Phase graph; show them once on the module impact map; add visual tiers so Changes and Audit fold by default
- track-ai-plans: Keep list and graph view defaulting to the same current phase (others fold, click to expand); "All phases" stays an explicit opt-in. Clarify that the list/graph toggle scopes to one phase's tasks, separate from the always-visible Phase relationship graph

### Fixes
- track-ai-plans: Fix the phase list accordion expanding every phase card when collapsing the one already open; the list's own expand/collapse state is now tracked separately from the Phase graph's impact-scope selection instead of sharing the same toggle
- track-ai-plans: Move the "all phases" control from the task list toolbar to the module impact map panel it actually scopes, and stop it from touching the task list's expand/collapse state or the task graph's focused phase

## 4.1.0 - 2026-08-11

### Features
- track-ai-plans: Add two-level `phaseGraph` visualization — full Phase dependency graph plus one focused Phase's task graph with cross-Phase boundary links; Phase/task selection scopes impact map, module detail, and change rows; derive the same projection for older frozen V2 snapshots missing `phaseGraph`
- track-ai-plans: Add `create_dashboard_fixture.sh` for disposable multi-Phase dashboard QA fixtures

## 4.0.1 - 2026-08-11

### Fixes
- track-ai-plans: Stop the dashboard mislabeling a migrated `done` item's file as pending; a migrated frozen status now restates the file-match V1's own completion rule already guaranteed, instead of leaving the per-item observations V2's live projection normally fills in empty

## 4.0.0 - 2026-08-11

### Breaking Changes
- track-ai-plans: Store V2 plans and the dashboard under `qing-plans/`; retain safe read-only support and staged migration for legacy `plans/` stores
- track-ai-plans: Replace per-phase review gates with `none` and `single` review policies; `single` independently reviews the initial plan and material amendments

### Features
- track-ai-plans: Discover unfinished plans deterministically across agents and computers with explicit checkpoints, handoff portability, and paused-plan protection
- track-ai-plans: Track an AI-maintained project map, module dependencies, planned/observed/verified files, reasons, execution attribution, amendments, issues, and append-only verification attempts
- track-ai-plans: Add a module-aware dashboard with plan and phase selection, dependency visualization, file evidence, amendments, and handoff status
- track-ai-plans: Add a zh/en language toggle to the dashboard, persisted per browser
- track-ai-plans: Add staged, hash-verified V1 migration that preserves the legacy store and reports when it is safe for the user to delete

### Fixes
- track-ai-plans: Keep the runtime in the skill and install only `dashboard.html` into a repository, so a repository carries its plan data and a self-contained viewer without vendoring an executable copy that can silently drift from the skill that writes it
- track-ai-plans: Give `install-dashboard`, `validate`, and `resume` a clear next step instead of a raw missing-file error when no plan store exists yet, and stop a failed command from leaving an empty `qing-plans/` directory behind
- track-ai-plans: Reject a module dependency that would create a cycle at `upsert-dependency` time instead of only detecting it later in `validate` with no way to undo it
- track-ai-plans: Stop `validate` from failing on a pending-review temporary amendment whose cleanup item is created by that amendment's own (not yet applied) operations
- track-ai-plans: Scope the dashboard's per-plan impact map and dependency edges to that plan's own frozen `status.json` projection instead of the live root `project-map.json`, so a completed or cancelled plan's map no longer changes when a later plan edits modules or dependencies
- track-ai-plans: Downgrade the dashboard's file-verification badge from "verified" to "mismatched" when the observed action disagrees with the planned action, matching the check that already blocks completion
- track-ai-plans: Stop writing `__pycache__` into the user's repository, which previously pinned handoff readiness to `local-only` even on a clean commit
- track-ai-plans: Stop writing an `AGENTS.md` discovery block into the repository root; `qing-plans/index.json` discovery already happens through this skill's own preflight instructions
- track-ai-plans: Compare the checkpoint's recorded commit against `HEAD` by ancestry instead of equality, since the recorded commit is always one commit behind the moment the checkpoint is itself committed with the code — the old check raised a false "HEAD differs from checkpoint" warning on every correctly committed-and-pushed handoff

### Refactor
- track-ai-plans: Split the plan runtime into focused storage, domain, projection, execution, amendment, migration, command, Git, and CLI modules
- track-ai-plans: Consolidate duplicate SHA-256 and Git dirty-path helpers into single implementations

### Documentation
- project: Update the skill catalog description and usage example for `qing-plans`, the `single` review policy, and the dependency-free runtime
- track-ai-plans: Rewrite the reference walkthrough around a neutral CSV-export example instead of one describing the skill's own runtime, so the example no longer doubles as inaccurate architecture guidance

## 3.2.0 - 2026-08-10

### Features
- track-ai-plans: Require a draft plan to pass an independent `review-plan` from a named agent other than the planner before it can activate
- track-ai-plans: Gate a phase's items from entering a later phase until an agent other than every completed-item agent in that phase passes `review-phase`
- track-ai-plans: Show plan review, phase review, and execution gate status in the read-only dashboard
- track-ai-plans: Improve the dashboard's mobile layout
- track-ai-plans: Reject a `--root` value that points directly at a single plan's directory instead of the plans store root

### Documentation
- track-ai-plans: Explain the independent review gates and how they block progress in skill instructions and reference docs
- track-ai-plans: Clarify that reviewer independence requires a separate subagent invocation, not just a different `--actor` name within the same context

## 3.1.0 - 2026-08-08

### Features
- track-ai-plans: Install the read-only dashboard automatically on first plan creation without overwriting an existing copy; keep `install-dashboard` as the explicit refresh command

### Documentation
- track-ai-plans: Explain Git-backed cross-device plan visibility, milestone commits, dashboard serving, and reconciliation of off-plan or mismatched changes
- track-ai-plans: Keep user-authored plan, evidence, and issue text consistent with the user's conversation language

## 3.0.0 - 2026-08-08

### Breaking Changes
- track-ai-plans: Reset persisted plan artifacts from schema version 2 to schema version 1; existing schema-2 stores are rejected

### Refactor
- track-ai-plans: Remove V2 branding from skill instructions, lifecycle documentation, agent metadata, implementation comments, and regression fixtures

## 2.0.0 - 2026-08-08

### Breaking Changes
- Remove the a-share-stock-picker, ai-decision, data-collect, skill-create, and technical-analysis skills from the public collection

### Features
- track-ai-plans: Add a Git-backed plan lifecycle with dependency-aware work tracking, verification evidence, exact file-change coverage, audit events, and a read-only dashboard

### Documentation
- project: Update the skill catalog, installation examples, usage, and dependencies for track-ai-plans

## 1.2.0 - 2026-04-03

### Features
- a-share-stock-picker: Multi-horizon A-share analysis skill with data scripts, watchlists, reports, and T+1 tail workflow
- skill-create: Cursor skill compliance audit guide for reviewing SKILL structure and frontmatter

### Documentation
- project: List new skills in README; bundle release-skills under `.agents/skills/` for agent workflows

## 1.1.0 - 2026-02-05

### Features
- data-collect: add optional tushare provider for A-share K-lines (requires TUSHARE_TOKEN)
- skill-enhancement: add v2 plan for enhanced indicators and a Markdown dashboard

## 1.0.2 - 2026-02-04

### Documentation
- release-skills: Mark skill as internal

## 1.0.1 - 2026-02-04

### Fixes
- data-collect: Add validation for unknown market codes with helpful error message
- data-collect: Correct chip data field range documentation (percentage to 0~1)
- technical-analysis: Add 'ok' field to indicate analysis success/failure status
- technical-analysis: Improve error message with minimum data requirement
- ai-decision: Add validation for technical-analysis output
- ai-decision: Correct chip data field range in trading rules (percentage to 0~1)

## 1.0.0 - 2026-02-04

### Breaking Changes
- data-collect: --date parameter is now required (no default value)

### Features
- data-collect: --date parameter is now required to ensure reproducibility

### Documentation
- Add input/output field specifications and failure handling guide for ai-decision
- Add input/output field specifications and failure handling guide for technical-analysis

## 0.4.0 - 2026-02-04

### Features
- Add release-skills for universal release workflow

### Documentation
- Update installation instructions to use npx skills

## 0.3.3 - 2026-02-03

### Documentation
- Align technical-analysis and ai-decision script docstrings with output/{code}/{date} data flow
- Clarify technical-analysis indicator status (KDJ marked as planned)

## 0.3.2 - 2026-02-03

### Refactor
- Reorganize output directory structure: consolidate files by stock code and date (output/{code}/{date}/{type}.json)

## 0.3.1 - 2026-02-03

### Fixes
- Enhance data-collect script robustness with NaN/null value handling
- Add system proxy disabling for better domestic data source access
- Add 3-retry mechanism for realtime quote fetching
- Standardize date format to YYYY-MM-DD consistently

### Refactor
- Restructure data-collect SKILL.md following Cursor Skills best practices
- Simplify description from 300 to 120 characters
- Implement progressive disclosure pattern with reference documentation

### Documentation
- Add detailed market identification rules (markets.md)
- Add complete output field specifications (fields.md)

## 0.3.0 - 2026-02-03

### Features
- Add file persistence for data pipeline: output/data/, output/analysis/, output/decision/
- Support `--date` parameter for specifying data date (format: YYYY-MM-DD)
- Each step reads from previous step's output file instead of stdin pipe

## 0.2.1 - 2026-02-03

### Fixes
- Graceful degradation when realtime/chip data fetch fails in data-collect
- Fix numpy.bool_ JSON serialization error in technical-analysis

## 0.2.0 - 2026-02-03

### Features
- Add universal release workflow skill with multi-language changelog support

### Fixes
- Fix ai-decision data flow to properly receive chip data from analysis pipeline

### Refactor
- Simplify data-collect SKILL.md structure and remove duplicate content
- Improve technical-analysis to pass through chip/realtime data for downstream skills
- Streamline all skill execution examples with full pipeline commands

## 0.1.0 - 2026-02-03

### Features
- Add data-collect skill for stock data collection (A-share, HK, US, ETF)
- Add technical-analysis skill for MA/MACD/RSI/KDJ analysis
- Add ai-decision skill for investment decision dashboard

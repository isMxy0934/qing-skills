# Skill Enhancement v2 (Indicators + Claude Dashboard)

## TL;DR

> **Quick Summary**: Strengthen `technical-analysis` by adding KDJ/Bollinger/ATR/expanded MA/volume-price indicators and rebalancing the 100-point scoring (profile-based). Improve `ai-decision` output into a Claude-friendly Markdown dashboard, while keeping JSON outputs backward compatible and deterministic.
>
> **Deliverables**:
> - Enhanced indicator + scoring pipeline: `data.json` -> `analysis.json` -> `decision.json`
> - Strategy profiles: `conservative|balanced|aggressive` (default `balanced`)
> - Deterministic JSON contracts preserved; new keys added with `schema_version/strategy_version/profile`
> - `decision.py` prints Markdown dashboard by default; Claude (skill agent) expands narrative in chat

**Estimated Effort**: Large
**Parallel Execution**: YES - 3 waves
**Critical Path**: Update strategy spec (rules + indicator definitions) -> Implement technical-analysis indicators + scoring -> Update ai-decision formatting + compatibility

---

## Context

### Original Request
Enhance three skills (data collection, indicator computation, AI decision). Priority: stronger indicators + more usable output in Claude chat. Focus on “core strategy correctness” and “run first”; no automated tests for now.

### Current Pipeline (repo)
- Data: `skills/data-collect/scripts/collect_stock_data.py` -> `output/<code>/<date>/data.json`
- Analysis: `skills/technical-analysis/scripts/analyze.py` -> `output/<code>/<date>/analysis.json`
- Decision: `skills/ai-decision/scripts/decision.py` -> `output/<code>/<date>/decision.json`

### Confirmed Decisions
- **Authority spec**: `skills/ai-decision/references/trading-rules.md` is the source of truth (update in place).
- **Indicators**: add KDJ, Bollinger Bands, ATR, expanded MA system, volume-price indicators.
- **Scoring**: new indicators affect final score/action; keep 100-point score; rebalance weights.
- **Profiles**: `conservative|balanced|aggressive`, default `balanced`; v1 uses built-in profile defaults (no fine-grained tuning).
- **Data window**: change `data-collect --days` default 60 -> 120.
- **Chip**: display-only (checklist/report), NOT part of scoring.
- **Degrade**: insufficient data/NaN should degrade gracefully (warnings + unavailable fields), avoid hard fail.
- **AI explanation**: Claude generates explanatory narrative in chat; Python remains deterministic and does not call LLM APIs.
- **Output**: `decision.py` prints Markdown dashboard by default; JSON still written.
- **Compatibility**: backward compatible; only add fields; include versioning metadata.
- **Tests**: no automated test framework; verification via agent-executed smoke runs + canonical scenarios derived from `trading-rules.md`.

### Metis Review (guardrails applied)
- Lock down indicator definitions + profile thresholds in `trading-rules.md` first to avoid hidden policy drift.
- Add `--quiet/--format` to avoid breaking existing automation expecting JSON-only output.
- Handle NaN/None, divide-by-zero (KDJ RSV, volume indicators), extreme jumps (cap contributions).

---

## Work Objectives

### Core Objective
Make the strategy stronger and the output more usable in Claude chat, while keeping the pipeline deterministic, reproducible, and backward compatible.

### Concrete Deliverables
- Updated scripts:
  - `skills/data-collect/scripts/collect_stock_data.py`
  - `skills/technical-analysis/scripts/analyze.py`
  - `skills/ai-decision/scripts/decision.py`
- Updated skill docs/spec:
  - `skills/ai-decision/references/trading-rules.md`
  - `skills/technical-analysis/references/indicators.md`
  - `skills/*/SKILL.md`

### Must Have
- End-to-end flow runs and writes files to `output/<code>/<date>/`.
- New indicators included in score/action (per profile) with graceful degradation.
- `analysis.json` / `decision.json` keep existing keys; add `schema_version/strategy_version/profile`.
- `decision.py` default stdout is Markdown dashboard; provide JSON-only option.

### Must NOT Have (Guardrails)
- Do NOT remove/rename existing output keys.
- Do NOT make action dependent on non-deterministic LLM output.
- Do NOT make pipeline fail when a non-critical indicator is unavailable.
- Do NOT expand scope into backtesting/parameter optimization.

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> All verification is agent-executed via commands and file parsing.
> No “ask user to confirm” or “visually check”.

### Test Decision
- **Infrastructure exists**: NO
- **Automated tests**: None (for now)
- **Primary verification**: agent-executed smoke runs + JSON assertions + Markdown stdout assertions

### Agent-Executed QA Scenarios (applies to all tasks)
Each task below includes executable checks. Evidence is captured to `.sisyphus/evidence/` (stdout/stderr dumps, parsed JSON summaries).

Note: To avoid network flakiness (akshare), QA scenarios prefer **synthetic local fixtures** by writing `output/<code>/<date>/data.json` directly when feasible.

---

## Execution Strategy

Wave 1 (Spec + interfaces):
- Task 1 (update trading-rules + indicator spec)
- Task 2 (CLI contract decisions + output versioning fields)

Wave 2 (Core implementation):
- Task 3 (data-collect default days)
- Task 4 (technical-analysis new indicators + scoring + profiles + degrade)

Wave 3 (Output + skill UX):
- Task 5 (ai-decision Markdown dashboard + compatibility + CLI flags)
- Task 6 (SKILL.md updates so Claude generates narrative consistently)

Critical Path: 1 -> 4 -> 5

---

## TODOs

### 1) Update Strategy Spec (rules + indicator definitions)

**What to do**:
- Update `skills/ai-decision/references/trading-rules.md` in place to explicitly define:
  - Profiles: conservative/balanced/aggressive
  - Score→action mapping per profile (thresholds)
  - Hard rules (e.g., bias>5% never buy) and “soft evidence” rules
  - Which indicators exist, what they mean in this strategy
- Update `skills/technical-analysis/references/indicators.md` to include:
  - New indicator definitions (KDJ, Bollinger, ATR, volume-price set)
  - New 100-point weight table (rebalanced)

**Defaults Applied (can be overridden in implementation if needed)**:
- Indicator parameters (initial):
  - KDJ: (9, 3, 3)
  - Bollinger: (20, 2)
  - ATR: (14)
  - MA periods: [5, 10, 20, 60, 120] (optionally 250 if samples allow)
- Volume-price v1 set: OBV + MFI(14) + CMF(20)

- Initial weight proposal (balanced profile, sum=100):
  - Trend/MA system: 22
  - Bias/position vs MA: 18
  - Volume regime: 10
  - Support/Resistance: 10
  - MACD: 10
  - RSI: 6
  - KDJ: 8
  - Bollinger: 6
  - ATR/volatility: 5
  - Volume-price (OBV/MFI/CMF): 5

- Initial score→action proposal (per profile; hard rules still override):
  - conservative: STRONG_BUY>=85, BUY>=70, HOLD>=55, WAIT>=40 else SELL
  - balanced: STRONG_BUY>=80, BUY>=60, HOLD>=45, WAIT>=30 else SELL
  - aggressive: STRONG_BUY>=75, BUY>=55, HOLD>=40, WAIT>=25 else SELL

**Recommended Agent Profile**:
- Category: `writing`
- Skills: `release-skills` (optional), `git-master` (optional)

**Parallelization**:
- Can Run In Parallel: YES (with Task 2)

**References**:
- `skills/ai-decision/references/trading-rules.md` - authority spec to update
- `skills/technical-analysis/references/indicators.md` - indicator doc + weights
- `skills/technical-analysis/scripts/analyze.py` - current weights/logic to mirror in spec

**Acceptance Criteria (agent-executable)**:
- File contains explicit sections for: Profiles, Weights (100pt), Indicator definitions, Hard rules.
- Agent verifies via simple grep/read: the new indicator keywords exist (KDJ/Bollinger/ATR/OBV/MFI/CMF).

---

### 2) Decide and Document CLI / Output Metadata Contract

**What to do**:
- Define versioning keys and where they live (backward compatible). Proposed:
  - `analysis.json.meta = { schema_version, strategy_version, profile }`
  - `decision.json.meta = { schema_version, strategy_version, profile }`
- Define CLI flags (minimal but prevents breakage):
  - `technical-analysis`: add `--profile` (default balanced)
  - `ai-decision`: add `--format md|json` and `--quiet` (or `--no-print`)
- Ensure `decision.py` behavior is safe for automation (JSON-only option).

**Recommended Agent Profile**:
- Category: `unspecified-low`
- Skills: `git-master`

**Parallelization**:
- Can Run In Parallel: YES (with Task 1)
- Blocks: Tasks 4, 5

**References**:
- `skills/technical-analysis/SKILL.md` - update usage examples later
- `skills/ai-decision/SKILL.md` - update usage examples later
- `skills/ai-decision/scripts/decision.py` - current argparse
- `skills/technical-analysis/scripts/analyze.py` - current argparse

**Acceptance Criteria (agent-executable)**:
- Spec decision recorded in docs (either in SKILL.md or references) with exact flag names.

---

### 3) Update data-collect default window to 120 days

**What to do**:
- Change default `--days` from 60 to 120 in `collect_stock_data.py`.
- Update `skills/data-collect/SKILL.md` examples and parameter description if needed.

**Must NOT do**:
- Do not change output path structure.

**Recommended Agent Profile**:
- Category: `quick`
- Skills: `git-master`

**Parallelization**:
- Can Run In Parallel: YES (with Task 4 once specs are clear)

**References**:
- `skills/data-collect/scripts/collect_stock_data.py` - argparse default at bottom
- `skills/data-collect/SKILL.md` - docs claim default is 60

**Acceptance Criteria (agent-executable)**:
- `python skills/data-collect/scripts/collect_stock_data.py --help` shows default days=120.

**Agent-Executed QA Scenario**:
```
Scenario: data-collect default days is 120
  Tool: Bash
  Steps:
    1. Run: python skills/data-collect/scripts/collect_stock_data.py --help > .sisyphus/evidence/task-3-data-collect-help.txt
    2. Assert: help text contains "default" and "120" near --days
  Evidence: .sisyphus/evidence/task-3-data-collect-help.txt
```

---

### 4) Implement new indicators + rebalanced scoring + profiles in technical-analysis

**What to do**:
- Add indicator calculations:
  - KDJ (handle RSV denominator=0; early NaN)
  - Bollinger Bands (middle/upper/lower, band width, position)
  - ATR (volatility regime; use for risk notes and/or scoring)
  - Expanded MA (add MA120; optionally MA250 if available; add slope/stacking features)
  - Volume-price indicators (choose minimal v1 set; handle zero-volume)
- Rebalance 100-point scoring weights to include new dimensions (profile-based weights/thresholds).
- Add `--profile` flag; write profile into output metadata.
- Degrade gracefully:
  - If an indicator cannot be computed: mark `unavailable=true` + `reason`, add warning, and continue.
- Maintain backward compatibility:
  - Keep existing keys: `trend`, `bias`, `macd`, `volume`, `signal`, etc.
  - Add new blocks under new keys (e.g. `kdj`, `bollinger`, `atr`, `ma_system`, `volume_price`, `warnings`, `meta`).

**Must NOT do**:
- Do not change meaning/shape of existing stable fields.
- Do not let one extreme indicator dominate (cap contributions if needed).

**Recommended Agent Profile**:
- Category: `unspecified-high`
- Skills: `git-master`

**Parallelization**:
- Can Run In Parallel: NO (depends on Task 1+2)
- Blocks: Task 5

**References**:
- `skills/technical-analysis/scripts/analyze.py` - current indicator + scoring implementation
- `skills/technical-analysis/references/indicators.md` - current weights and definitions
- `skills/ai-decision/references/trading-rules.md` - hard rules to remain consistent

**Acceptance Criteria (agent-executable)**:
- Running analysis produces `analysis.json` with:
  - Existing keys unchanged
  - New keys present when computable (kdj/bollinger/atr/...)
  - `meta.profile` equals selected profile
  - `meta.schema_version` and `meta.strategy_version` present
- Degrade check: with a deliberately short `data.json` (e.g. 20 bars) analysis completes and sets some new indicator blocks to `unavailable=true` with warnings.

**Agent-Executed QA Scenarios**:
```
Scenario: technical-analysis runs on a synthetic local data.json (no network)
  Tool: Bash
  Steps:
    1. Create synthetic fixture (120 bars) at output/TEST/2025-01-01/data.json:
       python - <<'PY'
       import os, json
       from datetime import date, timedelta
       code='TEST'; d='2025-01-01'
       out_dir=os.path.join('output', code, d)
       os.makedirs(out_dir, exist_ok=True)
       start=date(2024, 6, 1)
       klines=[]
       price=100.0
       for i in range(120):
         day=start + timedelta(days=i)
         # simple trending + mild noise (deterministic)
         price = price * (1.0005)
         o=price*0.998; h=price*1.005; l=price*0.995; c=price
         klines.append({
           'date': day.isoformat(),
           'open': round(o,2), 'high': round(h,2), 'low': round(l,2), 'close': round(c,2),
           'volume': 1000000 + i*1000,
           'amount': round((1000000 + i*1000) * c, 2),
           'pct_chg': 0.05,
         })
       data={'code':code,'name':'Synthetic','market':'A股','source':'synthetic','update_time':d,'klines':klines,'realtime':None,'chip':None}
       json.dump(data, open(os.path.join(out_dir,'data.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=2)
       print(os.path.join(out_dir,'data.json'))
       PY
    2. Run: python skills/technical-analysis/scripts/analyze.py TEST --date 2025-01-01 --profile balanced > .sisyphus/evidence/task-4-analysis-synth.json
    3. Assert file exists: output/TEST/2025-01-01/analysis.json
    4. Parse JSON and assert required keys + meta:
       python - <<'PY'
       import json
       p='output/TEST/2025-01-01/analysis.json'
       d=json.load(open(p,'r',encoding='utf-8'))
       assert d.get('ok') is True
       for k in ['trend','bias','macd','volume','signal']:
         assert k in d
       m=d.get('meta',{})
       assert m.get('profile') in ['conservative','balanced','aggressive']
       assert 'schema_version' in m and 'strategy_version' in m
       PY
  Evidence: .sisyphus/evidence/task-4-analysis-synth.json

Scenario: technical-analysis runs and writes analysis.json with new keys
  Tool: Bash
  Preconditions: data.json exists (from Task 3 run)
  Steps:
    1. Run: python skills/technical-analysis/scripts/analyze.py 600519 --date 2025-01-01 > .sisyphus/evidence/task-4-analysis-stdout.json
    2. Assert file exists: output/600519/2025-01-01/analysis.json
    3. Run python -c to load JSON and assert keys/meta:
       python - <<'PY'
       import json
       p='output/600519/2025-01-01/analysis.json'
       d=json.load(open(p,'r',encoding='utf-8'))
       assert d.get('ok') is True
       for k in ['trend','bias','macd','volume','signal']:
         assert k in d
       assert 'meta' in d and 'profile' in d['meta']
       PY
  Evidence:
    - .sisyphus/evidence/task-4-analysis-stdout.json

Scenario: profile flag changes meta.profile
  Tool: Bash
  Steps:
    1. Run: python skills/technical-analysis/scripts/analyze.py 600519 --date 2025-01-01 --profile aggressive > .sisyphus/evidence/task-4-profile-aggressive.json
    2. Parse meta.profile equals "aggressive"
  Evidence: .sisyphus/evidence/task-4-profile-aggressive.json
```

---

### 5) Upgrade ai-decision: Markdown dashboard stdout + compatibility + flags

**What to do**:
- Keep deterministic decision fields driven by `analysis.json` score/action.
- Print a compact Markdown dashboard by default (Claude-friendly), including:
  - Core conclusion (action/score/confidence)
  - Key price levels (ideal/secondary buy, stop, take-profit, R:R)
  - Checklist table (YES/WARN/NO)
  - Indicator highlights (include new indicators if present)
  - Warnings (including unavailable indicators)
- Add `--format md|json` (default `md`) and `--quiet` (no stdout).
- Backward compatibility:
  - If new indicator blocks are missing in old `analysis.json`, still produce `decision.json` and include warnings.
- Add metadata (`meta.schema_version/strategy_version/profile`) in `decision.json`.

**Must NOT do**:
- Do not call external LLM APIs.
- Do not contradict `trading-rules.md` hard rules.

**Recommended Agent Profile**:
- Category: `unspecified-high`
- Skills: `git-master`

**Parallelization**:
- Can Run In Parallel: NO (depends on Task 4)

**References**:
- `skills/ai-decision/scripts/decision.py` - current output + argparse
- `skills/ai-decision/SKILL.md` - docs and usage examples
- `skills/ai-decision/references/trading-rules.md` - checklist template + thresholds

**Acceptance Criteria (agent-executable)**:
- `python skills/ai-decision/scripts/decision.py 600519 --date 2025-01-01`:
  - Writes `output/600519/2025-01-01/decision.json`
  - Stdout begins with Markdown (e.g., `#` header) and contains action/score
- `--format json` prints valid JSON only (no Markdown)
- `--quiet` produces empty stdout but still writes decision.json
- Backward compatibility check: if `analysis.json` is missing new indicator blocks, decision still completes and writes `decision.json` with warnings.

**Agent-Executed QA Scenarios**:
```
Scenario: ai-decision runs on synthetic analysis.json (no network)
  Tool: Bash
  Preconditions: output/TEST/2025-01-01/analysis.json exists (from Task 4 synthetic scenario)
  Steps:
    1. Run: python skills/ai-decision/scripts/decision.py TEST --date 2025-01-01 > .sisyphus/evidence/task-5-decision-synth-md.txt
    2. Assert: output/TEST/2025-01-01/decision.json exists
    3. Parse decision.json and assert meta/profile exists and action is in allowed set:
       python - <<'PY'
       import json
       p='output/TEST/2025-01-01/decision.json'
       d=json.load(open(p,'r',encoding='utf-8'))
       allowed=set(['强烈买入','买入','持有','观望','卖出','强烈卖出'])
       assert d.get('summary',{}).get('action') in allowed
       m=d.get('meta',{})
       assert m.get('profile') in ['conservative','balanced','aggressive']
       PY
  Evidence: .sisyphus/evidence/task-5-decision-synth-md.txt

Scenario: Default ai-decision prints Markdown dashboard
  Tool: Bash
  Steps:
    1. Run: python skills/ai-decision/scripts/decision.py 600519 --date 2025-01-01 > .sisyphus/evidence/task-5-decision-md.txt
    2. Assert: output/600519/2025-01-01/decision.json exists
    3. Assert: first line of stdout starts with "#" and contains stock code/name
  Evidence: .sisyphus/evidence/task-5-decision-md.txt

Scenario: JSON-only output mode
  Tool: Bash
  Steps:
    1. Run: python skills/ai-decision/scripts/decision.py 600519 --date 2025-01-01 --format json > .sisyphus/evidence/task-5-decision-json.txt
    2. Parse: python -c "import json; json.load(open('.sisyphus/evidence/task-5-decision-json.txt','r',encoding='utf-8'))"
  Evidence: .sisyphus/evidence/task-5-decision-json.txt
```

---

### 6) Update SKILL.md so Claude expands narrative consistently (no policy drift)

**What to do**:
- Update:
  - `skills/technical-analysis/SKILL.md` (new indicators, `--profile`, new output fields)
  - `skills/ai-decision/SKILL.md` to instruct Claude:
    - Treat `decision.json` as authoritative for action/levels/checklist
    - Provide explanation that never contradicts deterministic output
    - Use `trading-rules.md` as source of truth
    - Keep narrative concise (dashboard-first), then optional deeper notes
- Ensure `README.md` usage flow stays accurate if CLI flags changed.

**Recommended Agent Profile**:
- Category: `writing`
- Skills: `git-master`

**Parallelization**:
- Can Run In Parallel: YES (after Task 5 begins, but final pass after Task 5 complete)

**References**:
- `skills/ai-decision/SKILL.md` - skill instructions and triggering description
- `skills/technical-analysis/SKILL.md` - skill instructions and usage
- `README.md` - overall workflow docs

**Acceptance Criteria (agent-executable)**:
- `SKILL.md` files reflect new flags and outputs.
- Agent verifies via reading that they include explicit “do not contradict decision.json” guardrail.

---

## Commit Strategy

- Prefer 3 commits (if the user wants commits):
  1. `docs: update strategy spec and indicator definitions`
  2. `feat(analysis): add indicators, profiles, and rebalanced scoring`
  3. `feat(decision): markdown dashboard output and compatibility flags`

---

## Success Criteria

### Verification Commands (agent-executable)
```bash
# Example run (uses network via akshare):
python skills/data-collect/scripts/collect_stock_data.py 600519 --date 2025-01-01
python skills/technical-analysis/scripts/analyze.py 600519 --date 2025-01-01 --profile balanced
python skills/ai-decision/scripts/decision.py 600519 --date 2025-01-01
```

### Final Checklist
- [ ] End-to-end flow produces data.json / analysis.json / decision.json
- [ ] analysis.json and decision.json include version/profile metadata
- [ ] New indicators present when computable; otherwise marked unavailable with warnings
- [ ] decision.py prints Markdown by default and supports JSON-only + quiet modes
- [ ] trading-rules.md and indicators.md reflect the implemented strategy

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

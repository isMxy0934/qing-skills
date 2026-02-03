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

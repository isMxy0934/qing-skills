## 0.2.1 - 2026-02-03

### 修复
- data-collect 实时行情/筹码数据获取失败时优雅降级，不阻断主流程
- 修复 technical-analysis 中 numpy.bool_ 无法 JSON 序列化的问题

## 0.2.0 - 2026-02-03

### 新功能
- 新增通用发布工作流技能，支持多语言 changelog

### 修复
- 修复 ai-decision 数据流，正确从分析管道接收筹码数据

### 重构
- 精简 data-collect SKILL.md 结构，移除重复内容
- 改进 technical-analysis 透传 chip/realtime 数据供下游技能使用
- 统一所有技能的执行示例为完整管道命令

## 0.1.0 - 2026-02-03

### 新功能
- 新增 data-collect 技能，支持收集 A股/港股/美股/ETF 行情数据
- 新增 technical-analysis 技能，支持 MA/MACD/RSI/KDJ 技术分析
- 新增 ai-decision 技能，生成投资决策仪表盘

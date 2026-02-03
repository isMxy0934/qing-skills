## 0.3.2 - 2026-02-03

### 重构
- 重组输出目录结构：按股票代码和日期整合文件（output/{code}/{date}/{type}.json）

## 0.3.1 - 2026-02-03

### 修复
- 增强 data-collect 脚本健壮性，添加 NaN/空值安全处理
- 禁用系统代理，改善国内数据源访问
- 为实时行情获取添加 3 次重试机制
- 统一日期格式为 YYYY-MM-DD

### 重构
- 按照 Cursor Skills 最佳实践重构 data-collect SKILL.md
- 精简描述从 300 字符到 120 字符
- 实现渐进式披露模式，添加参考文档

### 文档
- 新增详细的市场识别规则说明（markets.md）
- 新增完整的输出字段规范说明（fields.md）

## 0.3.0 - 2026-02-03

### 新功能
- 新增数据持久化：output/data/、output/analysis/、output/decision/
- 支持 `--date` 参数指定数据日期（格式：YYYY-MM-DD）
- 各步骤从上一步的输出文件读取，不再依赖管道

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

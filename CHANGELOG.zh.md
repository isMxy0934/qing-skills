## 3.2.0 - 2026-08-10

### 新功能
- track-ai-plans：草案计划激活前必须通过独立的 `review-plan`，审查者须是与 planner 不同的具名 agent
- track-ai-plans：阶段内所有任务完成后,须由该阶段内非任何 completedBy 的 agent 通过 `review-phase`，后续阶段才能解除阻塞
- track-ai-plans：仪表盘展示计划审查、阶段审查与执行门禁状态
- track-ai-plans：优化仪表盘移动端布局
- track-ai-plans：拒绝直接指向单个计划目录（而非 plans 存储根目录）的 `--root` 值

### 文档
- track-ai-plans：在技能说明与参考文档中解释独立审查门禁及其阻塞进度的方式
- track-ai-plans：明确审查独立性要求由独立的 subagent 调用完成，而非在同一上下文中更换 `--actor` 名称

## 3.1.0 - 2026-08-08

### 新功能
- track-ai-plans：首次创建计划时自动安装只读仪表盘且不覆盖现有副本；保留 `install-dashboard` 作为显式刷新命令

### 文档
- track-ai-plans：说明 Git 支持的跨设备计划可见性、里程碑提交、仪表盘服务与计划外或动作不匹配变更的对账流程
- track-ai-plans：使用户编写的计划、验证证据与问题文本和用户的对话语言保持一致

## 3.0.0 - 2026-08-08

### 破坏性变更
- track-ai-plans：将持久化计划数据的 schema 版本从 2 重置为 1；现有 schema 2 数据将被拒绝

### 重构
- track-ai-plans：移除技能说明、生命周期文档、Agent 元数据、实现注释与回归测试中的 V2 品牌措辞

## 2.0.0 - 2026-08-08

### 破坏性变更
- 从公开技能集中移除 a-share-stock-picker、ai-decision、data-collect、skill-create 和 technical-analysis

### 新功能
- track-ai-plans：新增 Git 支持的计划生命周期，包含依赖感知的任务跟踪、验证证据、精确文件变更覆盖、审计事件与只读仪表盘

### 文档
- project：更新 track-ai-plans 的技能目录、安装示例、用法与依赖说明

## 1.2.0 - 2026-04-03

### 新功能
- a-share-stock-picker: A 股多周期选股与分析技能，含数据采集脚本、自选池、报告与 T+1 尾盘流程
- skill-create: 符合 Cursor 技能规范的审查指南（结构、frontmatter、渐进式披露）

### 文档
- project: README 补充新技能说明；在 `.agents/skills/` 下提供 release-skills 副本供 Agent 使用

## 1.1.0 - 2026-02-05

### 新功能
- data-collect: 新增 tushare 数据源选项（A 股 K 线，需 TUSHARE_TOKEN）
- skill-enhancement: 新增 v2 方案，包含增强指标与 Markdown 仪表盘

## 1.0.2 - 2026-02-04

### 文档
- release-skills: 标记技能为 internal

## 1.0.1 - 2026-02-04

### 修复
- data-collect: 为未知市场代码添加验证和友好错误提示
- data-collect: 修正筹码数据字段范围说明（百分比改为 0~1）
- technical-analysis: 添加 'ok' 字段标识分析成功/失败状态
- technical-analysis: 改进错误提示，明确最少数据要求
- ai-decision: 添加对上游分析数据的验证
- ai-decision: 修正交易规则中筹码字段范围说明（百分比改为 0~1）

## 1.0.0 - 2026-02-04

### 破坏性变更
- data-collect: --date 参数现在是必填的（不再有默认值）

### 新功能
- data-collect: --date 参数改为必填以确保可复现性

### 文档
- 为 ai-decision 添加输入输出字段说明和失败处理指南
- 为 technical-analysis 添加输入输出字段说明和失败处理指南

## 0.4.0 - 2026-02-04

### 新功能
- 新增 release-skills 通用发布工作流技能

### 文档
- 更新安装说明为 npx skills 命令

## 0.3.3 - 2026-02-03

### 文档
- 修正脚本说明：technical-analysis/ai-decision 头部输入输出路径与 output/{code}/{date} 一致
- README 中明确指标状态：已实现 MA/MACD/RSI，KDJ 为计划实现

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

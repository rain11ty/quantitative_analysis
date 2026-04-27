# 操作日志

> 本文件记录项目的关键操作和维护历史

## 2026-04-27 文档全面更新

**操作内容**：对 `docs/` 目录下所有过时文档进行全面审查和更新

**更新的文件**：
- ✅ `docs/guides/CURRENT_WORKSPACE_STRUCTURE.md` — 完全重写（反映 22 个模型/13 个服务/24 个模板/新模块）
- ✅ `docs/guides/PROJECT_STRUCTURE.md` — 完全重写
- ✅ `docs/analysis/DEVELOPMENT_SUMMARY.md` — 完全重写（旧版仅描述 7 张表早期版本）
- ✅ `docs/README_balance_sheet.md` — 更新路径和说明
- ✅ `docs/README_cash_flow.md` — 更新路径和说明
- ✅ `docs/README_income_statement.md` — 更新路径和说明

**变更原因**：上述文档的内容严重滞后（仍描述项目早期版本），包含错误的路径引用（如 `/Users/henrylin/...`）、过时的功能清单（如"待扩展：K线图表集成""待扩展：策略回测功能"而这些功能早已实现）、缺失的新模块（新闻/AI/实时监控/Celery/Redis 缓存/邮件服务等均未提及）

---

## 2026-04-27 CRUD 完整性审计 & 修复

**操作内容**：完成全系统 12 大模块的逐源码级 CRUD 审计

**产出文档**：`docs/SYSTEM_CRUD_AUDIT_REPORT.md`

**关键发现**：
- 🔴 2 个必修复项：分析记录缺 R/U/D / 回测结果无法持久化
- 🟡 5 个建议改进项：自选股缺编辑 / 选股条件不能存预设 / 新闻无缓存 / AI 双重写入 / 管理员列表无分页
- ⚠️ 5 个 ORM 模型零引用：TradingSignals / PortfolioPositions / RiskAlerts / StockIncomeStatement / StockBalanceSheet
- ⚠️ backtest_engine.py 空壳陷阱：实际实现在 analysis_api.py 内部类

**修复动作**：创建 `scripts/migrate_v20260427_crud_fix.py` 迁移脚本

---

## 2026-04-27 数据库使用情况评估

**操作内容**：全面分析 22 张 ORM 模型的实际使用情况

**结论**：
- 未使用的 5 张表不影响运行时性能（ORM 定义 ≠ 数据库操作）
- 真正有开销的问题是 AI 对话双重写入（UserAiConversation + UserChatHistory 同时写）
- 建议：答辩前统一聊天记录到新体系，死模型加注释标注"预留扩展"

---

## 2026-04-26 ~ 2026-04-27 新增模块记录

近期新增的功能模块：

1. **新闻资讯模块**：`news_api.py` + `news_service.py` + `news.html`（4 源聚合）
2. **邮件服务**：`email_service.py`（Resend SMTP 验证码）
3. **Celery 异步队列**：`celery_app.py` + `tasks.py`（预留配置）
4. **Redis 双层缓存**：`cache_utils.py`（自动降级为内存字典）
5. **新增 ORM 模型**：`stock_cyq_chips.py`（筹码分布明细）+ `stock_shock.py`（异动信息）
6. **管理员健康检查页**：`admin/health_check.html`（四组件连通性检测）
7. **每日自动更新**：`daily_auto_update.py`（增量同步调度）
8. **数据健康巡检**：`data_health_check.py`
9. **DB 索引优化**：`add_db_indexes.py`
10. **V2 因子补算**：`backfill_factors_v2.py`（替代 V1 版）

---

## 2025-01-27 前端 Bug 修复（历史记录）

### formatNumber 函数未定义问题（跨页面批量修复）

**问题**：多个页面使用了 `formatNumber` / `formatPercent` 函数但未定义，导致 JavaScript 运行时报错

**影响的页面**：
- ✅ `analysis.html` — 已修复
- ✅ `stock_detail.html` — 已修复
- ✅ `screen.html` — 已修复
- ✅ `backtest.html` — 已修复

**修复方案**：在每个页面的 `<script>` 区域添加工具函数定义

**后续建议**（当时提出，部分已实施）：
- 将通用工具函数提取到公共 JS 文件（`base.html` 已部分解决此问题）
- 增加前端单元测试

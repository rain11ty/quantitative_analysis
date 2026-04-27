# Quantitative Analysis

一个基于 Flask 的 A 股量化分析项目，当前主线功能已经收敛到 Web 应用、行情概览、选股/回测、实时监控、AI 助手、用户体系和后台管理。

## 当前功能

- 股票列表、详情页、历史行情、技术因子、资金流向、筹码分布
- 市场概览与市场数据健康检查
- 条件筛选与简单策略回测
- 实时监控看板
- AI 助手会话与聊天接口
- 用户登录/注册/个人中心/自选股/回测记录
- 管理后台与系统日志

## 快速启动

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python run.py
```

默认访问地址：

- Web: `http://127.0.0.1:5001`
- Health: `http://127.0.0.1:5001/healthz`
- API 示例: `http://127.0.0.1:5001/api/stocks`

如果想用辅助启动方式，也可以运行：

```bash
python quick_start.py
python run_system.py --menu
```

## 目录结构

```text
quantitative_analysis/
|-- app/                  Flask 应用主体
|   |-- api/              API 路由
|   |-- main/             页面路由
|   |-- models/           SQLAlchemy 模型
|   |-- routes/           认证和后台蓝图
|   |-- services/         业务服务
|   |-- static/           当前生效的静态资源
|   |-- templates/        当前生效的模板
|   `-- utils/            基础工具函数与数据脚本
|-- deploy/               Docker / Nginx / service 示例
|-- docs/                 当前项目文档
|-- scripts/              数据同步、诊断、维护脚本
|-- models/               演示模型文件
|-- quick_start.py        轻量启动脚本
|-- run.py                主入口
|-- run_system.py         菜单式启动入口
`-- start.bat/start.sh    平台启动脚本
```

## 文档入口

- 安装说明：[docs/guides/INSTALL_GUIDE.md](/D:/G/工作与学习/大四下/lianghua/quantitative_analysis/docs/guides/INSTALL_GUIDE.md)
- 目录说明：[docs/guides/PROJECT_STRUCTURE.md](/D:/G/工作与学习/大四下/lianghua/quantitative_analysis/docs/guides/PROJECT_STRUCTURE.md)
- 工作区盘点：[docs/guides/CURRENT_WORKSPACE_STRUCTURE.md](/D:/G/工作与学习/大四下/lianghua/quantitative_analysis/docs/guides/CURRENT_WORKSPACE_STRUCTURE.md)
- 数据库说明：[docs/guides/database.md](/D:/G/工作与学习/大四下/lianghua/quantitative_analysis/docs/guides/database.md)
- 当前审查结论：[docs/analysis/CURRENT_PROJECT_REVIEW.md](/D:/G/工作与学习/大四下/lianghua/quantitative_analysis/docs/analysis/CURRENT_PROJECT_REVIEW.md)

## 当前边界

- 旧 `ml_factor` 文档已不再保留为当前主线资料。
- `/analysis` 路由现在是兼容性入口，会重定向到股票列表。
- 财务三表相关脚本仍属于数据准备工具，而不是前台已上线页面。

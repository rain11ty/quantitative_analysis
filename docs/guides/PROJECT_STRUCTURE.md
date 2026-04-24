# Project Structure

## Active areas

### `app/`

当前运行中的 Flask 应用主体。

- `api/`: JSON API
- `main/`: 页面入口
- `routes/`: 认证和管理后台
- `services/`: 业务逻辑
- `models/`: SQLAlchemy 模型
- `templates/` / `static/`: 当前生效的前端资源

### `scripts/`

手工脚本集中区，避免一次性脚本继续堆在仓库根目录。

- `setup/`: 初始化准备脚本
- `diagnostics/`: 手工烟雾检查、联通性检查
- `db_tools/`: 手工数据库查看工具

### `docs/guides/`

当前有效、面向日常开发和维护的文档。

### `docs/archive/`

已下线模块的历史资料。这里的内容默认不再代表当前系统实现。

## Root directory rules

仓库根目录只保留以下几类文件：

- 应用入口：`run.py`、`quick_start.py`、`run_system.py`
- 配置与依赖：`config.py`、`requirements*.txt`
- 部署文件：`Dockerfile`、`docker-compose*.yml`
- 平台启动脚本：`start.bat`、`start.sh`

以下内容不应该再直接堆在根目录：

- 一次性编码修复脚本
- 临时测试脚本
- 编辑器恢复脚本
- 手工导出的排障文本
- 已删除功能的页面资源

## Cleanup notes

这次梳理做了几件事：

- 删除了旧版 `ml_factor` 页面资源
- 把手工诊断脚本移动到 `scripts/diagnostics/`
- 把数据库查看工具移动到 `scripts/db_tools/`
- 把已下线模块文档归档到 `docs/archive/ml_factor/`

后续新增脚本时，优先放到 `scripts/` 对应子目录，不要再直接放到仓库根目录。

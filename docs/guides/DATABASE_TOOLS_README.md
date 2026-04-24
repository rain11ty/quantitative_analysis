# Database Tools

仓库保留了一组手工数据库查看工具，方便在排查数据问题时直接连库检查。

这些工具不属于 Web 应用运行主链路，也不会在 `run.py` 中自动加载。

## 目录

- `scripts/db_tools/database_explorer.py`
- `scripts/db_tools/db_viewer.py`

## 使用方式

在项目根目录执行：

```bash
python scripts/db_tools/database_explorer.py
python scripts/db_tools/db_viewer.py
```

## 适用场景

- 查看当前数据库有哪些表
- 检查核心行情表和财务表的结构
- 抽样核对某只股票的数据是否完整
- 在重跑数据任务前先做人工巡检

## 注意事项

- 这两个脚本直接读取数据库连接参数，默认值仍然偏本地开发环境
- 它们更适合人工排障，不建议作为生产自动化脚本直接调用
- 如果要做正式的数据巡检任务，建议基于 `app/models` 和 `app/services` 再封装一层更稳定的命令行入口

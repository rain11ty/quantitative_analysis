# Current Project Review

## Main problems

### 1. Documentation drift

旧 README 和安装文档长期描述已经删除的 `ml_factor` 页面、`app.py` 入口、`quick_start_fixed.py` 和不存在的示例脚本，容易让维护者误判项目状态。

### 2. Root directory was overloaded

仓库根目录之前混杂了：

- 手工排障脚本
- 编码修复脚本
- 编辑器恢复脚本
- 旧版前端资源
- 导出的文本产物

这会让真正的主入口不够明显，也增加误执行风险。

### 3. Manual checks and docs were mixed with runtime code

数据库查看工具和联通性检查脚本本身有价值，但应该集中放到 `scripts/`，而不是和应用入口放在同一层。

### 4. Runtime edge cases still need attention

- 错误页渲染依赖曾缺少 `render_template` 导入
- 自动化测试仍然偏弱
- 入口脚本和部署脚本之间曾存在端口与功能说明不一致

## Recommended next steps

1. 给 `app/services/` 的关键服务补一层 `pytest` 单元测试和 API 集成测试。
2. 把数据库配置进一步拆成开发、测试、生产三套，降低本地 MySQL 耦合。
3. 逐步清理 `docs/analysis/` 中剩余的历史分析文档，保留对当前系统仍然有效的部分。
4. 给 `scripts/diagnostics/` 中真正稳定的检查逻辑补上统一入口，避免脚本继续分散增长。

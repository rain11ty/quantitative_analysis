# 安装与启动指南

> 更新日期：`2026-04-28`

## 1. 环境要求

- Python `3.8+`
- MySQL `8.x`
- Redis `可选`
- Tushare Token `推荐准备`
- DeepSeek / Qwen / OpenAI / Ollama `至少一种 AI 提供方，若要使用 AI 助手`

## 2. 安装依赖

在项目根目录执行：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

如果只是在 Windows 本地开发，`run.py` 和 `quick_start.py` 已经会先做 UTF-8 环境修复。

## 3. 配置 `.env`

```bash
copy .env.example .env
```

至少需要根据实际环境填写：

- `DB_HOST`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `SECRET_KEY`

如果要启用行情与 AI：

- `TUSHARE_TOKEN`
- `DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY`

如果要启用 Redis 缓存：

- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_DB`

## 4. 初始化数据库

最简单的做法是：

```bash
python run_system.py --menu
```

然后选择初始化数据库。

如果模型表已存在，可以直接跳过这一步。

## 5. 启动方式

### 方式一：标准启动

```bash
python run.py
```

默认地址：

- Web：`http://127.0.0.1:5001`
- 健康检查：`http://127.0.0.1:5001/healthz`

### 方式二：快速启动

```bash
python quick_start.py
```

### 方式三：菜单式启动

```bash
python run_system.py --menu
```

## 6. 常见可选组件

### Redis

Redis 不是强制依赖。

即使 Redis 不可用，应用也会自动降级到进程内缓存，只是跨进程共享能力会消失。

### 邮件服务

如果没有配置 `MAIL_USERNAME` 和 `MAIL_PASSWORD`，邮件验证码能力会被禁用。

### AI 服务

默认推荐 `DeepSeek`。如果你准备接入通义千问，请设置 `LLM_PROVIDER=qwen` 并配置 `DASHSCOPE_API_KEY`；如果未配置云端 API key，也可以改用 `Ollama` 本地模型，但 AI 助手页面必须有可用提供方才具备完整能力。

## 7. 首次启动后的建议检查

1. 打开首页确认页面可访问。
2. 访问 `/healthz` 查看数据库和 Redis 状态。
3. 访问 `/api/market/overview` 确认市场概览接口正常。
4. 如果要验证 AI，再访问 `/api/ai/status`。

## 8. 已知边界

- 财务三表脚本不是主启动流程的一部分。
- `scripts/sync_tushare_data.py` 主要负责行情类同步，不会自动把所有财务脚本都跑一遍。
- 旧 `ml_factor` 归档不再是当前系统的一部分。

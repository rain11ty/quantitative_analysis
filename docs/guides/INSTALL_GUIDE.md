# Install Guide

## Requirements

- Python 3.8+
- MySQL 5.7+ or compatible MySQL service
- Windows PowerShell or a Unix-like shell

## 1. Create a virtual environment

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

如果你只是做最小化环境验证，也可以安装：

```bash
pip install -r requirements_minimal.txt
```

## 3. Configure environment variables

复制示例配置并按实际环境修改：

```bash
copy .env.example .env
```

至少确认下面这些配置正确：

- `DB_HOST`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `SECRET_KEY`
- `DEBUG`

## 4. Start the app

推荐直接用主入口：

```bash
python run.py
```

可选启动方式：

```bash
python quick_start.py
python run_system.py --menu
start.bat
./start.sh
```

默认地址：

- Web: `http://127.0.0.1:5001`
- Health: `http://127.0.0.1:5001/healthz`

## 5. Initialize the database

如果数据库表还没有创建，可以运行：

```bash
python run_system.py --menu
```

然后在菜单中选择 `Initialize database`。

## Troubleshooting

### SECRET_KEY error

生产环境必须显式设置 `SECRET_KEY`。如果没有设置，应用会拒绝在生产模式下启动。

### Database connection failed

- 检查 `.env` 中的数据库配置
- 确认 MySQL 服务可连接
- 确认数据库名已经创建

### Optional market data providers are unavailable

项目支持 Tushare 和 AkShare 的健康检查；当外部数据源不可用时，部分市场概览功能会降级，但 Web 应用本身仍可启动。

### Dependency install failures

如果某些机器学习依赖安装较慢或失败，可以先使用 `requirements_minimal.txt` 完成基础启动，再按需补装扩展依赖。

FROM python:3.11-slim

LABEL maintainer="stock-analysis" \
      description="Stock Quantitative Analysis System with LLM"

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc default-libmysqlclient-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制依赖文件（利用 Docker 缓存层）
COPY requirements.txt requirements-prod.txt ./

RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-prod.txt && \
    rm -rf /root/.cache/pip

# 复制项目代码
COPY . .

# 创建非 root 用户运行应用
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# 数据目录（用于持久化挂载）
RUN mkdir -p /app/logs /app/data

EXPOSE 5001

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/healthz')" || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]

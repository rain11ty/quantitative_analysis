FROM python:3.11-slim AS builder

LABEL maintainer="stock-analysis" \
     description="Stock Quantitative Analysis System with LLM (builder stage)"

# 先升级 pip
RUN pip install --no-cache-dir --upgrade pip

# 安装系统依赖（包含 ML 包编译所需的库）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ default-libmysqlclient-dev build-essential \
    cmake libopenblas-dev liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制依赖文件
COPY requirements.txt requirements-prod.txt ./

# 安装所有依赖
RUN pip install --no-cache-dir --upgrade -r requirements.txt
RUN pip install --no-cache-dir -r requirements-prod.txt || echo "部分生产依赖安装失败"
RUN pip install --no-cache-dir gunicorn>=21.0.0 redis>=5.0.0 flask-session

# 清理缓存
RUN rm -rf /root/.cache/pip

# ========== 最终镜像（不含编译工具，体积更小） ==========
FROM python:3.11-slim

LABEL maintainer="stock-analysis" \
     description="Stock Quantitative Analysis System with LLM"

# 只安装运行时需要的库
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 从 builder 阶段复制已安装的 Python 包
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码和配置文件
COPY . .

# 创建非 root 用户运行应用
RUN useradd --create-home --shell=/bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# 数据目录（用于持久化挂载）
RUN mkdir -p /app/logs /app/data

EXPOSE 5001

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/healthz')" || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]

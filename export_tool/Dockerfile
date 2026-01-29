FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.11-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    NODE_VERSION=20.x

# 安装系统依赖和 Node.js
# 注意：setup_${NODE_VERSION} 不能有空格！
# 安装系统依赖和 Node.js
# 注意：setup_${NODE_VERSION} 不能有空格！
# 替换为国内源 (Aliyun) 以解决连接问题
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates curl fonts-liberation libasound2 \
    libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcups2 libdbus-1-3 \
    libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 libwayland-client0 \
    libxcomposite1 libxdamage1 libxfixes3 libxkbcommon0 libxrandr2 xdg-utils \
    poppler-utils \
    fonts-noto-cjk fonts-wqy-microhei \
    && curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION} | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 配置 npm 使用华为云镜像（移除了无效的 disturl）
RUN npm config set registry https://repo.huaweicloud.com/repository/npm/

WORKDIR /app

# 复制 Python 依赖并安装
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple  

# 安装 Playwright 浏览器
RUN playwright install chromium

# ==================== 代码复制 ====================
WORKDIR /app

# 复制应用代码
COPY app ./app

# COPY static ./static


EXPOSE 8017

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8017/api/export_tool/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8017"]
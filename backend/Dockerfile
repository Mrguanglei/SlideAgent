FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# 更快的 apt 源（按需替换）
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list; \
        sed -i 's|http://security.debian.org|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list; \
    fi; \
    if ls /etc/apt/sources.list.d/*.sources >/dev/null 2>&1; then \
        sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/*.sources; \
        sed -i 's|http://security.debian.org|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/*.sources; \
    fi; \
    if ls /etc/apt/sources.list.d/*.list >/dev/null 2>&1; then \
        sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/*.list; \
        sed -i 's|http://security.debian.org|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/*.list; \
    fi

# 系统依赖（带缓存）
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl wget ca-certificates gnupg lsb-release \
    python3-dev libxml2-dev libxslt1-dev zlib1g-dev libffi-dev libssl-dev \
    libreoffice libreoffice-impress \
    chromium \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    poppler-utils \
    libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev shared-mime-info \
    fonts-liberation fonts-noto-cjk fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# 安装 Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# pip/uv（带缓存）
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel \
    && pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY requirements.txt ./
COPY pptagent/pyproject.toml pptagent/README.md ./pptagent/
COPY pptagent/pptagent/__init__.py ./pptagent/pptagent/
COPY deeppresenter/pyproject.toml ./deeppresenter/
COPY deeppresenter/deeppresenter/__init__.py ./deeppresenter/deeppresenter/

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

RUN --mount=type=cache,target=/root/.cache/pip \
    cd pptagent && pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

RUN --mount=type=cache,target=/root/.cache/pip \
    cd deeppresenter && pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install python-pptx -i https://pypi.tuna.tsinghua.edu.cn/simple

# 安装 Playwright 浏览器
RUN playwright install chromium && \
    playwright install-deps chromium

COPY . .

# 安装 html2pptx 的 npm 依赖
RUN cd html2pptx && npm install

ENV HF_HOME=/root/.cache/huggingface \
    HUGGINGFACE_HUB_CACHE=/root/.cache/huggingface/hub \
    CHROME_BIN=/usr/bin/chromium \
    CHROMIUM_PATH=/usr/bin/chromium

RUN mkdir -p /tmp/ppt_workspace
EXPOSE 8000
CMD ["python", "api_server.py"]

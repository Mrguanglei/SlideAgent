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
# 移除了导出相关的依赖，这些已迁移到 export_tool 服务：
# - chromium (PDF/PNG 导出)
# - libreoffice (不再需要)
# - libcairo2, libpango (WeasyPrint 依赖)
# - poppler-utils (PDF 处理)
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl wget ca-certificates gnupg lsb-release \
    python3-dev libxml2-dev libxslt1-dev zlib1g-dev libffi-dev libssl-dev \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    libreoffice poppler-utils \
    fonts-noto-cjk fonts-noto-color-emoji fonts-wqy-zenhei fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/*

# pip/uv（带缓存）
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel \
    && pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY requirements.txt ./
COPY deeppresenter/pyproject.toml ./deeppresenter/
COPY deeppresenter/__init__.py ./deeppresenter/

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

RUN --mount=type=cache,target=/root/.cache/pip \
    cd deeppresenter && pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .


ENV HF_HOME=/root/.cache/huggingface \
    HUGGINGFACE_HUB_CACHE=/root/.cache/huggingface/hub

RUN mkdir -p /tmp/ppt_workspace
EXPOSE 8000
CMD ["python", "api_server.py"]

# Partly copied from wonderwhy-er/DesktopCommanderMCP
FROM node:lts-bullseye-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV MCP_CLIENT_DOCKER=true

# Create app directory
WORKDIR /usr/src/app

# Install ca-certificates first to avoid GPG signature issues, then other packages
RUN apt-get update --allow-insecure-repositories && \
    apt-get install -y --fix-missing  --no-install-recommends --allow-unauthenticated ca-certificates && \
    update-ca-certificates && \
    apt-get install -y --no-install-recommends git bash

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Clone the repository at specific commit
RUN git clone https://github.com/wonderwhy-er/DesktopCommanderMCP.git . && \
    git checkout 252a00d624c2adc5707fa743c57a1b68bc223689 && \
    rm -rf .git

# Install dependencies without triggering any unwanted scripts
RUN npm install --ignore-scripts

# System packages installation (second batch)
RUN apt-get install -y --no-install-recommends curl wget unzip ripgrep vim

# Set environment variables
ENV PATH="/opt/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    VIRTUAL_ENV="/opt/.venv"

# Create Python virtual environment and install packages
RUN uv venv --python 3.13 $VIRTUAL_ENV && \
    uv pip install pip python-pptx matplotlib seaborn plotly numpy pandas opencv-python-headless pillow

# Creating System environment for mermaid-cli
# Install Chromium and dependencies
RUN apt-get install -y --no-install-recommends \
        chromium \
        fonts-liberation \
        libappindicator3-1 \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        xdg-utils \
        fonts-dejavu \
        fonts-noto \
        fonts-noto-cjk \
        fonts-noto-cjk-extra \
        fonts-noto-color-emoji \
        fonts-freefont-ttf \
        fonts-urw-base35 \
        fonts-roboto \
        fonts-wqy-zenhei \
        fonts-wqy-microhei \
        fonts-arphic-ukai \
        fonts-arphic-uming \
        fonts-ipafont \
        fonts-ipaexfont \
        fonts-comic-neue \
        imagemagick

RUN npm install -g @mermaid-js/mermaid-cli
RUN npm install -g pptxgenjs playwright sharp react react-dom react-icons
RUN npx playwright install chromium

# Copying config and tailored server files (moved to end, removed CACHEBUST)
COPY config.json /root/.claude-server-commander/config.json
COPY server.ts src/server.ts
COPY improved-process-tools.ts src/tools/improved-process-tools.ts

# Rebuild the package
RUN npm run build

CMD ["node",  "/usr/src/app/dist/index.js", "--no-onboarding"]

# 构建阶段
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/node:20-alpine AS builder

WORKDIR /app

# 可用构建参数覆盖镜像内 npm/pnpm 的 registry
ARG NPM_REGISTRY=https://registry.npmmirror.com

# 【优化】先复制依赖文件，这样代码改动不会让依赖层缓存失效
COPY package.json pnpm-lock.yaml ./
COPY patches ./patches

# 安装依赖（这层会被缓存）
RUN npm config set registry $NPM_REGISTRY \
 && npm config set fetch-retry-maxtimeout 600000 \
 && npm install -g pnpm \
 && pnpm config set registry $NPM_REGISTRY \
 && pnpm install --no-frozen-lockfile

# 【优化】最后才复制代码并构建
COPY . .
RUN pnpm run build

# 运行阶段
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/node:20-alpine

WORKDIR /app

# 可用构建参数覆盖镜像内 npm/pnpm 的 registry
ARG NPM_REGISTRY=https://registry.npmmirror.com

# 安装 pnpm
RUN npm config set registry $NPM_REGISTRY \
 && npm config set fetch-retry-maxtimeout 600000 \
 && npm install -g pnpm

# 【优化】先复制依赖文件
COPY package.json pnpm-lock.yaml ./
COPY patches ./patches

# 安装所有依赖（这层会被缓存）
RUN pnpm config set registry $NPM_REGISTRY \
 && pnpm install --no-frozen-lockfile

# 从构建阶段复制构建产物
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/dist/public ./dist/public

# 暴露端口
EXPOSE 3000

# 启动应用
ENV NODE_ENV=production
CMD ["node", "dist/index.js"]

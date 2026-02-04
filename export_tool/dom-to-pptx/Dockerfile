# Build dom-to-pptx and serve demo + dist via nginx
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/node:20-alpine AS build
WORKDIR /app

# Install deps (use registry mirror if needed)
ARG NPM_REGISTRY=https://registry.npmmirror.com
COPY package.json pnpm-lock.yaml ./
RUN npm config set registry ${NPM_REGISTRY} \
  && npm i -g pnpm@10.28.0 \
  && pnpm config set registry ${NPM_REGISTRY} \
  && pnpm install --include=dev

# Build
COPY . .
RUN pnpm build

FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/nginx:alpine
COPY --from=build /app/demo /usr/share/nginx/html/demo
COPY --from=build /app/dist /usr/share/nginx/html/dist

EXPOSE 80

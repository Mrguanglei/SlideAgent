import "dotenv/config";
import express from "express";
import AdmZip from "adm-zip";
import fs from "fs/promises";
import path from "path";
import { createHash } from "crypto";
import { createServer } from "http";
import net from "net";
import { createExpressMiddleware } from "@trpc/server/adapters/express";
import { registerOAuthRoutes } from "./oauth";
import { appRouter } from "../routers";
import { createContext } from "./context";
import { serveStatic, setupVite } from "./vite";

// Python 后端地址
const BACKEND_URL = process.env.BACKEND_URL || "http://backend:8000";
const FONT_CACHE_DIR = process.env.FONT_CACHE_DIR || "/tmp/pptagent_font_cache";
const FONT_ALLOWED_HOSTS = new Set([
  "fonts.googleapis.com",
  "fonts.gstatic.com",
  "cdn.cn.font.mi.com",
]);
const FAILED_FETCH_COOLDOWN_MS = 5 * 60 * 1000; // 5 分钟失败冷却
const failedFetchUntil = new Map<string, number>();
const failedFetchLogged = new Set<string>();

function getFontCacheKey(url: string): string {
  return createHash("sha256").update(url).digest("hex");
}

function getFontCachePaths(url: string) {
  const key = getFontCacheKey(url);
  return {
    dataPath: path.join(FONT_CACHE_DIR, `${key}.bin`),
    metaPath: path.join(FONT_CACHE_DIR, `${key}.json`),
  };
}

function toFontCacheUrl(rawUrl: string): string {
  return `/api/font-cache?url=${encodeURIComponent(rawUrl)}`;
}

function isAllowedFontUrl(rawUrl: string): boolean {
  try {
    const parsed = new URL(rawUrl);
    return (parsed.protocol === "https:" || parsed.protocol === "http:") && FONT_ALLOWED_HOSTS.has(parsed.hostname);
  } catch {
    return false;
  }
}

function rewriteCssFontUrls(css: string): string {
  return css.replace(/url\((['"]?)(https?:\/\/[^'")\s]+)\1\)/gi, (full, quote, url: string) => {
    if (!isAllowedFontUrl(url)) return full;
    return `url(${quote || ""}${toFontCacheUrl(url)}${quote || ""})`;
  });
}

function getMiSansFallbackCss(): string {
  return `
/* MiSans unavailable, fallback to local/system fonts */
@font-face {
  font-family: "MiSans";
  src: local("Noto Sans SC"), local("PingFang SC"), local("Microsoft YaHei"), local("sans-serif");
  font-weight: 300 700;
  font-style: normal;
}
`;
}

function isPortAvailable(port: number): Promise<boolean> {
  return new Promise(resolve => {
    const server = net.createServer();
    server.listen(port, () => {
      server.close(() => resolve(true));
    });
    server.on("error", () => resolve(false));
  });
}

async function findAvailablePort(startPort: number = 3000): Promise<number> {
  for (let port = startPort; port < startPort + 20; port++) {
    if (await isPortAvailable(port)) {
      return port;
    }
  }
  throw new Error(`No available port found starting from ${startPort}`);
}

async function startServer() {
  const app = express();
  const server = createServer(app);
  // Configure body parser with larger size limit for file uploads
  app.use(express.json({ limit: "50mb" }));
  app.use(express.urlencoded({ limit: "50mb", extended: true }));
  // OAuth callback under /api/oauth/callback
  registerOAuthRoutes(app);
  const demoDir =
    process.env.PPT_DEMO_DIR || path.resolve(process.cwd(), "..", "PPT_demo");

  app.get("/api/font-cache", async (req, res) => {
    try {
      const rawUrl = typeof req.query.url === "string" ? req.query.url : "";
      if (!rawUrl) {
        res.status(400).json({ error: "Missing url query param" });
        return;
      }
      if (!isAllowedFontUrl(rawUrl)) {
        res.status(403).json({ error: "URL host is not allowed" });
        return;
      }

      const parsedUrl = new URL(rawUrl);
      // MiSans 域名在部分容器网络下不可解析：直接返回可缓存的降级 CSS，避免反复网络失败
      if (parsedUrl.hostname === "cdn.cn.font.mi.com") {
        const fallbackCss = getMiSansFallbackCss();
        const contentType = "text/css; charset=utf-8";
        res.setHeader("Content-Type", contentType);
        res.setHeader("Cache-Control", "public, max-age=31536000, immutable");

        await fs.mkdir(FONT_CACHE_DIR, { recursive: true });
        const { dataPath, metaPath } = getFontCachePaths(rawUrl);
        await Promise.all([
          fs.writeFile(dataPath, Buffer.from(fallbackCss, "utf-8")),
          fs.writeFile(metaPath, JSON.stringify({ contentType }), "utf-8"),
        ]);

        res.send(fallbackCss);
        return;
      }

      const now = Date.now();
      const failedUntil = failedFetchUntil.get(rawUrl);
      if (failedUntil && failedUntil > now) {
        res.status(502).json({ error: "Font upstream temporarily unavailable", retryAfterMs: failedUntil - now });
        return;
      }

      await fs.mkdir(FONT_CACHE_DIR, { recursive: true });
      const { dataPath, metaPath } = getFontCachePaths(rawUrl);

      try {
        const [cachedBody, cachedMetaText] = await Promise.all([
          fs.readFile(dataPath),
          fs.readFile(metaPath, "utf-8"),
        ]);
        const cachedMeta = JSON.parse(cachedMetaText) as { contentType?: string };
        if (cachedMeta.contentType) {
          res.setHeader("Content-Type", cachedMeta.contentType);
        }
        res.setHeader("Cache-Control", "public, max-age=31536000, immutable");
        res.send(cachedBody);
        return;
      } catch {
        // cache miss, continue fetching
      }

      const upstream = await fetch(rawUrl, {
        headers: {
          "User-Agent": "Mozilla/5.0 PPTAgent Font Cache",
          "Accept": "*/*",
        },
      });

      if (!upstream.ok) {
        res.status(upstream.status).send(await upstream.text());
        return;
      }

      let contentType = upstream.headers.get("content-type") || "application/octet-stream";
      let bodyBuffer = Buffer.from(await upstream.arrayBuffer());

      if (contentType.includes("text/css")) {
        const rewrittenCss = rewriteCssFontUrls(bodyBuffer.toString("utf-8"));
        bodyBuffer = Buffer.from(rewrittenCss, "utf-8");
        contentType = "text/css; charset=utf-8";
      }

      await Promise.all([
        fs.writeFile(dataPath, bodyBuffer),
        fs.writeFile(metaPath, JSON.stringify({ contentType }), "utf-8"),
      ]);
      failedFetchUntil.delete(rawUrl);
      failedFetchLogged.delete(rawUrl);

      res.setHeader("Content-Type", contentType);
      res.setHeader("Cache-Control", "public, max-age=31536000, immutable");
      res.send(bodyBuffer);
    } catch (error) {
      const rawUrl = typeof req.query.url === "string" ? req.query.url : "";
      if (rawUrl) {
        failedFetchUntil.set(rawUrl, Date.now() + FAILED_FETCH_COOLDOWN_MS);
        if (!failedFetchLogged.has(rawUrl)) {
          console.error("[FontCache] failed:", error);
          failedFetchLogged.add(rawUrl);
        }
      } else {
        console.error("[FontCache] failed:", error);
      }
      res.status(500).json({ error: "Failed to load font resource" });
    }
  });

  const proxySSE = async (req: express.Request, res: express.Response, backendPath: string) => {
    try {
      const response = await fetch(`${BACKEND_URL}${backendPath}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(req.body),
      });

      // 设置 SSE 响应头
      res.setHeader("Content-Type", "text/event-stream");
      res.setHeader("Cache-Control", "no-cache");
      res.setHeader("Connection", "keep-alive");
      res.setHeader("X-Accel-Buffering", "no");

      // 转发 session_id / conversation_id（必须在 flushHeaders 前设置）
      const sessionId = response.headers.get("X-Session-Id");
      if (sessionId) {
        res.setHeader("X-Session-Id", sessionId);
      }
      const conversationId = response.headers.get("X-Conversation-Id");
      if (conversationId) {
        res.setHeader("X-Conversation-Id", conversationId);
      }

      res.flushHeaders?.();

      // 流式转发响应
      if (response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          res.write(chunk);
        }
      }
      res.end();
    } catch (error) {
      console.error("[Proxy] SSE error:", error);
      if (!res.headersSent) {
        res.status(500).json({ error: "Failed to connect to backend" });
      } else {
        res.end();
      }
    }
  };

  // 代理到 Python 后端的 /api/chat 接口 (SSE)
  app.post("/api/ppt/chat", async (req, res) => {
    console.log("[Proxy] Forwarding chat request to Python backend");
    console.log("[Proxy] Request body:", JSON.stringify(req.body, null, 2));
    await proxySSE(req, res, "/api/chat");
  });

  // Demo PPT list (local only)
  app.get("/api/demo/list", async (_req, res) => {
    try {
      const entries = await fs.readdir(demoDir, { withFileTypes: true });
      const files = await Promise.all(
        entries
          .filter(entry => entry.isFile() && entry.name.toLowerCase().endsWith(".pptx"))
          .map(async entry => {
            const filePath = path.join(demoDir, entry.name);
            const stat = await fs.stat(filePath);
            return {
              name: entry.name,
              size: stat.size,
              modifiedAt: stat.mtime.toISOString(),
              url: `/demo-files/${encodeURIComponent(entry.name)}`,
              thumbnailUrl: `/api/demo/thumbnail/${encodeURIComponent(entry.name)}`,
            };
          })
      );
      res.json({ items: files });
    } catch (error) {
      console.warn("[Demo] Failed to read PPT_demo directory:", error);
      res.json({ items: [] });
    }
  });

  // PPTX thumbnail (docProps/thumbnail.*)
  app.get("/api/demo/thumbnail/:name", async (req, res) => {
    try {
      const filename = req.params.name;
      const resolved = path.resolve(demoDir, filename);
      const demoRoot = path.resolve(demoDir);

      if (!resolved.startsWith(demoRoot + path.sep)) {
        res.status(400).json({ error: "Invalid file path" });
        return;
      }

      const zip = new AdmZip(resolved);
      const entry =
        zip.getEntry("docProps/thumbnail.jpeg") ||
        zip.getEntry("docProps/thumbnail.jpg") ||
        zip.getEntry("docProps/thumbnail.png");

      if (!entry) {
        res.status(404).json({ error: "Thumbnail not found" });
        return;
      }

      const buffer = entry.getData();
      const isPng = entry.entryName.toLowerCase().endsWith(".png");
      res.setHeader("Content-Type", isPng ? "image/png" : "image/jpeg");
      res.setHeader("Cache-Control", "public, max-age=3600");
      res.send(buffer);
    } catch (error) {
      console.warn("[Demo] Failed to load thumbnail:", error);
      res.status(500).json({ error: "Failed to load thumbnail" });
    }
  });

  // Serve local demo files
  app.use("/demo-files", express.static(demoDir));

  // 代理到 Python 后端的 /api/chat 接口 (SSE) - 兼容前端直连 /api/chat
  app.post("/api/chat", async (req, res) => {
    console.log("[Proxy] Forwarding chat request to Python backend");
    console.log("[Proxy] Request body:", JSON.stringify(req.body, null, 2));
    await proxySSE(req, res, "/api/chat");
  });

  // 代理到 Python 后端的 /api/confirm 接口 (SSE)
  app.post("/api/ppt/confirm", async (req, res) => {
    console.log("[Proxy] Forwarding confirm request to Python backend");
    await proxySSE(req, res, "/api/confirm");
  });

  // 代理到 Python 后端的 /api/confirm 接口 (SSE) - 兼容直连
  app.post("/api/confirm", async (req, res) => {
    console.log("[Proxy] Forwarding confirm request to Python backend");
    await proxySSE(req, res, "/api/confirm");
  });

  // 代理到 Python 后端的 /api/health 接口
  app.get("/api/ppt/health", async (req, res) => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/health`);
      const data = await response.json();
      res.json(data);
    } catch (error) {
      console.error("[Proxy] Health check error:", error);
      res.status(500).json({ error: "Backend not available" });
    }
  });

  // tRPC API
  app.use(
    "/api/trpc",
    createExpressMiddleware({
      router: appRouter,
      createContext,
    })
  );

  // 通用代理：将所有其他 /api/* 请求转发到 Python 后端
  app.use("/api", async (req, res) => {
    try {
      const url = `${BACKEND_URL}/api${req.url}`;
      console.log(`[Proxy] Forwarding ${req.method} /api${req.url} to ${url}`);

      const reqContentType = req.headers["content-type"];
      let body: any;
      let headers: HeadersInit = {};

      if (reqContentType && reqContentType.includes("multipart/form-data")) {
        // 对于上传文件，直接透传流和 Content-Type
        body = req;
        headers = {
          // 注意：不要手动设置 multipart/form-data 的 Content-Type，
          // 因为 fetch/browser/client 会设置 boundary。
          // 但是这里的 request 是来自 express 的 incoming request
          // 如果我们直接 pipe req 到 fetch body， fetch 应该能读取流。
          // 我们需要把 client 发来的 Content-Type (含 boundary) 转发给 backend
          "Content-Type": reqContentType,
        };
      } else {
        // 默认处理 JSON
        headers = {
          "Content-Type": reqContentType || "application/json",
        };
        body = req.method !== "GET" && req.method !== "HEAD" ? JSON.stringify(req.body) : undefined;
      }

      const response = await fetch(url, {
        method: req.method,
        headers: headers,
        body: body,
        // @ts-ignore - node-fetch supports stream as body
        duplex: 'half'
      });

      // 转发响应头
      response.headers.forEach((value, key) => {
        res.setHeader(key, value);
      });

      // 检查响应类型，对于二进制文件使用 arrayBuffer
      const contentType = response.headers.get("content-type") || "";
      const isBinaryResponse =
        contentType.includes("application/octet-stream") ||
        contentType.includes("application/pdf") ||
        contentType.includes("application/zip") ||
        contentType.includes("application/vnd.openxmlformats") ||  // PPTX, DOCX, XLSX
        contentType.includes("image/");

      if (isBinaryResponse) {
        // 二进制文件：使用 arrayBuffer 保持原始字节
        const buffer = await response.arrayBuffer();
        res.status(response.status).send(Buffer.from(buffer));
      } else {
        // 文本响应：使用 text
        const data = await response.text();
        res.status(response.status).send(data);
      }
    } catch (error) {
      console.error("[Proxy] API error:", error);
      res.status(500).json({ error: "Failed to connect to backend" });
    }
  });
  // development mode uses Vite, production mode uses static files
  if (process.env.NODE_ENV === "development") {
    await setupVite(app, server);
  } else {
    serveStatic(app);
  }

  const preferredPort = parseInt(process.env.PORT || "3000");
  const port = await findAvailablePort(preferredPort);

  if (port !== preferredPort) {
    console.log(`Port ${preferredPort} is busy, using port ${port} instead`);
  }

  server.listen(port, () => {
    console.log(`Server running on http://localhost:${port}/`);
  });
}

startServer().catch(console.error);

import "dotenv/config";
import express from "express";
import AdmZip from "adm-zip";
import fs from "fs/promises";
import path from "path";
import { createServer } from "http";
import net from "net";
import { createExpressMiddleware } from "@trpc/server/adapters/express";
import { registerOAuthRoutes } from "./oauth";
import { appRouter } from "../routers";
import { createContext } from "./context";
import { serveStatic, setupVite } from "./vite";

// Python 后端地址
const BACKEND_URL = process.env.BACKEND_URL || "http://backend:8000";

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

  const proxySSE = async (req: express.Request, res: express.Response, backendPath: string) => {
    const abortController = new AbortController();
    const onClientDisconnect = () => {
      if (!abortController.signal.aborted) {
        abortController.abort();
      }
    };

    req.once("aborted", onClientDisconnect);
    res.once("close", onClientDisconnect);

    try {
      const response = await fetch(`${BACKEND_URL}${backendPath}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(req.body),
        signal: abortController.signal,
      });

      const sessionId = response.headers.get("X-Session-Id");
      if (sessionId) {
        res.setHeader("X-Session-Id", sessionId);
      }
      const conversationId = response.headers.get("X-Conversation-Id");
      if (conversationId) {
        res.setHeader("X-Conversation-Id", conversationId);
      }
      const conversationUuid = response.headers.get("X-Conversation-UUID");
      if (conversationUuid) {
        res.setHeader("X-Conversation-UUID", conversationUuid);
      }

      // 非流式错误必须透传状态码，避免把后端 4xx/5xx 伪装成 200 SSE
      if (!response.ok) {
        const contentType = response.headers.get("content-type") || "application/json";
        const errorText = await response.text();
        res.status(response.status);
        res.setHeader("Content-Type", contentType);
        res.send(errorText);
        return;
      }

      // 设置 SSE 响应头
      res.setHeader("Content-Type", "text/event-stream");
      res.setHeader("Cache-Control", "no-cache");
      res.setHeader("Connection", "keep-alive");
      res.setHeader("X-Accel-Buffering", "no");

      res.flushHeaders?.();

      // 流式转发响应
      if (response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          if (abortController.signal.aborted || res.writableEnded) {
            try {
              await reader.cancel();
            } catch (_err) {
              // Ignore cancellation errors from already-closed streams.
            }
            break;
          }
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          res.write(chunk);
        }
      }
      res.end();
    } catch (error) {
      if (abortController.signal.aborted) {
        return;
      }
      console.error("[Proxy] SSE error:", error);
      if (!res.headersSent) {
        res.status(500).json({ error: "Failed to connect to backend" });
      } else {
        res.end();
      }
    } finally {
      req.removeListener("aborted", onClientDisconnect);
      res.removeListener("close", onClientDisconnect);
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

import "dotenv/config";
import express from "express";
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
  
  // 代理到 Python 后端的 /api/chat 接口 (SSE)
  app.post("/api/ppt/chat", async (req, res) => {
    try {
      console.log("[Proxy] Forwarding chat request to Python backend");
      console.log("[Proxy] Request body:", JSON.stringify(req.body, null, 2));
      const response = await fetch(`${BACKEND_URL}/api/chat`, {
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

      // 转发 session_id
      const sessionId = response.headers.get("X-Session-Id");
      if (sessionId) {
        res.setHeader("X-Session-Id", sessionId);
      }

      // 流式转发响应
      if (response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });

          // 记录接收到的数据块
          const lines = chunk.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.type === 'tool_call') {
                  console.log("[Proxy] Received tool_call:", JSON.stringify(data, null, 2));
                }
              } catch (e) {
                // 忽略解析错误
              }
            }
          }

          res.write(chunk);
        }
      }
      res.end();
    } catch (error) {
      console.error("[Proxy] Chat error:", error);
      res.status(500).json({ error: "Failed to connect to backend" });
    }
  });
  
  // 代理到 Python 后端的 /api/confirm 接口 (SSE)
  app.post("/api/ppt/confirm", async (req, res) => {
    try {
      console.log("[Proxy] Forwarding confirm request to Python backend");
      const response = await fetch(`${BACKEND_URL}/api/confirm`, {
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
      console.error("[Proxy] Confirm error:", error);
      res.status(500).json({ error: "Failed to connect to backend" });
    }
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

      const response = await fetch(url, {
        method: req.method,
        headers: {
          "Content-Type": req.headers["content-type"] || "application/json",
        },
        body: req.method !== "GET" && req.method !== "HEAD" ? JSON.stringify(req.body) : undefined,
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

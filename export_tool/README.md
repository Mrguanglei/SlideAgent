# HTML to PPTX API Service

基于 FastAPI 和 dom-to-pptx 的 HTML 转 PPTX API 服务。

## 功能特点

- ✅ 将 HTML 内容转换为可编辑的 PPTX 文件
- ✅ 支持复杂样式(渐变、阴影、圆角等)
- ✅ 自动字体嵌入
- ✅ 无头浏览器渲染,保证高保真度
- ✅ 异步处理,高性能
- ✅ 浏览器池管理,支持并发请求

## 技术栈

- **后端框架**: FastAPI 0.109+
- **无头浏览器**: Playwright (Chromium)
- **HTML 转 PPTX**: dom-to-pptx 1.1.4
- **Python**: 3.9+

## 快速开始

### 1. 安装依赖

```bash
cd export_tool

# 创建虚拟环境(可选但推荐)
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或 Windows: venv\Scripts\activate

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 根据需要编辑 .env 文件
```

### 3. 启动服务

```bash
# 开发模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

服务将在 `http://localhost:8000` 启动

- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/health

## API 使用

### 端点: `POST /api/html-to-pptx`

将 HTML 内容转换为 PPTX 文件。

**请求体 (JSON)**:

```json
{
  "html": "<div style='width:1920px;height:1080px;background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);'><h1 style='color:white;padding:100px;'>Hello World</h1></div>",
  "css": ".custom-class { font-family: 'Roboto', sans-serif; }",
  "options": {
    "fileName": "presentation.pptx",
    "autoEmbedFonts": true,
    "fonts": [
      {
        "name": "Roboto",
        "url": "https://fonts.gstatic.com/s/roboto/v30/KFOmCnqEu92Fr1Mu4mxK.woff2"
      }
    ]
  }
}
```

**响应**:
- 成功: 返回 PPTX 文件(二进制流)
- 失败: 返回 JSON 错误信息

### cURL 示例

```bash
curl -X POST http://localhost:8000/api/html-to-pptx \
  -H "Content-Type: application/json" \
  -d '{
    "html": "<div style=\"width:1920px;height:1080px;background:#667eea;\"><h1 style=\"color:white;padding:100px;\">测试幻灯片</h1></div>",
    "options": {
      "fileName": "test.pptx"
    }
  }' \
  --output test.pptx
```

### Python 客户端示例

```python
import requests

url = "http://localhost:8000/api/html-to-pptx"
payload = {
    "html": """
        <div style='width:1920px;height:1080px;background:#667eea;'>
            <h1 style='color:white;padding:100px;'>测试幻灯片</h1>
        </div>
    """,
    "options": {
        "fileName": "output.pptx",
        "autoEmbedFonts": True
    }
}

response = requests.post(url, json=payload)

if response.status_code == 200:
    with open("output.pptx", "wb") as f:
        f.write(response.content)
    print("PPTX 文件生成成功!")
else:
    print(f"错误: {response.json()}")
```

### JavaScript 客户端示例

```javascript
async function convertToPptx(html, options = {}) {
    const response = await fetch('http://localhost:8000/api/html-to-pptx', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            html: html,
            options: options
        })
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Conversion failed');
    }
    
    const blob = await response.blob();
    
    // 下载文件
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = options.fileName || 'output.pptx';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// 使用示例
const html = `
    <div style="width:1920px;height:1080px;background:#667eea;">
        <h1 style="color:white;padding:100px;">测试幻灯片</h1>
    </div>
`;

await convertToPptx(html, { fileName: 'test.pptx' });
```

## 项目结构

```
export_tool/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口
│   ├── api/
│   │   ├── __init__.py
│   │   └── endpoints.py     # API 路由
│   ├── services/
│   │   ├── __init__.py
│   │   └── pptx_service.py  # PPTX 生成服务
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py       # 数据模型
│   └── utils/
│       ├── __init__.py
│       └── browser.py       # 浏览器管理
├── dom-to-pptx/            # HTML 转 PPTX 核心库
│   ├── src/
│   ├── dist/
│   └── package.json
├── requirements.txt         # Python 依赖
├── .env.example            # 环境变量模板
├── .dockerignore           # Docker 忽略文件
├── Dockerfile              # Docker 构建文件
└── README.md               # 本文件
```

## 配置说明

环境变量 (`.env` 文件):

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `HOST` | 0.0.0.0 | 服务监听地址 |
| `PORT` | 8000 | 服务端口 |
| `DEBUG` | true | 调试模式 |
| `MAX_CONCURRENT_CONVERSIONS` | 5 | 最大并发转换数 |
| `CONVERSION_TIMEOUT` | 30 | 转换超时时间(秒) |
| `BROWSER_POOL_SIZE` | 3 | 浏览器池大小 |
| `ALLOWED_ORIGINS` | * | CORS 允许的源 |
| `DOM_TO_PPTX_BUNDLE_PATH` | 空 | 可选：直接指定 dom-to-pptx.bundle.js 的本地路径（优先级高于默认路径） |
| `DOM_TO_PPTX_BUNDLE_URL` | 空 | 可选：直接指定 dom-to-pptx.bundle.js 的完整 URL（用于远程加载） |

说明：`export_tool` 会直接加载 `export_tool/dom-to-pptx/dist/dom-to-pptx.bundle.js`。若本地未构建，请在 `export_tool/dom-to-pptx` 下执行 `npm install && npm run build`，或用上述环境变量覆盖路径/URL。

## Docker 部署

### 使用 Docker Compose (推荐)

在项目根目录（To-ppt）运行：

```bash
# 构建并启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f export_tool

# 停止服务
docker-compose down
```

服务将在 `http://localhost:8002` 启动。

### 手动 Docker 构建

```bash
cd export_tool

# 构建镜像
docker build -t export-tool-api .

# 运行容器
docker run -d -p 8002:8000 --name export_tool export-tool-api
```

## 性能优化

1. **浏览器池**: 使用浏览器池避免频繁启动浏览器
2. **并发控制**: 通过信号量限制并发请求数
3. **超时保护**: 设置合理的超时时间防止资源泄漏
4. **异步处理**: 利用 FastAPI 的异步特性提高吞吐量

## 故障排查

### 问题: Playwright 浏览器安装失败

```bash
# 手动安装浏览器
playwright install chromium

# 如果在 Docker 中,还需要安装系统依赖
playwright install-deps
```

### 问题: PPTX 生成超时

- 增加 `CONVERSION_TIMEOUT` 环境变量
- 检查 HTML 内容是否过于复杂
- 减少 `BROWSER_POOL_SIZE` 降低资源竞争

### 问题: 字体嵌入失败

- 确保字体 URL 可访问
- 检查字体 URL 是否有 CORS 限制
- 使用 `fonts` 选项手动指定字体

## License

MIT

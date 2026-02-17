// PPTAgent 前端服务 - 调用 Python 后端 API

// Python 后端 API 地址
const BACKEND_URL = process.env.BACKEND_URL || "http://backend:8000";

// 存储 session_id
let currentSessionId: string | null = null;

// 工具显示名称映射
const TOOL_DISPLAY_NAMES: Record<string, string> = {
  supplement_info: "补充信息",
  task_plan: "任务执行规划",
  web_search: "搜索网页",
  image_search: "搜索图片",
  create_slide: "新增页面",
};

// PPTAgent 可用工具定义（用于前端测试和工具协议约束）
export const pptTools = [
  {
    type: "function",
    function: {
      name: "supplement_info",
      description: "收集并确认生成 PPT 所需的补充信息",
      parameters: {
        type: "object",
        properties: {
          topic: { type: "string" },
          audienceQuestion: { type: "string" },
          audienceOptions: { type: "array", items: { type: "string" } },
          modulesQuestion: { type: "string" },
          modulesOptions: { type: "array", items: { type: "string" } },
          styleQuestion: { type: "string" },
          styleOptions: { type: "array", items: { type: "string" } },
          emphasisQuestion: { type: "string" },
          emphasisPlaceholder: { type: "string" },
        },
        required: ["topic", "audienceOptions", "modulesOptions", "styleOptions"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "task_plan",
      description: "输出任务规划和执行步骤",
      parameters: {
        type: "object",
        properties: {
          coreRequirement: { type: "string" },
          details: { type: "array", items: { type: "string" } },
          steps: { type: "array", items: { type: "object" } },
        },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "web_search",
      description: "执行网页搜索并返回结果",
      parameters: {
        type: "object",
        properties: {
          query: { type: "string" },
        },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "image_search",
      description: "执行图片搜索并返回结果",
      parameters: {
        type: "object",
        properties: {
          query: { type: "string" },
        },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "create_slide",
      description: "生成单页幻灯片 HTML",
      parameters: {
        type: "object",
        properties: {
          pageNumber: { type: "number" },
          title: { type: "string" },
          content: { type: "string" },
          htmlCode: { type: "string" },
        },
        required: ["pageNumber", "title", "content"],
      },
    },
  },
];

// 获取工具显示名称
function getToolDisplayName(toolName: string): string {
  return TOOL_DISPLAY_NAMES[toolName] || toolName;
}

// 获取工具状态
function getToolStatus(toolName: string): string {
  if (toolName === "supplement_info") {
    return "pending"; // 需要用户确认
  }
  return "auto_execute"; // 自动执行
}

// 解析流式响应
async function parseStreamResponse(response: Response): Promise<{
  content: string;
  sessionId?: string;
  toolCall?: {
    id: string;
    type: string;
    name: string;
    status: string;
    data: Record<string, unknown>;
  };
}> {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("No response body");
  }

  const decoder = new TextDecoder();
  let content = "";
  let sessionId: string | undefined;
  let toolCall: {
    id: string;
    type: string;
    name: string;
    status: string;
    data: Record<string, unknown>;
  } | undefined;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value, { stream: true });
    const lines = text.split("\n").filter(line => line.trim());

    for (const line of lines) {
      try {
        const msg = JSON.parse(line);

        // 提取 session_id
        if (msg.session_id) {
          sessionId = msg.session_id;
          currentSessionId = sessionId ?? null;
        }

        // 累积内容
        if (msg.content) {
          content = msg.content; // 使用最后一条消息的 content
        }

        // 提取工具调用
        if (msg.tool_calls && msg.tool_calls.length > 0) {
          const tc = msg.tool_calls[0];
          const functionName = tc.function?.name || tc.type || "unknown";
          let args: Record<string, unknown> = {};

          if (tc.function?.arguments) {
            try {
              args = typeof tc.function.arguments === "string"
                ? JSON.parse(tc.function.arguments)
                : tc.function.arguments;
            } catch {
              args = { raw: tc.function.arguments };
            }
          }

          toolCall = {
            id: tc.id || `tool-${Date.now()}`,
            type: functionName,
            name: tc.displayName || getToolDisplayName(functionName),
            status: tc.status || getToolStatus(functionName),
            data: args,
          };
        }
      } catch (e) {
        console.error("[PPTAgent] Failed to parse stream line:", line, e);
      }
    }
  }

  return { content, sessionId, toolCall };
}

// 调用 Python 后端 Chat API（流式）
async function callBackendChatAPI(data: Record<string, unknown>): Promise<{
  content: string;
  sessionId?: string;
  toolCall?: {
    id: string;
    type: string;
    name: string;
    status: string;
    data: Record<string, unknown>;
  };
}> {
  const url = `${BACKEND_URL}/api/chat`;
  console.log(`[PPTAgent] Calling backend API: ${url}`);

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Backend API error: ${response.status} - ${errorText}`);
    }

    // 获取 session_id 从响应头
    const sessionIdFromHeader = response.headers.get("X-Session-Id");
    if (sessionIdFromHeader) {
      currentSessionId = sessionIdFromHeader;
    }

    return await parseStreamResponse(response);
  } catch (error) {
    console.error(`[PPTAgent] Backend API error:`, error);
    throw error;
  }
}

// 调用后端 Confirm API（流式）
async function callBackendConfirmAPI(sessionId: string, supplementData: Record<string, unknown>): Promise<{
  content: string;
  toolCall?: {
    id: string;
    type: string;
    name: string;
    status: string;
    data: Record<string, unknown>;
  };
}> {
  const url = `${BACKEND_URL}/api/confirm`;
  console.log(`[PPTAgent] Calling backend confirm API: ${url}`);

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        session_id: sessionId,
        supplement_data: supplementData,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Backend API error: ${response.status} - ${errorText}`);
    }

    return await parseStreamResponse(response);
  } catch (error) {
    console.error(`[PPTAgent] Backend confirm API error:`, error);
    throw error;
  }
}

// 理解用户意图（第一次调用）
export async function understandIntent(userMessage: string): Promise<{
  content: string;
  sessionId?: string;
  toolCall?: {
    id: string;
    type: string;
    name: string;
    status: string;
    data: Record<string, unknown>;
  };
}> {
  try {
    const result = await callBackendChatAPI({
      instruction: userMessage,
    });

    return {
      content: result.content,
      sessionId: result.sessionId,
      toolCall: result.toolCall,
    };
  } catch (error) {
    console.error("[PPTAgent] understandIntent error:", error);

    // 如果后端不可用，返回模拟的补充信息工具调用
    return {
      content: `好的，我将为您制作一份关于"${userMessage}"的PPT。首先，我需要了解更多关于这份PPT的详细信息，以便更好地为您服务。`,
      toolCall: {
        id: `tool-${Date.now()}`,
        type: "supplement_info",
        name: "补充信息",
        status: "pending",
        data: {
          topic: userMessage,
          audienceQuestion: "这份PPT的目标受众是？",
          audienceOptions: ["企业内部汇报", "行业分析师", "消费者市场研究", "媒体发布"],
          modulesQuestion: "PPT中需要包含哪些内容模块？",
          modulesOptions: ["市场概况与趋势", "品牌市场份额分析", "区域市场对比", "消费者偏好分析", "未来预测"],
          styleQuestion: "你期望的PPT设计风格是？",
          styleOptions: ["专业商务", "数据可视化导向", "简洁现代", "科技感"],
          emphasisQuestion: "是否有特定的品牌或数据需要重点突出？",
          emphasisPlaceholder: "例如华为、小米、苹果等",
        },
      },
    };
  }
}

// 继续对话（确认补充信息后调用）
export async function continueConversation(
  conversationHistory: Array<{
    role: string;
    content: string;
    name?: string;
    tool_call_id?: string;
  }>,
  toolResult?: { name: string; result: string },
  sessionId?: string
): Promise<{
  content: string;
  toolCall?: {
    id: string;
    type: string;
    name: string;
    status: string;
    data: Record<string, unknown>;
  };
}> {
  try {
    // 如果有 tool_result 且是 supplement_info，使用 confirm API
    if (toolResult && toolResult.name === "supplement_info") {
      const resultData = JSON.parse(toolResult.result);
      const useSessionId = sessionId || currentSessionId;

      if (!useSessionId) {
        throw new Error("No session_id available for confirm");
      }

      console.log(`[PPTAgent] Confirming supplement info with session: ${useSessionId}`);
      return await callBackendConfirmAPI(useSessionId, resultData.data);
    }

    // 其他情况，发送带 supplement_data 的 chat 请求
    const useSessionId = sessionId || currentSessionId;

    // 从 conversationHistory 或 toolResult 中提取 supplement_data
    let supplementData: Record<string, unknown> | undefined;
    if (toolResult) {
      try {
        const parsed = JSON.parse(toolResult.result);
        if (parsed.data) {
          supplementData = parsed.data;
        }
      } catch {
        // ignore
      }
    }

    const result = await callBackendChatAPI({
      instruction: "",
      session_id: useSessionId,
      supplement_data: supplementData,
    });

    return {
      content: result.content,
      toolCall: result.toolCall,
    };
  } catch (error) {
    console.error("[PPTAgent] continueConversation error:", error);

    // 如果后端不可用，返回模拟的任务规划
    const topic = conversationHistory.find(m => m.role === "user")?.content || "PPT";

    return {
      content: `好的，我已收到您的补充信息。现在我将为您生成任务规划。`,
      toolCall: {
        id: `tool-${Date.now()}`,
        type: "task_plan",
        name: "任务执行规划",
        status: "auto_execute",
        data: {
          coreRequirement: `制作一份关于"${topic}"的PPT`,
          details: [
            "目标受众：企业内部汇报",
            "内容模块：市场概况与趋势、各品牌市场份额分析、区域销量对比",
            "设计风格：专业商务",
          ],
          steps: [
            { id: 1, text: "搜索相关市场数据和报告" },
            { id: 2, text: "整理和分析收集到的信息" },
            { id: 3, text: "设计PPT结构和布局" },
            { id: 4, text: "生成各页面内容" },
          ],
        },
      },
    };
  }
}

// 执行工具调用
export async function executeTool(
  toolName: string,
  args: Record<string, unknown>
): Promise<{ success: boolean; result: unknown }> {
  // 工具执行由后端自动处理，这里返回确认结果
  switch (toolName) {
    case "supplement_info":
      return {
        success: true,
        result: {
          confirmed: true,
          data: args,
        },
      };

    case "task_plan":
      return {
        success: true,
        result: {
          planned: true,
          data: args,
        },
      };

    case "web_search":
      return {
        success: true,
        result: {
          query: args.query,
          results: args.results || [],
          thinking: `已完成搜索「${args.query}」`,
        },
      };

    case "image_search":
      return {
        success: true,
        result: {
          query: args.query,
          images: args.images || [],
        },
      };

    case "create_slide":
      return {
        success: true,
        result: {
          pageNumber: args.pageNumber,
          title: args.title,
          content: args.content,
          htmlCode: args.htmlCode || generateSlideHtml({
            pageNumber: args.pageNumber as number,
            title: args.title as string,
            content: args.content as string,
          }),
        },
      };

    default:
      return {
        success: false,
        result: {
          error: `Unknown tool: ${toolName}`,
          data: args,
        },
      };
  }
}

interface SlideArgs {
  pageNumber: number;
  title: string;
  content: string;
  htmlCode?: string;
}

// 生成幻灯片 HTML
function generateSlideHtml(args: SlideArgs): string {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta content="width=device-width, initial-scale=1.0" name="viewport"/>
  <title>${args.title}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gradient-to-br from-slate-800 to-slate-900 min-h-screen flex items-center justify-center">
  <div class="text-center text-white p-12">
    <h1 class="text-4xl font-bold mb-4">${args.title}</h1>
    <p class="text-xl text-slate-300">${args.content}</p>
  </div>
</body>
</html>`;
}

// 获取当前 session_id
export function getCurrentSessionId(): string | null {
  return currentSessionId;
}

// 设置 session_id
export function setCurrentSessionId(sessionId: string): void {
  currentSessionId = sessionId;
}

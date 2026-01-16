/**
 * PPTAgent 主页面
 * 
 * 功能：
 * - 左侧：历史对话侧边栏
 * - 中间：聊天区域
 * - 右侧：工具面板（任务规划、搜索结果、PPT预览等）
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useLocation } from "wouter";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  FileSliders,
  Send,
  Paperclip,
  Settings,
  Loader2,
  X,
  MessageSquarePlus,
  FolderOpen,
} from "lucide-react";

// 组件导入
import ConversationSidebar from "@/components/ConversationSidebar";
import MessageItem from "@/components/MessageItem";
import RightPanel from "@/components/RightPanel";
import DownloadModal from "@/components/DownloadModal";
import ShareModal from "@/components/ShareModal";
import TaskFilesModal from "@/components/TaskFilesModal";
import LoadingDots from "@/components/LoadingDots";

// 类型导入
import type {
  Message,
  ToolCall,
  TaskPlan,
  SearchRound,
  RightPanelType,
  PPTViewMode,
  PPTProject,
  Conversation,
  Template,
  TemplateCategory,
} from "@/types";

// API 导入
import {
  getConversations,
  getConversationDetail,
  createConversation,
  deleteConversation,
  getPPTProjects,
} from "@/lib/api";

// 模板数据 - 智谱清言风格（带预览图）
const TEMPLATES: Template[] = [
  { 
    id: 1, 
    title: "AI医疗创新", 
    category: "科技", 
    color: "from-white to-gray-50", 
    subtitle: "AI-DRIVEN HEALTHCARE INNOVATION",
    preview: "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=400&h=225&fit=crop"
  },
  { 
    id: 2, 
    title: "中国医疗创新", 
    category: "商务", 
    color: "from-blue-50 to-blue-100", 
    subtitle: "中国医疗创新：未来的挑战",
    preview: "https://images.unsplash.com/photo-1551076805-e1869033e561?w=400&h=225&fit=crop"
  },
  { 
    id: 3, 
    title: "战略规划", 
    category: "商务", 
    color: "from-purple-600 to-purple-700", 
    subtitle: "STRATEGIC EXCELLENCE",
    preview: "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=400&h=225&fit=crop"
  },
  { 
    id: 4, 
    title: "商业转型", 
    category: "商务", 
    color: "from-slate-700 to-slate-800", 
    subtitle: "Business Transformation Strategy",
    preview: "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=400&h=225&fit=crop"
  },
  { 
    id: 5, 
    title: "律师事务所", 
    category: "商务", 
    color: "from-amber-700 to-amber-800", 
    subtitle: "LAWYER",
    preview: "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=400&h=225&fit=crop"
  },
  { 
    id: 6, 
    title: "企业卓越", 
    category: "商务", 
    color: "from-orange-500 to-orange-600", 
    subtitle: "CORPORATE EXCELLENCE",
    preview: "https://images.unsplash.com/photo-1497366216548-37526070297c?w=400&h=225&fit=crop"
  },
  { 
    id: 7, 
    title: "研究报告", 
    category: "科技", 
    color: "from-gray-100 to-gray-200", 
    subtitle: "ADVANCED RESEARCH SYMPOSIUM",
    preview: "https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=400&h=225&fit=crop"
  },
  { 
    id: 8, 
    title: "酒店介绍", 
    category: "创意", 
    color: "from-stone-600 to-stone-700", 
    subtitle: "The Grand Meridian",
    preview: "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=400&h=225&fit=crop"
  },
];

const TEMPLATE_CATEGORIES: TemplateCategory[] = ["全部", "科技", "商务", "创意"];

export default function Home() {
  // ==================== 路由 ====================
  const params = useParams<{ conversationId?: string }>();
  const [, setLocation] = useLocation();

  // ==================== 状态管理 ====================

  // 页面模式
  const [mode, setMode] = useState<"home" | "chat">("home");
  
  // 侧边栏状态
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
  const [currentConversationUuid, setCurrentConversationUuid] = useState<string | null>(null);
  
  // 聊天状态
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentTopic, setCurrentTopic] = useState("");
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  
  // 工具调用状态
  const [autoConfirmCountdown, setAutoConfirmCountdown] = useState<number | null>(null);
  const autoConfirmTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [pendingToolCallId, setPendingToolCallId] = useState<string>("");
  const [isConfirming, setIsConfirming] = useState(false);
  
  // 任务规划状态
  const [taskPlan, setTaskPlan] = useState<TaskPlan | null>(null);
  const [taskPlanStreaming, setTaskPlanStreaming] = useState(false);
  
  // 搜索状态
  const [searchRounds, setSearchRounds] = useState<SearchRound[]>([]);
  const [currentSearchRound, setCurrentSearchRound] = useState(1);
  const [deepThinking, setDeepThinking] = useState("");
  const [deepThinkingStreaming, setDeepThinkingStreaming] = useState(false);
  
  // PPT 状态
  const [pptOutline, setPptOutline] = useState("");
  const [pptOutlineStreaming, setPptOutlineStreaming] = useState(false);
  const [pptHtmlCode, setPptHtmlCode] = useState("");
  const [pptViewMode, setPptViewMode] = useState<PPTViewMode>("preview");
  const [pptProject, setPptProject] = useState<PPTProject | null>(null);
  const [pptProjects, setPptProjects] = useState<PPTProject[]>([]);
  const [isEditMode, setIsEditMode] = useState(false);
  
  // 右侧面板状态
  const [showRightPanel, setShowRightPanel] = useState(false);
  const [rightPanelType, setRightPanelType] = useState<RightPanelType>(null);
  const [targetSlideIndex, setTargetSlideIndex] = useState<number | undefined>(undefined);
  
  // 模板状态
  const [selectedCategory, setSelectedCategory] = useState<TemplateCategory>("全部");
  const [isPptMode, setIsPptMode] = useState(true);
  
  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // ==================== 初始化 ====================

  useEffect(() => {
    // 延迟加载，避免影响主页显示
    const loadData = async () => {
      try {
        await loadConversations();
      } catch (error) {
        // API 失败时静默处理，不影响主页显示
        console.warn("Failed to load conversations, backend may not be running");
      }
      try {
        await loadPPTProjects();
      } catch (error) {
        console.warn("Failed to load PPT projects, backend may not be running");
      }

      // 检查路由参数，如果有 conversation UUID，加载该对话
      if (params.conversationId) {
        try {
          await loadConversation(params.conversationId);
        } catch (error) {
          console.error("Failed to load conversation from URL:", error);
        }
      }
    };
    loadData();
  }, [params.conversationId]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ==================== API 调用 ====================
  
  const loadConversations = async () => {
    try {
      const data = await getConversations();
      setConversations(data);
    } catch (error) {
      console.error("Failed to load conversations:", error);
    }
  };

  const loadPPTProjects = async () => {
    try {
      const data = await getPPTProjects();
      setPptProjects(data);
    } catch (error) {
      console.error("Failed to load PPT projects:", error);
    }
  };

  const loadConversation = async (uuid: string) => {
    try {
      const data = await getConversationDetail(uuid);
      setCurrentConversationId(data.conversation.id);
      setCurrentConversationUuid(uuid);

      // 恢复消息
      if (data.messages) {
        const restoredMessages: Message[] = data.messages.map((msg: any) => ({
          id: msg.id.toString(),
          role: msg.role,
          content: msg.content,
          timestamp: new Date(msg.created_at).getTime(),
          toolCalls: msg.tool_calls?.map((tc: any) => ({
            id: tc.id.toString(),
            type: tc.tool_type,
            name: tc.tool_name,
            status: tc.status,
            // 合并 arguments 和 result，确保 query 和 results 都能获取到
            data: { ...(tc.arguments || {}), ...(tc.result || {}) },
          })),
        }));
        setMessages(restoredMessages);
      }
      
      // 恢复 PPT 项目
      if (data.ppt_project) {
        const project = data.ppt_project;
        setPptProject(project);

        // 恢复 PPT HTML 代码
        // 后端返回的数据结构：project.slides（不是project.versions[].slides）
        if (project.slides && project.slides.length > 0) {
          const htmlCode = project.slides
            .sort((a: any, b: any) => a.page_number - b.page_number)
            .map((slide: any) => slide.html_content)
            .join("\n");
          setPptHtmlCode(htmlCode);
          console.log("[PPT恢复] 成功恢复", project.slides.length, "张幻灯片");
        } else {
          console.warn("[PPT恢复] 未找到幻灯片数据", project);
        }

        // 使用 PPT 项目标题
        setCurrentTopic(project.title);
      } else {
        // 如果没有 PPT 项目，使用对话标题
        setCurrentTopic(data.conversation.title);
      }
      
      // 从工具调用中提取任务规划和搜索数据
      if (data.messages) {
        // 提取任务规划
        for (const msg of data.messages) {
          if (msg.tool_calls) {
            for (const tc of msg.tool_calls) {
              if (tc.tool_type === "task_plan" && tc.task_plan) {
                setTaskPlan({
                  streamContent: tc.task_plan.plan_content,  // 使用streamContent而不是content
                  steps: tc.task_plan.steps || [],
                });
              }
            }
          }
        }
        
        // 提取搜索轮次
        const extractedRounds: SearchRound[] = [];
        for (const msg of data.messages) {
          if (msg.tool_calls) {
            for (const tc of msg.tool_calls) {
              if ((tc.tool_type === "web_search" || tc.tool_type === "search") && tc.search_rounds) {
                for (const sr of tc.search_rounds) {
                  extractedRounds.push({
                    round: sr.round_number,
                    query: sr.query,
                    results: sr.results?.map((r: any) => ({
                      title: r.title,
                      url: r.url,
                      snippet: r.snippet,
                      date: r.date,
                    })) || [],
                    isCompleted: true,
                    thinking: "",
                  });
                }
              }
            }
          }
        }
        if (extractedRounds.length > 0) {
          setSearchRounds(extractedRounds);
          setCurrentSearchRound(extractedRounds[extractedRounds.length - 1].round);
        }
        
        // 提取 PPT 大纲
        for (const msg of data.messages) {
          if (msg.tool_calls) {
            for (const tc of msg.tool_calls) {
              if (tc.tool_type === "ppt_outline" && tc.result) {
                setPptOutline(tc.result.content || "");
              }
            }
          }
        }
      }
      
      setMode("chat");
    } catch (error) {
      console.error("Failed to load conversation:", error);
    }
  };

  // ==================== 事件处理 ====================
  
  const handleNewChat = () => {
    // 取消正在进行的请求
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    // 重置所有状态
    setCurrentConversationId(null);
    setCurrentConversationUuid(null);
    setMessages([]);
    setInputValue("");
    setIsLoading(false);
    setCurrentTopic("");
    setTaskPlan(null);
    setTaskPlanStreaming(false);
    setSearchRounds([]);
    setCurrentSearchRound(1);
    setDeepThinking("");
    setDeepThinkingStreaming(false);
    setPptOutline("");
    setPptOutlineStreaming(false);
    setPptHtmlCode("");
    setPptProject(null);
    setShowRightPanel(false);
    setRightPanelType(null);
    setAutoConfirmCountdown(null);
    
    if (autoConfirmTimerRef.current) {
      clearInterval(autoConfirmTimerRef.current);
    }

    setMode("home");
    // 导航到新对话页面
    setLocation('/chat');
  };

  const handleSelectConversation = (conversation: Conversation) => {
    loadConversation(conversation.uuid);
    // 导航到对话页面
    setLocation(`/chat/${conversation.uuid}`);
  };

  const handleDeleteConversation = async (id: number) => {
    try {
      await deleteConversation(id);
      setConversations(prev => prev.filter(c => c.id !== id));
      
      if (currentConversationId === id) {
        handleNewChat();
      }
    } catch (error) {
      console.error("Failed to delete conversation:", error);
    }
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: inputValue.trim(),
      timestamp: Date.now(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);
    // 只在新对话时设置临时 topic，后续会被 AI 生成的主题替换
    if (!currentConversationId) {
      setCurrentTopic(userMessage.content);
    }
    setMode("chat");

    // 创建 AbortController
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instruction: userMessage.content,
          conversation_id: currentConversationId,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error("Chat request failed");
      }

      // 捕获 session_id
      const sessionId = response.headers.get("X-Session-Id");
      if (sessionId) {
        setCurrentSessionId(sessionId);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              handleStreamEvent(data);
            } catch (e) {
              console.error("Failed to parse SSE data:", e);
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name !== "AbortError") {
        console.error("Chat error:", error);
        setMessages(prev => [
          ...prev,
          {
            id: `error-${Date.now()}`,
            role: "assistant",
            content: "抱歉，发生了错误，请稍后重试。",
            timestamp: Date.now(),
          },
        ]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleStreamEvent = (data: any) => {
    // 收到任何事件时，取消确认加载状态
    if (isConfirming) {
      setIsConfirming(false);
    }

    console.log("[Frontend] SSE Event:", data.type, data);
    switch (data.type) {
      case "conversation_created":
        setCurrentConversationId(data.conversation_id);
        setCurrentConversationUuid(data.conversation_uuid);
        // 导航到对话页面
        if (data.conversation_uuid) {
          setLocation(`/chat/${data.conversation_uuid}`);
        }
        loadConversations();
        break;

      case "message":
        setMessages(prev => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.role === "assistant" && !lastMsg.toolCalls?.length) {
            return [
              ...prev.slice(0, -1),
              {
                ...lastMsg,
                content: lastMsg.content + data.content,
                streaming: data.streaming !== false // 保持流式状态，除非明确设置为 false
              },
            ];
          }
          return [
            ...prev,
            {
              id: `assistant-${Date.now()}`,
              role: "assistant",
              content: data.content,
              timestamp: Date.now(),
              streaming: data.streaming === true, // 只有明确设置为 true 时才显示流式光标
            },
          ];
        });
        break;

      case "tool_call":
        handleToolCall(data);
        break;

      case "task_plan_stream":
        setTaskPlanStreaming(true);
        setShowRightPanel(true);
        setRightPanelType("task_plan");
        setTaskPlan(prev => ({
          ...prev,
          streamContent: (prev?.streamContent || "") + data.content,
        }));
        break;

      case "task_plan_complete":
        setTaskPlanStreaming(false);
        if (data.data) {
          setTaskPlan(data.data);
        }
        break;

      case "search_start":
        setSearchRounds(prev => [
          ...prev,
          {
            round: data.round,
            query: data.query,
            results: [],
            isCompleted: false,
          },
        ]);
        setCurrentSearchRound(data.round);
        setShowRightPanel(true);
        setRightPanelType("web_search");
        break;

      case "search_result":
        setSearchRounds(prev =>
          prev.map(r =>
            r.round === data.round
              ? { ...r, results: [...r.results, data.result] }
              : r
          )
        );
        break;

      case "search_complete":
        setSearchRounds(prev =>
          prev.map(r =>
            r.round === data.round ? { ...r, isCompleted: true } : r
          )
        );
        break;

      case "deep_thinking_start":
        // 深度思考开始，清空之前的内容并显示搜索面板
        setDeepThinking("");
        setDeepThinkingStreaming(true);
        setShowRightPanel(true);
        setRightPanelType("web_search");
        break;

      case "deep_thinking_stream":
        setDeepThinkingStreaming(true);
        setDeepThinking(prev => prev + data.content);
        break;

      case "deep_thinking_complete":
        setDeepThinkingStreaming(false);
        // 使用后端发送的完整内容，而不是状态中的 deepThinking
        const completeThinking = data.content || deepThinking;
        setSearchRounds(prev =>
          prev.map(r =>
            r.round === currentSearchRound
              ? { ...r, thinking: completeThinking }
              : r
          )
        );
        break;

      case "ppt_outline_stream":
        setPptOutlineStreaming(true);
        setShowRightPanel(true);
        setRightPanelType("ppt_outline");
        setPptOutline(prev => prev + data.content);
        break;

      case "ppt_outline_complete":
        setPptOutlineStreaming(false);
        break;

      case "ppt_slide":
        setPptHtmlCode(prev => prev + data.html);
        setShowRightPanel(true);
        setRightPanelType("ppt_preview");
        break;

      case "ppt_complete":
        if (data.project) {
          setPptProject(data.project);
          loadPPTProjects();
        }
        break;

      case "done":
        setIsLoading(false);
        loadConversations();
        break;
    }
  };

  const handleToolCall = (data: any) => {
    console.log("[Frontend] Received tool_call data:", JSON.stringify(data, null, 2));
    console.log("[Frontend] data.data field:", data.data);

    const toolCall: ToolCall = {
      id: data.id || `tool-${Date.now()}`,
      type: data.tool_type,
      name: data.tool_name,
      status: data.status || "running",
      data: data.data || {},
    };

    setMessages(prev => {
      const lastMsg = prev[prev.length - 1];
      if (lastMsg?.role === "assistant") {
        return [
          ...prev.slice(0, -1),
          {
            ...lastMsg,
            toolCalls: [...(lastMsg.toolCalls || []), toolCall],
          },
        ];
      }
      return [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: "",
          timestamp: Date.now(),
          toolCalls: [toolCall],
        },
      ];
    });

    // 处理补充信息工具
    if (data.tool_type === "supplement_info" && data.status === "pending") {
      setPendingToolCallId(toolCall.id);
      startAutoConfirmCountdown();

      // 从补充信息中提取 AI 生成的主题
      const generatedTopic = data.data?.topic;
      if (generatedTopic && typeof generatedTopic === "string") {
        console.log("[Frontend] Using AI-generated topic:", generatedTopic);
        setCurrentTopic(generatedTopic);
      }
    }

    // 处理任务规划工具
    if (data.tool_type === "task_plan" || data.tool_type === "plan_task") {
      const planData = data.data as any;
      const taskPlanData = {
        coreRequirement: planData.coreRequirement || planData.core_requirement || planData.goal || "",
        problemAnalysis: planData.problemAnalysis || planData.problem_analysis,
        informationDimensions: planData.informationDimensions || planData.information_dimensions,
        searchStrategy: planData.searchStrategy || planData.search_strategy,
        timeScope: planData.timeScope || planData.time_scope,
        details: planData.details || planData.requirements || [],
        steps: planData.steps || planData.tasks || [],
        streamContent: planData.streamContent || planData.content || "",
        streaming: planData.streaming || false,
      };
      setTaskPlan(taskPlanData);
      setShowRightPanel(true);
      setRightPanelType("task_plan");
    }

    // 处理搜索工具
    if (data.tool_type === "web_search" || data.tool_type === "search") {
      const searchData = data.data as any;
      const round = searchData.round || 1;
      const results = searchData.results || [];

      console.log("[Frontend] web_search tool_call:", {
        query: searchData.query,
        round: round,
        resultsCount: results.length
      });

      setSearchRounds(prev => {
        const existingRound = prev.find(r => r.round === round);
        if (existingRound) {
          return prev.map(r =>
            r.round === round
              ? { ...r, results: [...r.results, ...results], isCompleted: true }
              : r
          );
        }
        return [
          ...prev,
          {
            round,
            query: searchData.query || "",
            results,
            isCompleted: true,
          },
        ];
      });
      setCurrentSearchRound(round);
      setShowRightPanel(true);
      setRightPanelType("web_search");
    }

    // 处理 PPT 大纲工具
    if (data.tool_type === "ppt_outline") {
      const outlineData = data.data as any;
      setPptOutline(outlineData.content || "");
      setShowRightPanel(true);
      setRightPanelType("ppt_outline");
    }

    // 处理 PPT 幻灯片创建工具
    // 注意：不再在这里累积HTML，因为handleStreamEvent已经处理了ppt_slide事件
    // 这里只需要处理工具调用的显示（按钮）
    if (data.tool_type === "create_slide" || data.tool_type === "ppt_generate") {
      // 打开 PPT 预览面板
      setShowRightPanel(true);
      setRightPanelType("ppt_preview");
    }
  };

  const startAutoConfirmCountdown = () => {
    setAutoConfirmCountdown(30);
    
    if (autoConfirmTimerRef.current) {
      clearInterval(autoConfirmTimerRef.current);
    }

    autoConfirmTimerRef.current = setInterval(() => {
      setAutoConfirmCountdown(prev => {
        if (prev === null || prev <= 1) {
          clearInterval(autoConfirmTimerRef.current!);
          handleConfirmInfo(pendingToolCallId, {});
          return null;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const cancelAutoConfirm = () => {
    if (autoConfirmTimerRef.current) {
      clearInterval(autoConfirmTimerRef.current);
    }
    setAutoConfirmCountdown(null);
  };

  const handleConfirmInfo = async (toolCallId: string, selectedData: Record<string, unknown>) => {
    cancelAutoConfirm();

    // 立即更新工具状态，让卡片立即折叠
    setMessages(prev =>
      prev.map(msg => ({
        ...msg,
        toolCalls: msg.toolCalls?.map(tc =>
          tc.id === toolCallId ? { ...tc, status: "confirmed" as const } : tc
        ),
      }))
    );

    // 设置确认状态，显示加载动画
    setIsConfirming(true);

    try {
      const response = await fetch("/api/ppt/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: currentSessionId,
          conversation_id: currentConversationId,
          supplement_data: selectedData,
        }),
      });

      if (!response.ok) {
        throw new Error("Confirm request failed");
      }

      // 处理流式响应
      const reader = response.body?.getReader();
      if (reader) {
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                handleStreamEvent(data);
              } catch (e) {
                console.error("Failed to parse SSE data:", e);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error("Confirm error:", error);
    }
  };

  const openRightPanel = (type: RightPanelType) => {
    setRightPanelType(type);
    setShowRightPanel(true);
  };

  const handleSelectProject = (project: PPTProject) => {
    setPptProject(project);
    
    // 加载 PPT HTML 代码
    if (project.versions && project.versions.length > 0) {
      const latestVersion = project.versions[project.versions.length - 1];
      if (latestVersion.slides) {
        const htmlCode = latestVersion.slides
          .sort((a: any, b: any) => a.page_number - b.page_number)
          .map((slide: any) => slide.html_content)
          .join("\n");
        setPptHtmlCode(htmlCode);
      }
    }
    
    setCurrentTopic(project.title);
    setRightPanelType("ppt_preview");
  };

  const handleScrollToSlide = (slideIndex: number) => {
    // 设置目标幻灯片索引，触发PPTPreviewPanel的滚动
    setTargetSlideIndex(slideIndex);
    // 打开PPT预览面板
    setShowRightPanel(true);
    setRightPanelType("ppt_preview");
  };

  // 弹窗状态
  const [showDownloadModal, setShowDownloadModal] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [showTaskFilesModal, setShowTaskFilesModal] = useState(false);

  const handleDownload = () => {
    if (pptProject) {
      setShowDownloadModal(true);
    }
  };

  const handleShare = () => {
    if (pptProject) {
      setShowShareModal(true);
    }
  };

  const handlePlay = () => {
    // TODO: 实现播放功能
    console.log("Play PPT");
  };

  const handleFullscreen = () => {
    // TODO: 实现全屏功能
    console.log("Fullscreen PPT");
  };

  // 过滤模板
  const filteredTemplates = TEMPLATES.filter(
    t => selectedCategory === "全部" || t.category === selectedCategory
  );

  // ==================== 渲染 ====================
  
  return (
    <div className="h-screen flex bg-background">
      {/* 左侧边栏 - 历史对话 */}
      <ConversationSidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={handleDeleteConversation}
        onNewChat={handleNewChat}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* 中间区域 - 聊天 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 头部 - 只在聊天模式下显示 */}
        {mode === "chat" && (
          <header className="h-14 border-b border-border flex items-center justify-between px-4 bg-background shrink-0">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground truncate max-w-[400px]">
                {currentTopic}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {/* 文件按钮 - 始终显示 */}
              <button
                onClick={() => setShowTaskFilesModal(true)}
                className="p-2 hover:bg-muted rounded-lg transition-colors"
                title="任务文件"
              >
                <FolderOpen className="h-4 w-4 text-muted-foreground" />
              </button>
            </div>
          </header>
        )}

        {/* 主内容区 */}
        <div className="flex-1 overflow-hidden">
          {mode === "home" ? (
            // 首页 - 智谱清言风格
            <ScrollArea className="h-full">
              <div className="min-h-full flex flex-col">
                {/* 上半部分：欢迎语 + 输入框 */}
                <div className="flex-shrink-0 pt-16 pb-12 px-4 ">
                  
                  <div className="max-w-3xl mx-auto mt-26">    
                    {/* 欢迎语 */}
                    <h1 className="text-3xl font-bold mb-8 text-center flex items-center justify-center gap-2">
                      <span>👋</span>
                      <span>嗨，今天有什么我可以帮你的吗？</span>
                    </h1>
                    
                    {/* 大输入框 - 智谱清言风格 */}
                    <div className="border border-border rounded-2xl bg-background shadow-sm overflow-hidden">
                      {/* 输入区域 */}
                      <textarea
                        ref={inputRef}
                        value={inputValue}
                        onChange={e => setInputValue(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === "Enter" && !e.shiftKey) {
                            e.preventDefault();
                            handleSendMessage();
                          }
                        }}
                        placeholder="告诉我PPT的主题或内容"
                        className="w-full px-5 pt-5 pb-3 bg-transparent resize-none focus:outline-none min-h-[80px] max-h-[200px] text-base"
                        rows={2}
                      />
                      
                      {/* 底部工具栏 */}
                      <div className="flex items-center justify-between px-4 py-3 border-t border-border/50">
                        {/* 左侧按钮 */}
                        <div className="flex items-center gap-1">
                          <button className="p-2 hover:bg-muted rounded-lg transition-colors">
                            <Paperclip className="h-5 w-5 text-muted-foreground" />
                          </button>
                          <button className="p-2 hover:bg-muted rounded-lg transition-colors">
                            <Settings className="h-5 w-5 text-muted-foreground" />
                          </button>
                          {/* PPT 模式标签 */}
                          {isPptMode && (
                            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-primary/10 rounded-lg ml-2">
                              <FileSliders className="h-4 w-4 text-primary" />
                              <span className="text-sm text-primary font-medium">PPT模式</span>
                              <button
                                onClick={() => setIsPptMode(false)}
                                className="ml-1 hover:bg-primary/20 rounded p-0.5"
                              >
                                <X className="h-3.5 w-3.5 text-primary" />
                              </button>
                            </div>
                          )}
                        </div>
                        
                        {/* 右侧发送按钮 */}
                        <button
                          onClick={handleSendMessage}
                          disabled={!inputValue.trim() || isLoading}
                          className="p-2.5 bg-primary text-white rounded-full hover:bg-primary/90 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        >
                          <Send className="h-5 w-5" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 下半部分：分类标签 + 模板网格 */}
                <div className="flex-1 px-4 pb-8">
                  {/* 分类标签 */}
                  <div className="flex justify-center gap-6 mb-8">
                    {TEMPLATE_CATEGORIES.map(cat => (
                      <button
                        key={cat}
                        onClick={() => setSelectedCategory(cat)}
                        className={cn(
                          "px-2 py-1 text-base transition-colors border-b-2",
                          selectedCategory === cat
                            ? "text-foreground border-foreground font-medium"
                            : "text-muted-foreground border-transparent hover:text-foreground"
                        )}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>

                  {/* 模板网格 - 大卡片风格 */}
                  <div className="max-w-6xl mx-auto">
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
                      {filteredTemplates.map(template => (
                        <button
                          key={template.id}
                          onClick={() => {
                            setInputValue(`帮我制作一个${template.title}的PPT`);
                            inputRef.current?.focus();
                          }}
                          className="group relative aspect-[16/9] rounded-xl overflow-hidden shadow-lg hover:shadow-2xl transition-all hover:scale-[1.02] bg-white"
                        >
                          {/* 背景图片 */}
                          {template.preview ? (
                            <img 
                              src={template.preview} 
                              alt={template.title}
                              className="absolute inset-0 w-full h-full object-cover"
                            />
                          ) : (
                            <div className={cn(
                              "absolute inset-0 bg-gradient-to-br",
                              template.color
                            )} />
                          )}
                          
                          {/* 渐变遮罩 */}
                          <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent" />
                          
                          {/* 内容 */}
                          <div className="absolute inset-0 p-4 flex flex-col justify-end text-white">
                            <div className="text-xs opacity-90 mb-1 uppercase tracking-wide">{template.subtitle}</div>
                            <h3 className="font-bold text-lg leading-tight">{template.title}</h3>
                          </div>
                          
                          {/* 悬浮效果 */}
                          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors" />
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </ScrollArea>
          ) : (
            // 聊天模式
            <ScrollArea className="h-full">
              <div className="max-w-3xl mx-auto p-6">
                {messages.map((message, index) => {
                  const isFirstAiMessage =
                    message.role === "assistant" &&
                    messages.slice(0, index).filter(m => m.role === "assistant").length === 0;

                  return (
                    <MessageItem
                      key={message.id}
                      message={message}
                      onOpenPanel={openRightPanel}
                      onConfirmInfo={handleConfirmInfo}
                      currentTopic={currentTopic}
                      autoConfirmCountdown={autoConfirmCountdown}
                      onCancelAutoConfirm={cancelAutoConfirm}
                      isFirstAiMessage={isFirstAiMessage}
                      onSetSearchRound={setCurrentSearchRound}
                      onScrollToSlide={handleScrollToSlide}
                    />
                  );
                })}

                {isLoading && messages.length > 0 && messages[messages.length - 1]?.role === "user" && (() => {
                  const isFirstAiResponse = messages.filter(m => m.role === "assistant").length === 0;
                  return (
                    <div className="mb-6">
                      {isFirstAiResponse ? (
                        // 首次 AI 响应：保持原样
                        <>
                          <div className="flex items-center gap-2 mb-3">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-sm shrink-0">
                              <svg viewBox="0 0 24 24" className="w-5 h-5 text-white" fill="currentColor">
                                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                              </svg>
                            </div>
                            <span className="text-sm font-medium text-foreground">SlideAgent</span>
                            <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">AI</span>
                          </div>
                          <div className="ml-10">
                            <span className="text-sm text-muted-foreground">让我先核对下本轮任务的目标和重点偏好，正在梳理您的需求~</span>
                            <span className="inline-flex items-center ml-1">
                              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                            </span>
                          </div>
                        </>
                      ) : (
                        // 后续响应：使用新的加载动画
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-muted-foreground">正在生成中...</span>
                          <LoadingDots />
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* 确认后的加载状态 */}
                {isConfirming && (
                  <div className="mb-6">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground">正在生成中...</span>
                      <LoadingDots />
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>
          )}
        </div>

        {/* 输入框 - 只在聊天模式下显示 */}
        {mode === "chat" && (
        <div className="p-4 border-t border-border bg-background shrink-0">
          <div className="max-w-3xl mx-auto">
            <div className="relative">
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                onKeyDown={e => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                placeholder="想调整内容、样式或风格等吗，直接告诉我吧"
                className="w-full px-4 py-3 pr-24 rounded-xl border border-border bg-background resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 min-h-[52px] max-h-[200px]"
                rows={1}
              />

              <div className="absolute right-2 bottom-2 flex items-center gap-1">
                <button className="p-2 hover:bg-muted rounded-lg transition-colors">
                  <Paperclip className="h-4 w-4 text-muted-foreground" />
                </button>
                <button className="p-2 hover:bg-muted rounded-lg transition-colors">
                  <Settings className="h-4 w-4 text-muted-foreground" />
                </button>

                {/* PPT 模式标签 */}
                {isPptMode && (
                  <div className="flex items-center gap-1 px-2 py-1 bg-primary/10 rounded-lg">
                    <FileSliders className="h-3.5 w-3.5 text-primary" />
                    <span className="text-xs text-primary font-medium">PPT模式</span>
                    <button
                      onClick={() => setIsPptMode(false)}
                      className="ml-1 hover:bg-primary/20 rounded p-0.5"
                    >
                      <X className="h-3 w-3 text-primary" />
                    </button>
                  </div>
                )}

                <button
                  onClick={handleSendMessage}
                  disabled={!inputValue.trim() || isLoading}
                  className={cn(
                    "p-2 rounded-lg transition-colors",
                    inputValue.trim() && !isLoading
                      ? "bg-primary text-white hover:bg-primary/90"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  <Send className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
        )}
      </div>

      {/* 右侧面板 */}
      <RightPanel
        rightPanelType={rightPanelType}
        setRightPanelType={setRightPanelType}
        showRightPanel={showRightPanel}
        setShowRightPanel={setShowRightPanel}
        pptHtmlCode={pptHtmlCode}
        pptViewMode={pptViewMode}
        setPptViewMode={setPptViewMode}
        pptProject={pptProject}
        currentTopic={currentTopic}
        isEditMode={isEditMode}
        setIsEditMode={setIsEditMode}
        targetSlideIndex={targetSlideIndex}
        taskPlan={taskPlan}
        taskPlanStreaming={taskPlanStreaming}
        searchRounds={searchRounds}
        currentSearchRound={currentSearchRound}
        setCurrentSearchRound={setCurrentSearchRound}
        deepThinking={deepThinking}
        deepThinkingStreaming={deepThinkingStreaming}
        pptOutline={pptOutline}
        pptOutlineStreaming={pptOutlineStreaming}
        pptProjects={pptProjects}
        onSelectProject={handleSelectProject}
        onDownload={handleDownload}
        onShare={handleShare}
        onPlay={handlePlay}
        onFullscreen={handleFullscreen}
      />

      {/* 下载弹窗 */}
      {pptProject && (
        <DownloadModal
          isOpen={showDownloadModal}
          onClose={() => setShowDownloadModal(false)}
          projectId={pptProject.id}
          versionId={pptProject.current_version?.id}
          title={pptProject.title}
        />
      )}

      {/* 分享弹窗 */}
      {pptProject && (
        <ShareModal
          isOpen={showShareModal}
          onClose={() => setShowShareModal(false)}
          projectId={pptProject.id}
          versionId={pptProject.current_version?.id}
          title={pptProject.title}
        />
      )}

      {/* 任务文件对话框 */}
      <TaskFilesModal
        isOpen={showTaskFilesModal}
        onClose={() => setShowTaskFilesModal(false)}
        pptProject={pptProject}
        onSelectProject={(project) => {
          handleSelectProject(project);
          setShowTaskFilesModal(false);
          setShowRightPanel(true);
          setRightPanelType("ppt_preview");
        }}
      />
    </div>
  );
}

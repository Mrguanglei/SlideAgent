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
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useComposition } from "@/hooks/useComposition";
import {
  FileSliders,
  Send,
  Paperclip,
  Settings,
  Loader2,
  X,
  MessageSquarePlus,
  FolderOpen,
  Pause,
  Database,
  Brain,
} from "lucide-react";

// 组件导入
import ConversationSidebar from "@/components/ConversationSidebar";
import MessageItem, { AIAvatar, AI_AVATAR_OFFSET_X } from "@/components/MessageItem";
import RightPanel from "@/components/RightPanel";
import DownloadModal from "@/components/DownloadModal";
import ShareModal from "@/components/ShareModal";
import TaskFilesModal from "@/components/TaskFilesModal";
import LoadingDots from "@/components/LoadingDots";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { KnowledgeBaseSelector } from "@/components/KnowledgeBaseSelector";

// 类型导入
import type {
  Message,
  ToolCall,
  TaskPlan,
  SearchRound,
  ImageSearchRound,
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
  updateConversation,
  deleteConversation,
  getPPTProjects,
  uploadFile,
  type UploadResponse,
  type DocumentResponse,
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
  const [showKbSelector, setShowKbSelector] = useState(false);

  // Popover state for file upload menus
  const [homePopoverOpen, setHomePopoverOpen] = useState(false);
  const [chatPopoverOpen, setChatPopoverOpen] = useState(false);

  // 聊天状态
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [activeAttachments, setActiveAttachments] = useState<UploadResponse[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // IME composition handling for home mode textarea
  const homeComposition = useComposition<HTMLTextAreaElement>({
    onKeyDown: (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    }
  });

  // IME composition handling for chat mode textarea
  const chatComposition = useComposition<HTMLTextAreaElement>({
    onKeyDown: (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    }
  });

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      try {
        const response = await uploadFile(file);
        setActiveAttachments(prev => [...prev, response]);
        toast.success("文件上传成功");
        // Close the popover after successful upload
        setHomePopoverOpen(false);
        setChatPopoverOpen(false);
      } catch (error) {
        console.error("File upload failed:", error);
        toast.error("文件上传失败");
      } finally {
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    }
  };

  const handleKbSelect = (docs: DocumentResponse[]) => {
    const newAttachments: UploadResponse[] = docs.map(doc => ({
      id: String(doc.id),
      filename: doc.display_name || doc.filename,
      file_path: "", // Managed by backend via knowledge_document_id
      content_type: doc.file_type,
      size: doc.file_size,
      knowledge_document_id: doc.id
    }));
    setActiveAttachments(prev => [...prev, ...newAttachments]);
    setShowKbSelector(false);
    // Close the popover after selection
    setHomePopoverOpen(false);
    setChatPopoverOpen(false);
    toast.success(`已添加 ${docs.length} 个知识库文件`);
  };
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
  const [imageSearchRounds, setImageSearchRounds] = useState<ImageSearchRound[]>([]);
  const [currentImageSearchRound, setCurrentImageSearchRound] = useState(1);
  const lastCompletedSearchRoundRef = useRef(0);
  const pendingImagePanelRoundRef = useRef<number | null>(null);

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

  // 深度思考模式状态
  const [deepThinkingMode, setDeepThinkingMode] = useState(false);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isStreamingRef = useRef(false); // 跟踪是否正在进行本地流式传输
  const currentSessionIdRef = useRef<string | null>(null);
  const currentConversationIdRef = useRef<number | null>(null);
  const thinkingModeForStreamRef = useRef(false);
  const currentThinkingToolIdRef = useRef<string | null>(null);
  const rightPanelOpenTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (rightPanelOpenTimerRef.current) {
        clearTimeout(rightPanelOpenTimerRef.current);
      }
    };
  }, []);

  // Sync Refs
  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  useEffect(() => {
    currentConversationIdRef.current = currentConversationId;
  }, [currentConversationId]);

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

  // 轮询机制：当任务正在运行且没有本地流式传输时（即切换对话后），定期刷新状态
  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (isLoading && !isStreamingRef.current && currentConversationUuid) {
      interval = setInterval(() => {
        // 使用静默加载，避免闪烁（这里复用 loadConversation，实际可能需要优化以减少全量替换的视觉影响）
        // 但为了保证数据同步，直接调用是可行的，因为 React diff 会处理 DOM 更新
        console.log("Polling conversation status...");
        loadConversation(currentConversationUuid);
      }, 3000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isLoading, currentConversationUuid]);

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

      // 设置 session_id
      if (data.session_id) {
        console.log(`[loadConversation] Setting session_id: ${data.session_id}`);
        setCurrentSessionId(data.session_id);
      }

      // 根据 task_status 设置 isLoading 状态
      // 只有当 task_status 为 running 且 currentConversationId 匹配时才设置 isLoading
      if (data.task_status === "running") {
        setIsLoading(true);
        setIsEditMode(false); // 正在运行时强制退出编辑模式
      } else {
        setIsLoading(false);
      }

      // 重置图片搜索状态，避免切换对话时残留
      setImageSearchRounds([]);
      setCurrentImageSearchRound(1);

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
            data: { ...(tc.arguments || {}), ...(tc.result || {}) },
          })),
          streaming: false, // 恢复的历史消息不应显示"正在生成..."
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

        // 提取图片搜索轮次
        const extractedImageRoundsMap = new Map<number, ImageSearchRound>();
        for (const msg of data.messages) {
          if (msg.tool_calls) {
            for (const tc of msg.tool_calls) {
              if (tc.tool_type === "image_search") {
                const rawRound = tc.arguments?.round ?? tc.result?.round ?? 1;
                const round = typeof rawRound === "number" ? rawRound : Number(rawRound) || 1;
                const query = tc.arguments?.query || tc.result?.query || "";
                const images = tc.result?.images || tc.arguments?.images || [];
                const existing = extractedImageRoundsMap.get(round);
                if (existing) {
                  existing.images = [...existing.images, ...images];
                } else {
                  extractedImageRoundsMap.set(round, {
                    round,
                    query,
                    images,
                    isCompleted: true,
                  });
                }
              }
            }
          }
        }
        const extractedImageRounds = Array.from(extractedImageRoundsMap.values()).sort((a, b) => a.round - b.round);
        if (extractedImageRounds.length > 0) {
          setImageSearchRounds(extractedImageRounds);
          setCurrentImageSearchRound(extractedImageRounds[extractedImageRounds.length - 1].round);
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
    setImageSearchRounds([]);
    setCurrentImageSearchRound(1);
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
      toast.success("对话已删除");
    } catch (error) {
      console.error("Failed to delete conversation:", error);
      toast.error("删除失败");
    }
  };

  // 重命名对话
  const handleRenameConversation = async (id: number, newTitle: string) => {
    try {
      await updateConversation(id, newTitle);
      setConversations(prev =>
        prev.map(c => (c.id === id ? { ...c, title: newTitle } : c))
      );
      toast.success("重命名成功");
    } catch (error) {
      console.error("Failed to rename conversation:", error);
      toast.error("重命名失败");
    }
  };

  // 置顶/取消置顶对话
  const handlePinConversation = async (id: number, pinned: boolean) => {
    try {
      // 更新本地状态（置顶的对话排在前面）
      setConversations(prev => {
        const updated = prev.map(c =>
          c.id === id ? { ...c, pinned } as Conversation : c
        );
        // 排序：置顶的在前面
        return updated.sort((a, b) => {
          const aPinned = (a as any).pinned ? 1 : 0;
          const bPinned = (b as any).pinned ? 1 : 0;
          if (aPinned !== bPinned) return bPinned - aPinned;
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
        });
      });
      toast.success(pinned ? "已置顶" : "已取消置顶");
    } catch (error) {
      console.error("Failed to pin conversation:", error);
      toast.error("操作失败");
    }
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    thinkingModeForStreamRef.current = deepThinkingMode;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: inputValue.trim(),
      timestamp: Date.now(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue("");
    const currentAttachments = activeAttachments;
    setActiveAttachments([]);
    setIsLoading(true);

    // 更新当前对话的任务状态为 running
    if (currentConversationId) {
      setConversations(prev =>
        prev.map(c =>
          c.id === currentConversationId ? { ...c, task_status: "running" as const } : c
        )
      );
    }

    // 只在新对话时设置临时 topic，后续会被 AI 生成的主题替换
    if (!currentConversationId) {
      setCurrentTopic(userMessage.content);
    }
    setMode("chat");

    // 创建 AbortController
    abortControllerRef.current = new AbortController();

    let response;

    // PPT 生成请求
    if (isPptMode) {
      setIsLoading(true);
      setIsEditMode(false); // 开始生成时强制退出编辑模式
      isStreamingRef.current = true; // 标记开始流式传输

      response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instruction: userMessage.content,
          conversation_id: currentConversationId,
          attachments: currentAttachments.length > 0 ? currentAttachments : undefined,
          deep_thinking_mode: deepThinkingMode,
        }),
        signal: abortControllerRef.current.signal,
      });
    } else {
      response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instruction: userMessage.content,
          conversation_id: currentConversationId,
          deep_thinking_mode: deepThinkingMode,
        }),
        signal: abortControllerRef.current.signal,
      });
    }

    try {
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
      // 刷新对话列表以同步最新的 task_status
      loadConversations();
      isStreamingRef.current = false; // 标记流式传输结束
    }
  };

  const appendToolCallToLastAssistant = (toolCall: ToolCall) => {
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
  };

  const updateToolCallById = (toolId: string, updater: (tool: ToolCall) => ToolCall) => {
    setMessages(prev =>
      prev.map(msg => {
        if (!msg.toolCalls || msg.toolCalls.length === 0) return msg;
        const updatedToolCalls = msg.toolCalls.map(tc => (tc.id === toolId ? updater(tc) : tc));
        const changed = updatedToolCalls.some((tc, idx) => tc !== msg.toolCalls![idx]);
        return changed ? { ...msg, toolCalls: updatedToolCalls } : msg;
      })
    );
  };

  const openRightPanelDeferred = useCallback((type: RightPanelType, delay = 180) => {
    if (rightPanelOpenTimerRef.current) {
      clearTimeout(rightPanelOpenTimerRef.current);
    }
    rightPanelOpenTimerRef.current = setTimeout(() => {
      setRightPanelType(type);
      setShowRightPanel(true);
    }, delay);
  }, []);

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
        openRightPanelDeferred("task_plan");
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

      case "search_start": {
        const roundNumber = typeof data.round === "number" ? data.round : Number(data.round) || 1;
        setSearchRounds(prev => [
          ...prev,
          {
            round: roundNumber,
            query: data.query,
            results: [],
            isCompleted: false,
          },
        ]);
        setImageSearchRounds(prev => [
          ...prev,
          {
            round: roundNumber,
            query: data.query,
            images: [],
            isCompleted: false,
          },
        ]);
        setCurrentSearchRound(roundNumber);
        setCurrentImageSearchRound(roundNumber);
        openRightPanelDeferred("web_search");
        break;
      }

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
        if (typeof data.round === "number") {
          lastCompletedSearchRoundRef.current = Math.max(
            lastCompletedSearchRoundRef.current,
            data.round
          );
        }
        if (pendingImagePanelRoundRef.current === data.round) {
          pendingImagePanelRoundRef.current = null;
          openRightPanelDeferred("image_search", 300);
        }
        break;

      case "deep_thinking_start":
        if (!thinkingModeForStreamRef.current) break;
        // 深度思考开始，清空之前的内容并显示搜索面板
        setDeepThinking("");
        setDeepThinkingStreaming(true);
        {
          const toolId = `deep-thinking-${Date.now()}`;
          currentThinkingToolIdRef.current = toolId;
          appendToolCallToLastAssistant({
            id: toolId,
            type: "deep_thinking",
            name: "深度思考",
            status: "running",
            data: { content: "" },
          });
        }
        openRightPanelDeferred("web_search");
        break;

      case "deep_thinking_stream":
        if (!thinkingModeForStreamRef.current) break;
        setDeepThinkingStreaming(true);
        setDeepThinking(prev => prev + data.content);
        {
          const toolId = currentThinkingToolIdRef.current;
          if (toolId) {
            updateToolCallById(toolId, (tool) => {
              const prevContent =
                typeof tool.data?.content === "string" ? tool.data.content : "";
              return {
                ...tool,
                status: "running",
                data: { ...tool.data, content: prevContent + (data.content || "") },
              };
            });
          } else {
            const newToolId = `deep-thinking-${Date.now()}`;
            currentThinkingToolIdRef.current = newToolId;
            appendToolCallToLastAssistant({
              id: newToolId,
              type: "deep_thinking",
              name: "深度思考",
              status: "running",
              data: { content: data.content || "" },
            });
          }
        }
        break;

      case "deep_thinking_complete":
        if (!thinkingModeForStreamRef.current) break;
        setDeepThinkingStreaming(false);
        // 使用后端发送的完整内容，而不是状态中的 deepThinking
        {
          const completeThinking = data.content || deepThinking;
          setSearchRounds(prev =>
            prev.map(r =>
              r.round === currentSearchRound
                ? { ...r, thinking: completeThinking }
                : r
            )
          );
          const toolId = currentThinkingToolIdRef.current;
          if (toolId) {
            updateToolCallById(toolId, (tool) => {
              const prevContent =
                typeof tool.data?.content === "string" ? tool.data.content : "";
              return {
                ...tool,
                status: "completed",
                data: { ...tool.data, content: completeThinking || prevContent },
              };
            });
          } else if (completeThinking) {
            const newToolId = `deep-thinking-${Date.now()}`;
            currentThinkingToolIdRef.current = newToolId;
            appendToolCallToLastAssistant({
              id: newToolId,
              type: "deep_thinking",
              name: "深度思考",
              status: "completed",
              data: { content: completeThinking },
            });
          }
          currentThinkingToolIdRef.current = null;
        }
        break;

      case "ppt_outline_stream":
        setPptOutlineStreaming(true);
        openRightPanelDeferred("ppt_outline");
        setPptOutline(prev => prev + data.content);
        break;

      case "ppt_outline_complete":
        setPptOutlineStreaming(false);
        break;

      case "ppt_slide":
        setPptHtmlCode(prev => prev + data.html);
        openRightPanelDeferred("ppt_preview");
        break;

      case "ppt_complete":
        if (data.project) {
          setPptProject(data.project);
          loadPPTProjects();
        }
        break;

      case "done":
        console.log("[handleStreamEvent] Task completed, resetting states");
        setIsLoading(false);
        isStreamingRef.current = false; // 任务完成时重置流式传输状态
        loadConversations();
        // 刷新当前的对话详情，确保 PPT 项目数据（包括 slides）是最新的，从而开启编辑功能
        if (currentConversationUuid) {
          loadConversation(currentConversationUuid);
        }

        // 确保最后一条消息的 streaming 状态被清除
        setMessages(prev => {
          if (prev.length === 0) return prev;
          const lastMsg = prev[prev.length - 1];
          if (lastMsg.role === "assistant" && lastMsg.streaming) {
            return [
              ...prev.slice(0, -1),
              { ...lastMsg, streaming: false }
            ];
          }
          return prev;
        });
        break;
    }
  };

  const handleToolCall = (data: any) => {
    console.log("[Frontend] Received tool_call data:", JSON.stringify(data, null, 2));
    console.log("[Frontend] data.data field:", data.data);

    const toolCall: ToolCall = {
      id: String(data.id || `tool-${Date.now()}`),
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
      startAutoConfirmCountdown(toolCall.id);

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
      openRightPanelDeferred("task_plan");
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
      openRightPanelDeferred("web_search");
    }

    // 处理图片搜索工具
    if (data.tool_type === "image_search") {
      const imageData = data.data as any;
      const round = typeof imageData.round === "number" ? imageData.round : Number(imageData.round) || 1;
      const images = imageData.images || [];

      setImageSearchRounds(prev => {
        const existingRound = prev.find(r => r.round === round);
        if (existingRound) {
          return prev.map(r =>
            r.round === round
              ? { ...r, images: [...r.images, ...images], isCompleted: true }
              : r
          );
        }
        return [
          ...prev,
          {
            round,
            query: imageData.query || "",
            images,
            isCompleted: true,
          },
        ];
      });
      setCurrentImageSearchRound(round);
      if (lastCompletedSearchRoundRef.current >= round) {
        openRightPanelDeferred("image_search", 300);
      } else {
        pendingImagePanelRoundRef.current = round;
      }
    }

    // 处理 PPT 大纲工具
    if (data.tool_type === "ppt_outline") {
      const outlineData = data.data as any;
      setPptOutline(outlineData.content || "");
      openRightPanelDeferred("ppt_outline");
    }

    // 处理 PPT 幻灯片创建工具
    // 注意：不再在这里累积HTML，因为handleStreamEvent已经处理了ppt_slide事件
    // 这里只需要处理工具调用的显示（按钮）
    if (data.tool_type === "create_slide" || data.tool_type === "ppt_generate") {
      // 打开 PPT 预览面板
      openRightPanelDeferred("ppt_preview");
    }
  };

  const startAutoConfirmCountdown = (toolCallId: string) => {
    console.log(`[startAutoConfirmCountdown] Starting countdown for tool: ${toolCallId}`);
    setAutoConfirmCountdown(30);

    if (autoConfirmTimerRef.current) {
      clearInterval(autoConfirmTimerRef.current);
    }

    autoConfirmTimerRef.current = setInterval(() => {
      setAutoConfirmCountdown(prev => {
        if (prev === null || prev <= 0) {
          console.log(`[startAutoConfirmCountdown] Countdown reached 0, triggering auto-confirm for tool: ${toolCallId}`);
          clearInterval(autoConfirmTimerRef.current!);
          handleConfirmInfo(toolCallId, {});
          return null;
        }
        console.log(`[startAutoConfirmCountdown] Countdown: ${prev - 1}`);
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
    thinkingModeForStreamRef.current = deepThinkingMode;

    // 立即更新工具状态，让卡片立即折叠
    // 立即更新工具状态，让卡片立即折叠
    const targetId = String(toolCallId); // 确保 ID 类型一致
    console.log(`[handleConfirmInfo] Updating status for tool: ${targetId}`);

    setMessages(prev =>
      prev.map(msg => ({
        ...msg,
        toolCalls: msg.toolCalls?.map(tc => {
          const tcId = String(tc.id);
          if (tcId === targetId) {
            console.log(`[handleConfirmInfo] Found target tool ${tcId}, setting to confirmed`);
            return { ...tc, status: "confirmed" as const };
          }
          return tc;
        }),
      }))
    );

    // 设置确认状态，显示加载动画
    setIsConfirming(true);
    setIsLoading(true); // 设置全局加载状态，确保显示暂停按钮
    setIsEditMode(false); // 开始生成时强制退出编辑模式
    isStreamingRef.current = true; // 标记开始流式传输

    console.log(`[handleConfirmInfo] Sending confirm request with:`);
    console.log(`  session_id: ${currentSessionIdRef.current}`);
    console.log(`  conversation_id: ${currentConversationIdRef.current}`);
    console.log(`  supplement_data:`, selectedData);

    try {
      const response = await fetch("/api/ppt/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: currentSessionIdRef.current,
          conversation_id: currentConversationIdRef.current,
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
          if (done) {
            console.log("[handleConfirmInfo] Stream completed");
            break;
          }

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
      } else {
        console.warn("[handleConfirmInfo] No response body reader available");
      }
    } catch (error) {
      console.error("Confirm error:", error);
      setIsLoading(false); // 发生错误时重置状态
      isStreamingRef.current = false; // 错误时也要重置
    } finally {
      setIsConfirming(false); // 无论成功失败，结束确认状态
      console.log("[handleConfirmInfo] Confirm process finished");
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
    if (pptProject) {
      // 在新窗口打开播放页面
      window.open(`/play/${pptProject.id}`, "_blank");
    }
  };

  const handleFullscreen = () => {
    // TODO: 实现全屏功能
    console.log("Fullscreen PPT");
  };

  const handleSaveSlide = async (slideId: number, htmlContent: string) => {
    try {
      // 调用 API 更新幻灯片
      const { updateSlide } = await import("@/lib/api");
      await updateSlide(slideId, htmlContent);

      // 更新本地 pptProject 数据
      setPptProject(prev => {
        if (!prev) return prev;

        // 修复：数据在 project.slides，不是 current_version.slides
        // 使用 any 绕过类型检查，因为后端返回结构与前端类型定义不完全一致
        const slides = (prev as any).slides;
        if (!slides) return prev;

        const updatedSlides = slides.map((slide: any) =>
          slide.id === slideId
            ? { ...slide, html_content: htmlContent, updated_at: new Date().toISOString() }
            : slide
        );

        // 关键：在这里同步更新 pptHtmlCode，确保预览立即刷新
        // 这样可以确保使用的是刚刚更新的 slides 数据，而不是外部可能过时的 state
        const htmlCode = updatedSlides
          .sort((a: any, b: any) => a.page_number - b.page_number)
          .map((slide: any) => slide.html_content)
          .join("\n");
        setPptHtmlCode(htmlCode);

        console.log('✅ Updated pptProject and pptHtmlCode (atomic update)');

        return {
          ...prev,
          slides: updatedSlides,
        } as any;
      });

      console.log(`Slide ${slideId} saved successfully`);
    } catch (error) {
      console.error("Failed to save slide:", error);
      throw error;
    }
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
        onRenameConversation={handleRenameConversation}
        onPinConversation={handlePinConversation}
        onNewChat={handleNewChat}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />


      {/* 中间区域 - 聊天 */}
      <div className="flex-1 flex flex-col min-w-0 relative chat-surface">
        {/* 右上角文件按钮 - 相对于中间区域定位 */}
        {mode === "chat" && (
          <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
            <button
              onClick={() => setShowTaskFilesModal(true)}
              className="p-2 hover:bg-muted rounded-lg transition-colors bg-background/90 backdrop-blur-sm shadow-sm border border-border/50"
              title="任务文件"
            >
              <FolderOpen className="h-4 w-4 text-muted-foreground" />
            </button>
          </div>
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
                      {/* 附件预览 */}
                      {activeAttachments.length > 0 && (
                        <div className="flex flex-wrap gap-2 px-5 pt-3">
                          {activeAttachments.map(file => (
                            <div key={file.id} className="flex items-center gap-1 bg-muted px-2 py-1 rounded-md text-sm border border-border">
                              <span className="truncate max-w-[150px]">{file.filename}</span>
                              <button
                                onClick={() => setActiveAttachments(prev => prev.filter(f => f.id !== file.id))}
                                className="hover:text-destructive transition-colors"
                              >
                                <X className="h-3 w-3" />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                      {/* 输入区域 */}
                      <textarea
                        ref={inputRef}
                        value={inputValue}
                        onChange={e => setInputValue(e.target.value)}
                        onCompositionStart={homeComposition.onCompositionStart}
                        onCompositionEnd={homeComposition.onCompositionEnd}
                        onKeyDown={homeComposition.onKeyDown}
                        placeholder="告诉我PPT的主题或内容"
                        className="w-full px-5 pt-5 pb-3 bg-transparent resize-none focus:outline-none min-h-[80px] max-h-[200px] text-base"
                        rows={2}
                      />

                      {/* 底部工具栏 */}
                      <div className="flex items-center justify-between px-4 py-3 border-t border-border/50">
                        {/* 左侧按钮 */}
                        <div className="flex items-center gap-1">
                          <Popover open={homePopoverOpen} onOpenChange={setHomePopoverOpen}>
                            <PopoverTrigger asChild>
                              <button className="p-2 hover:bg-muted rounded-lg transition-colors">
                                <Paperclip className="h-5 w-5 text-muted-foreground" />
                              </button>
                            </PopoverTrigger>
                            <PopoverContent className="w-48 p-0" align="start">
                              <div className="flex flex-col">
                                <button
                                  onClick={() => setShowKbSelector(true)}
                                  className="flex items-center gap-2 px-4 py-2 hover:bg-muted text-sm text-left transition-colors"
                                >
                                  <Database className="h-4 w-4" />
                                  <span>云知识库选择</span>
                                </button>
                                <button
                                  onClick={() => fileInputRef.current?.click()}
                                  className="flex items-center gap-2 px-4 py-2 hover:bg-muted text-sm text-left transition-colors"
                                >
                                  <Paperclip className="h-4 w-4" />
                                  <span>本地文件选择</span>
                                </button>
                              </div>
                            </PopoverContent>
                          </Popover>

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
            <div className="h-full flex flex-col">
              <div className="h-[58px] shrink-0" />
              <ScrollArea className="flex-1 chat-surface">
                <div className="max-w-4xl mx-auto px-6 pt-0 pb-8">
                  {messages.map((message, index) => {
                  const isFirstAiMessage =
                    message.role === "assistant" &&
                    (index === 0 || messages[index - 1]?.role !== "assistant");
                  const isFirstUserMessage =
                    message.role === "user" &&
                    (index === 0 || messages[index - 1]?.role !== "user");

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
                      isFirstUserMessage={isFirstUserMessage}
                      onSetSearchRound={setCurrentSearchRound}
                      onSetImageSearchRound={setCurrentImageSearchRound}
                      onScrollToSlide={handleScrollToSlide}
                      showThinking={deepThinkingMode}
                      isLoading={isLoading}
                    />
                  );
                })}

                {isLoading && messages.length > 0 && messages[messages.length - 1]?.role === "user" && (() => {
                  const hasAssistant = messages.some(m => m.role === "assistant");
                  return (
                    <div className="mb-6">
                      {!hasAssistant ? (
                        // 首次 AI 过渡提示
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-1 -ml-2 min-h-12">
                            <div className="w-12 h-12 flex items-center justify-center shrink-0">
                              <AIAvatar isActive offsetX={AI_AVATAR_OFFSET_X} />
                            </div>
                            <span className="text-base font-medium text-foreground leading-none">SlideAgent</span>
                          </div>
                          <div className="pl-8">
                            <div className="text-base text-foreground leading-relaxed whitespace-pre-wrap">
                              <span>让我先核对下本轮任务的目标和重点偏好，正在梳理您的需求~</span>
                              <span className="inline-flex items-center ml-2 align-middle">
                                <span className="w-2 h-2 rounded-full bg-primary animate-pulse align-middle" />
                              </span>
                            </div>
                          </div>
                        </div>
                      ) : (
                        // 后续响应：使用加载动画
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
            </div>
          )}
        </div>

        {/* 输入框 - 只在聊天模式下显示 - 智谱清言风格 */}
        {mode === "chat" && (
          <div className="p-4 shrink-0">
            <div className="max-w-4xl mx-auto">
              <div className="relative rounded-2xl border border-border bg-muted/50">
                {/* 附件预览 */}
                {activeAttachments.length > 0 && (
                  <div className="flex flex-wrap gap-2 px-4 pt-3">
                    {activeAttachments.map(file => (
                      <div key={file.id} className="flex items-center gap-1 bg-background px-2 py-1 rounded-md text-sm border border-border">
                        <span className="truncate max-w-[150px]">{file.filename}</span>
                        <button
                          onClick={() => setActiveAttachments(prev => prev.filter(f => f.id !== file.id))}
                          className="hover:text-destructive transition-colors"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <textarea
                  ref={inputRef}
                  value={inputValue}
                  onChange={e => setInputValue(e.target.value)}
                  onCompositionStart={chatComposition.onCompositionStart}
                  onCompositionEnd={chatComposition.onCompositionEnd}
                  onKeyDown={chatComposition.onKeyDown}
                  placeholder="想调整内容、样式或风格等吗，直接告诉我吧"
                  className="w-full px-4 py-4 pr-32 bg-transparent resize-none focus:outline-none min-h-[56px] max-h-[200px] text-sm"
                  rows={1}
                />

                <div className="absolute right-3 bottom-2 flex items-center gap-2">
                  <Popover open={chatPopoverOpen} onOpenChange={setChatPopoverOpen}>
                    <PopoverTrigger asChild>
                      <button className="p-1.5 hover:bg-muted/80 rounded-lg transition-colors">
                        <Paperclip className="h-4 w-4 text-muted-foreground" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-48 p-0" align="start">
                      <div className="flex flex-col">
                        <button
                          onClick={() => setShowKbSelector(true)}
                          className="flex items-center gap-2 px-4 py-2 hover:bg-muted text-sm text-left transition-colors"
                        >
                          <Database className="h-4 w-4" />
                          <span>云知识库选择</span>
                        </button>
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          className="flex items-center gap-2 px-4 py-2 hover:bg-muted text-sm text-left transition-colors"
                        >
                          <Paperclip className="h-4 w-4" />
                          <span>本地文件选择</span>
                        </button>
                      </div>
                    </PopoverContent>
                  </Popover>


                  {/* 发送或暂停按钮 - 圆形设计 */}
                  {isLoading ? (
                    <button
                      onClick={async () => {
                        // 调用暂停 API
                        if (currentSessionId) {
                          try {
                            await fetch(`/api/sessions/${currentSessionId}/pause`, {
                              method: "POST",
                            });
                            // 中止当前请求
                            if (abortControllerRef.current) {
                              abortControllerRef.current.abort();
                            }
                            setIsLoading(false);
                            // 更新对话状态
                            if (currentConversationId) {
                              setConversations(prev =>
                                prev.map(c =>
                                  c.id === currentConversationId ? { ...c, task_status: "paused" as const } : c
                                )
                              );
                            }
                          } catch (e) {
                            console.error("Pause failed:", e);
                          }
                        }
                      }}
                      className="w-8 h-8 rounded-full flex items-center justify-center transition-colors bg-orange-500 text-white hover:bg-orange-600"
                      title="暂停任务"
                    >
                      <Pause className="h-4 w-4" />
                    </button>
                  ) : (
                    <button
                      onClick={handleSendMessage}
                      disabled={!inputValue.trim()}
                      className={cn(
                        "w-8 h-8 rounded-full flex items-center justify-center transition-colors",
                        inputValue.trim()
                          ? "bg-primary text-white hover:bg-primary/90"
                          : "bg-muted text-muted-foreground"
                      )}
                    >
                      <Send className="h-4 w-4" />
                    </button>
                  )}
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
        isLoading={isLoading}
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
          imageSearchRounds={imageSearchRounds}
          currentImageSearchRound={currentImageSearchRound}
          setCurrentImageSearchRound={setCurrentImageSearchRound}
          pptOutline={pptOutline}
          pptOutlineStreaming={pptOutlineStreaming}
          pptProjects={pptProjects}
        onSelectProject={handleSelectProject}
        onDownload={handleDownload}
        onShare={handleShare}
        onPlay={handlePlay}
        onFullscreen={handleFullscreen}
        onSaveSlide={handleSaveSlide}
      />

      {/* 下载弹窗 */}
      {
        pptProject && (
          <DownloadModal
            isOpen={showDownloadModal}
            onClose={() => setShowDownloadModal(false)}
            projectId={pptProject.id}
            versionId={pptProject.current_version?.id}
            title={pptProject.title}
          />
        )
      }

      {/* 分享弹窗 */}
      {
        pptProject && (
          <ShareModal
            isOpen={showShareModal}
            onClose={() => setShowShareModal(false)}
            projectId={pptProject.id}
            versionId={pptProject.current_version?.id}
            title={pptProject.title}
          />
        )
      }

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

      {/* 知识库选择器 */}
      <KnowledgeBaseSelector
        open={showKbSelector}
        onOpenChange={setShowKbSelector}
        onSelect={handleKbSelect}
      />
      <input
        type="file"
        ref={fileInputRef}
        className="hidden"
        onChange={handleFileSelect}
      />
    </div >
  );
}

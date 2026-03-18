/**
 * PPTAgent 主页面（重构版）
 * 逻辑拆分到 hooks/，UI 拆分到 components/
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useLocation } from "wouter";
import { toast } from "sonner";
import { Loader2, X, MessageSquarePlus, FolderOpen } from "lucide-react";
import { useComposition } from "@/hooks/useComposition";
import { useConversationManager } from "@/hooks/useConversationManager";
import { useStreamHandler } from "@/hooks/useStreamHandler";
import { useRightPanel } from "@/hooks/useRightPanel";
import { useDownloadProgress } from "@/hooks/useDownloadProgress";

// 组件
import ConversationSidebar from "@/components/ConversationSidebar";
import RightPanel from "@/components/RightPanel";
import DownloadModal from "@/components/DownloadModal";
import ShareModal from "@/components/ShareModal";
import TaskFilesModal from "@/components/TaskFilesModal";
import HomeScreen from "@/components/HomeScreen";
import ChatArea from "@/components/ChatArea";
import { KnowledgeBaseSelector } from "@/components/KnowledgeBaseSelector";

// 类型
import type {
  Message,
  TaskPlan,
  SearchRound,
  ImageSearchRound,
  PPTProject,
  Conversation,
  TemplateCategory,
  Template,
} from "@/types";

// API
import { uploadFile, parseUploadedFile, type UploadResponse, type DocumentResponse } from "@/lib/api";

const pickGreeting = () => {
  const now = new Date();
  const hour = now.getHours();
  const dayOfWeek = now.getDay(); // 0=周日, 6=周六
  
  // 判断时段
  const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
  
  let segment: string;
  if (isWeekend) {
    segment = "weekend";
  } else if (hour >= 5 && hour < 11) {
    segment = "morning";
  } else if (hour >= 11 && hour < 14) {
    segment = "noon";
  } else if (hour >= 14 && hour < 18) {
    segment = "afternoon";
  } else if (hour >= 18 && hour < 24) {
    segment = "evening";
  } else {
    segment = "late_night"; // 0-5点
  }

  const sets: Record<string, string[]> = {
    morning: [
      "早上好，今天想做哪类 PPT？",
      "早安！要不要来个清爽的开场？",
      "新的一天开始了，准备好做 PPT 吗？",
      "早上好！把你的想法交给我吧。",
      "晨光正好，今天想呈现什么内容？",
      "早！一杯咖啡的时间就能出大纲。",
      "新的一天，新的演示，主题是什么？",
      "早上好！让今天的 PPT 有个漂亮开头。"
    ],
    noon: [
      "中午好，来个高效的 PPT 规划？",
      "午间灵感时刻，想做什么主题？",
      "中午好！要不要快速出一版大纲？",
      "午安，给我一个方向就能开始。",
      "午休前搞定 PPT，下午轻松开会。",
      "午饭时间也能出精品，主题请讲。",
      "午间黄金半小时，快速出稿。",
      "中午好！吃饱了就来做点有营养的 PPT。"
    ],
    afternoon: [
      "下午好，继续推进你的 PPT 吧！",
      "下午好，来点更有冲击力的设计？",
      "午后时间最适合打磨 PPT 细节。",
      "下午好！告诉我主题，我来输出。",
      "下午茶时间，顺便把 PPT 也泡出来？",
      "下午效率高峰，趁热打铁做演示。",
      "三点几了，做 PPT 先啦！",
      "下午好！赶在下班前完美收工。"
    ],
    evening: [
      "晚上好，今晚也要高效产出 PPT。",
      "夜间灵感正好，来个漂亮的演示？",
      "晚上好！收尾也能很丝滑。",
      "夜深了，交给我快速生成吧。",
      "晚上是创意的温床，想做什么风格？",
      "夜猫子模式开启，PPT 交给我。",
      "今晚的灵感，变成明天的惊艳演示。",
      "晚上好！熬夜不如高效，马上开始。"
    ],
    late_night: [
      "这么晚还在准备 PPT？交给我，你早点休息。",
      "深夜加班模式，我来帮你速战速决。",
      "凌晨的 PPT 也能闪闪发光。",
      "夜已深，但好演示不分昼夜。",
      "深夜灵感往往最炸，说来听听？",
      "凌晨了，快速搞定去睡觉！",
      "深夜战士，PPT 交给我守护。",
      "这个点还在卷？我陪你快速收工。"
    ],
    weekend: [
      "周末也在忙 PPT？辛苦了，马上开工。",
      "周末好！工作与生活平衡，快速搞定它。",
      "休息日还来加班，必须让你早点收工。",
      "周末的 PPT，可以做得更有趣一点？",
      "周末灵感更松弛，做个漂亮的！",
      "周六/周日也在卷？我让你卷得轻松点。",
      "周末办公模式开启，效率不减。",
      "难得的周末，PPT 我来做，你去玩。"
    ]
  };

  const list = sets[segment] || sets.morning;
  return list[Math.floor(Math.random() * list.length)] || "嗨，今天有什么我可以帮你的吗？";
};

export default function Home() {
  const params = useParams<{ conversationId?: string }>();
  const [, setLocation] = useLocation();

  // ==================== 页面模式 ====================
  const [mode, setMode] = useState<"home" | "chat">("home");
  const [greeting, setGreeting] = useState(() => pickGreeting());
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<TemplateCategory>("全部");
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [isPptMode] = useState(true);

  // ==================== 聊天状态 ====================
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [activeAttachments, setActiveAttachments] = useState<UploadResponse[]>([]);
  const [homePopoverOpen, setHomePopoverOpen] = useState(false);
  const [chatPopoverOpen, setChatPopoverOpen] = useState(false);
  const [showKbSelector, setShowKbSelector] = useState(false);
  const [searchMode, setSearchMode] = useState<"auto" | "on" | "off">("auto");
  const isSearchDisabled = activeAttachments.length > 0;
  const hasPendingAttachmentProcessing = activeAttachments.some(
    (file) => file.upload_status === "uploading" || file.parse_status === "parsing"
  );

  // ==================== 对话/会话 ====================
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
  const [currentConversationUuid, setCurrentConversationUuid] = useState<string | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [currentTopic, setCurrentTopic] = useState("");

  // ==================== 工具调用 ====================
  const [pendingToolCallId, setPendingToolCallId] = useState<string>("");
  const [autoConfirmCountdown, setAutoConfirmCountdown] = useState<number | null>(null);
  const autoConfirmTimerRef = useRef<NodeJS.Timeout | null>(null);

  // ==================== 任务规划 ====================
  const [taskPlan, setTaskPlan] = useState<TaskPlan | null>(null);
  const [taskPlanStreaming, setTaskPlanStreaming] = useState(false);

  // ==================== 搜索状态 ====================
  const [searchRounds, setSearchRounds] = useState<SearchRound[]>([]);
  const [currentSearchRound, setCurrentSearchRound] = useState(1);
  const [deepThinking, setDeepThinking] = useState("");
  const [deepThinkingStreaming, setDeepThinkingStreaming] = useState(false);
  const [imageSearchRounds, setImageSearchRounds] = useState<ImageSearchRound[]>([]);
  const [currentImageSearchRound, setCurrentImageSearchRound] = useState(1);

  // ==================== PPT 状态 ====================
  const [pptOutline, setPptOutline] = useState("");
  const [pptOutlineStreaming, setPptOutlineStreaming] = useState(false);
  const [pptHtmlCode, setPptHtmlCode] = useState("");
  const [pptProject, setPptProject] = useState<PPTProject | null>(null);
  const [isEditMode, setIsEditMode] = useState(false);
  const [pptViewMode, setPptViewMode] = useState<"preview" | "code">("preview");
  // 手动编辑快照：key 为 parentVersionId，value 为编辑前的原始 HTML
  const [editSnapshots, setEditSnapshots] = useState<Record<number, string>>({});
  // 子版本 ID 映射：key 为 parentVersionId，value 为子版本 ID（用于下载原始版本）
  const [subVersionIds, setSubVersionIds] = useState<Record<number, number>>({});
  // 记录哪些版本当前显示的是"原始"状态（true=原始，false/undefined=修改）
  const [snapshotViewingOriginal, setSnapshotViewingOriginal] = useState<Record<number, boolean>>({});

  // ==================== 弹窗状态 ====================
  const [showDownloadModal, setShowDownloadModal] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [showTaskFilesModal, setShowTaskFilesModal] = useState(false);

  // ==================== Refs ====================
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isStreamingRef = useRef(false);
  const currentSessionIdRef = useRef<string | null>(null);
  const currentConversationIdRef = useRef<number | null>(null);
  const currentConversationUuidRef = useRef<string | null>(null);
  const lastCompletedSearchRoundRef = useRef(0);
  const pendingImagePanelRoundRef = useRef<number | null>(null);
  const pptProjectRef = useRef<PPTProject | null>(null);

  // Sync refs
  useEffect(() => { currentSessionIdRef.current = currentSessionId; }, [currentSessionId]);
  useEffect(() => { currentConversationIdRef.current = currentConversationId; }, [currentConversationId]);
  useEffect(() => { currentConversationUuidRef.current = currentConversationUuid; }, [currentConversationUuid]);
  useEffect(() => { pptProjectRef.current = pptProject; }, [pptProject]);

  useEffect(() => {
    if (isSearchDisabled && searchMode !== "off") setSearchMode("off");
  }, [isSearchDisabled, searchMode]);

  // 自动滚动
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // ==================== Hooks ====================
  const {
    conversations, setConversations,
    pptProjects, setPptProjects,
    loadConversations, loadPPTProjects,
    loadConversationDetail, refreshPPTProject: refreshProject,
    deleteConv, renameConv, pinConv, markConversationRunning,
  } = useConversationManager();

  const {
    showRightPanel, setShowRightPanel,
    rightPanelType, setRightPanelType,
    targetSlideIndex,
    openRightPanelDeferred, openRightPanel,
    handleScrollToSlide,
  } = useRightPanel();

  const { downloadProgress, setDownloadProgress, handleDownloadProgress } = useDownloadProgress();

  // 仅在 PPT 预览面板且预览视图中允许编辑态；切到其他面板/代码视图时自动退出编辑
  useEffect(() => {
    if (
      isEditMode &&
      (!showRightPanel || rightPanelType !== "ppt_preview" || pptViewMode !== "preview")
    ) {
      setIsEditMode(false);
    }
  }, [isEditMode, showRightPanel, rightPanelType, pptViewMode]);

  // refreshPPTProject wrapper that updates local state
  const refreshPPTProject = useCallback(async (id: number, opts?: { preserveHtml?: boolean }) => {
    const result = await refreshProject(id, opts, opts?.preserveHtml ? pptHtmlCode : undefined);
    if (result) {
      setPptProject(result.project);
      if (result.htmlCode) setPptHtmlCode(result.htmlCode);
      // Populate editSnapshots from backend sub-versions (survives container restart)
      if (result.subVersionMap && Object.keys(result.subVersionMap).length > 0) {
        setEditSnapshots(prev => {
          const next = { ...prev };
          for (const [parentIdStr, subVersion] of Object.entries(result.subVersionMap)) {
            const parentId = Number(parentIdStr);
            if (!next[parentId] && subVersion.slides && subVersion.slides.length > 0) {
              const html = subVersion.slides
                .slice()
                .sort((a: any, b: any) => a.page_number - b.page_number)
                .map((s: any) => s.html_content)
                .join("\n");
              next[parentId] = html;
            }
          }
          return next;
        });
        setSubVersionIds(prev => {
          const next = { ...prev };
          for (const [parentIdStr, subVersion] of Object.entries(result.subVersionMap)) {
            const parentId = Number(parentIdStr);
            if (!next[parentId]) next[parentId] = subVersion.id;
          }
          return next;
        });
      }
    }
  }, [refreshProject, pptHtmlCode]);

  const startAutoConfirmCountdown = useCallback((toolCallId: string) => {
    setAutoConfirmCountdown(30);
    if (autoConfirmTimerRef.current) clearInterval(autoConfirmTimerRef.current);
    autoConfirmTimerRef.current = setInterval(() => {
      setAutoConfirmCountdown(prev => {
        if (prev === null || prev <= 0) {
          clearInterval(autoConfirmTimerRef.current!);
          handleConfirmInfo(toolCallId, {});
          return null;
        }
        return prev - 1;
      });
    }, 1000);
  }, []);

  const cancelAutoConfirm = useCallback(() => {
    if (autoConfirmTimerRef.current) clearInterval(autoConfirmTimerRef.current);
    setAutoConfirmCountdown(null);
  }, []);

  const { handleStreamEvent, shouldRenderStreamForCurrentConversation } = useStreamHandler({
    isStreamingRef, currentConversationUuidRef,
    lastCompletedSearchRoundRef, pendingImagePanelRoundRef,
    setMessages, setIsLoading, setIsConfirming,
    setCurrentConversationId, setCurrentConversationUuid,
    setTaskPlan, setTaskPlanStreaming,
    setSearchRounds, setCurrentSearchRound,
    setDeepThinking, setDeepThinkingStreaming,
    setImageSearchRounds, setCurrentImageSearchRound,
    setPptOutline, setPptOutlineStreaming,
    setPptHtmlCode, setPptProject, setPptProjects,
    setCurrentTopic, setPendingToolCallId,
    openRightPanelDeferred, loadConversations, loadPPTProjects,
    refreshPPTProject,
    startAutoConfirmCountdown,
    isConfirming, deepThinking, currentSearchRound,
    pptProjectRef,
  });

  // ==================== IME ====================
  const homeComposition = useComposition<HTMLTextAreaElement>({
    onKeyDown: (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } }
  });
  const chatComposition = useComposition<HTMLTextAreaElement>({
    onKeyDown: (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } }
  });

  // ==================== 初始化 ====================
  useEffect(() => {
    const loadData = async () => {
      try { await loadConversations(); } catch {}
      try { await loadPPTProjects(); } catch {}
      if (params.conversationId) {
        try { await loadConversation(params.conversationId); } catch (e) { console.error(e); }
      }
    };
    loadData();
  }, [params.conversationId]);

  // 轮询（切换对话后恢复场景）
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isLoading && !isStreamingRef.current && currentConversationUuid) {
      interval = setInterval(() => {
        if (!isStreamingRef.current) loadConversation(currentConversationUuid);
      }, 3000);
    }
    return () => { if (interval) clearInterval(interval); };
  }, [isLoading, currentConversationUuid]);

  // ==================== 对话操作 ====================
  const loadConversation = async (uuid: string) => {
    try {
      const result = await loadConversationDetail(uuid);
      const resolvedConversationId = result.conversationId ?? ((result.pptProject as any)?.conversation_id ?? null);
      setCurrentConversationId(resolvedConversationId);
      setCurrentConversationUuid(uuid);
      if (result.sessionId) setCurrentSessionId(result.sessionId);
      if (result.searchMode) setSearchMode(result.searchMode);
      setIsLoading(result.taskStatus === "running");
      if (result.taskStatus === "running") setIsEditMode(false);

      setTaskPlan(null); setTaskPlanStreaming(false);
      setSearchRounds([]); setCurrentSearchRound(1);
      setDeepThinking(""); setDeepThinkingStreaming(false);
      setImageSearchRounds([]); setCurrentImageSearchRound(1);
      setPptOutline(""); setPptOutlineStreaming(false);
      if (!isStreamingRef.current) { setPptProject(null); setPptHtmlCode(""); }

      if (result.pptProject) {
        setPptProject(result.pptProject);
        if (result.pptHtmlCode) setPptHtmlCode(result.pptHtmlCode);
        setCurrentTopic(result.topic);
        // Load sub-versions from backend to restore editSnapshots after page refresh
        if (result.pptProject.id) {
          refreshPPTProject(result.pptProject.id, { preserveHtml: true });
        }
      } else {
        if (!isStreamingRef.current) { setPptProject(null); setPptHtmlCode(""); }
        setCurrentTopic(result.topic);
      }

      if (result.pptProjects.length > 0) setPptProjects(result.pptProjects);

      await new Promise<void>(r => typeof requestAnimationFrame === "function" ? requestAnimationFrame(() => r()) : setTimeout(r, 0));

      if (!isStreamingRef.current) setMessages(result.restoredMessages);
      if (result.taskPlan) setTaskPlan(result.taskPlan);
      if (result.searchRounds.length > 0) {
        setSearchRounds(result.searchRounds);
        setCurrentSearchRound(result.searchRounds[result.searchRounds.length - 1].round);
      }
      if (result.imageSearchRounds.length > 0) {
        setImageSearchRounds(result.imageSearchRounds);
        setCurrentImageSearchRound(result.imageSearchRounds[result.imageSearchRounds.length - 1].round);
      }
      if (result.pptOutline) setPptOutline(result.pptOutline);

      if (result.nextPanelType) {
        setRightPanelType(result.nextPanelType);
        setShowRightPanel(true);
      } else {
        setRightPanelType(null);
        setShowRightPanel(false);
      }
      setMode("chat");
    } catch (error) {
      console.error("Failed to load conversation:", error);
    }
  };

  const stopActiveStream = () => {
    if (abortControllerRef.current) { abortControllerRef.current.abort(); abortControllerRef.current = null; }
    isStreamingRef.current = false;
    setIsLoading(false);
    setIsConfirming(false);
  };

  const handleNewChat = () => {
    stopActiveStream();
    setCurrentConversationId(null); setCurrentConversationUuid(null);
    setCurrentSessionId(null); currentSessionIdRef.current = null;
    setMessages([]); setInputValue(""); setIsLoading(false); setCurrentTopic("");
    setTaskPlan(null); setTaskPlanStreaming(false);
    setSearchRounds([]); setCurrentSearchRound(1);
    setDeepThinking(""); setDeepThinkingStreaming(false);
    setImageSearchRounds([]); setCurrentImageSearchRound(1);
    setPptOutline(""); setPptOutlineStreaming(false);
    setPptHtmlCode(""); setPptProject(null);
    setShowRightPanel(false); setRightPanelType(null);
    setAutoConfirmCountdown(null); setSearchMode("auto");
    if (autoConfirmTimerRef.current) clearInterval(autoConfirmTimerRef.current);
    setGreeting(pickGreeting());
    setMode("home");
    setLocation("/chat");
  };

  const handleSelectConversation = (conversation: Conversation) => {
    isStreamingRef.current = false;
    setIsConfirming(false);
    setCurrentConversationId(conversation.id);
    setCurrentConversationUuid(conversation.uuid);
    loadConversation(conversation.uuid);
    setLocation(`/chat/${conversation.uuid}`);
  };

  const handleDeleteConversation = async (id: number) => {
    const ok = await deleteConv(id);
    if (ok && currentConversationId === id) handleNewChat();
  };

  // ==================== 发送消息 ====================
  const handleSendMessage = async () => {
    if (hasPendingAttachmentProcessing) {
      toast.info("文件还在上传或解析中，稍等一下再发送");
      return;
    }
    if ((!inputValue.trim() && !selectedTemplate && activeAttachments.length === 0) || isLoading) return;

    const currentTemplate = selectedTemplate;
    const messageContent = inputValue.trim() || (currentTemplate ? "请基于已选择的模板生成 PPT" : "请根据上传的附件制作 PPT");

    const userMessage: Message = {
      id: `user-${Date.now()}`, role: "user", content: messageContent, timestamp: Date.now(),
      template: currentTemplate ? {
        id: currentTemplate.id,
        title: currentTemplate.title,
        subtitle: currentTemplate.subtitle,
      } : undefined,
      attachments: activeAttachments.map(att => ({ id: att.id, filename: att.filename, file_path: att.file_path, file_size: att.size, content_type: att.content_type })),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue("");
    setSelectedTemplate(null);
    const currentAttachments = activeAttachments;
    setActiveAttachments([]);
    setIsLoading(true);
    if (currentConversationId) markConversationRunning(currentConversationId);
    if (!currentConversationId) setCurrentTopic(userMessage.content);
    setMode("chat");

    let streamConversationUuid = currentConversationId ? currentConversationUuidRef.current : null;
    abortControllerRef.current = new AbortController();

    setIsEditMode(false);
    isStreamingRef.current = true;
    setCurrentSessionId(null);
    currentSessionIdRef.current = null;

    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instruction: messageContent,
        session_id: undefined,
        conversation_id: currentConversationId,
        attachments: currentAttachments.length > 0 ? currentAttachments : undefined,
        template: currentTemplate?.title,
        search_mode: searchMode,
      }),
      signal: abortControllerRef.current.signal,
    });

    try {
      if (!response.ok) throw new Error("Chat request failed");
      const sessionId = response.headers.get("X-Session-Id");
      if (sessionId && shouldRenderStreamForCurrentConversation(streamConversationUuid)) setCurrentSessionId(sessionId);

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
              if (data.type === "conversation_created" && data.conversation_uuid && !streamConversationUuid) {
                streamConversationUuid = data.conversation_uuid;
                setCurrentConversationUuid(data.conversation_uuid);
                setLocation(`/chat/${data.conversation_uuid}`);
              }
              handleStreamEvent(data, streamConversationUuid);
            } catch (e) { console.error("Failed to parse SSE data:", e); }
          }
        }
      }
    } catch (error: any) {
      if (error.name !== "AbortError") {
        console.error("Chat error:", error);
        if (shouldRenderStreamForCurrentConversation(streamConversationUuid)) {
          setMessages(prev => [...prev, { id: `error-${Date.now()}`, role: "assistant", content: "抱歉，发生了错误，请稍后重试。", timestamp: Date.now() }]);
        }
      }
    } finally {
      if (shouldRenderStreamForCurrentConversation(streamConversationUuid)) {
        setIsLoading(false);
        isStreamingRef.current = false;
      }
      loadConversations();
    }
  };

  // ==================== 确认补充信息 ====================
  const handleConfirmInfo = async (toolCallId: string, selectedData: Record<string, unknown>) => {
    cancelAutoConfirm();
    const targetId = String(toolCallId);
    setMessages(prev => prev.map(msg => ({
      ...msg,
      toolCalls: msg.toolCalls?.map(tc => String(tc.id) === targetId ? { ...tc, status: "confirmed" as const } : tc),
    })));
    setIsConfirming(true);
    setIsLoading(true);
    setIsEditMode(false);
    isStreamingRef.current = true;
    const streamConversationUuid = currentConversationUuidRef.current;
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch("/api/ppt/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: currentSessionIdRef.current, conversation_id: currentConversationIdRef.current, supplement_data: selectedData, search_mode: searchMode }),
        signal: abortControllerRef.current.signal,
      });
      if (!response.ok) throw new Error("Confirm request failed");
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
              try { handleStreamEvent(JSON.parse(line.slice(6)), streamConversationUuid); } catch {}
            }
          }
        }
      }
    } catch (error) {
      console.error("Confirm error:", error);
      if (shouldRenderStreamForCurrentConversation(streamConversationUuid)) {
        setIsLoading(false);
        isStreamingRef.current = false;
      }
    } finally {
      setIsConfirming(false);
    }
  };

  // ==================== PPT 操作 ====================
  const handleEnterEditMode = async () => {
    const slides = (pptProject as any)?.slides;
    const hasRealSlides = slides && slides.length > 0 && slides[0].id > 0;
    if (!hasRealSlides && pptProject?.id) await refreshPPTProject(pptProject.id, { preserveHtml: true });
    // 进入编辑模式时，保存当前版本的原始 HTML 快照（仅首次）
    const versionId = pptProject?.current_version?.id;
    if (versionId && !editSnapshots[versionId]) {
      setEditSnapshots(prev => ({ ...prev, [versionId]: pptHtmlCode }));
    }
    setIsEditMode(true);
  };

  const handleSaveSlide = async (slideId: number, htmlContent: string) => {
    try {
      if (slideId > 0) {
        const { updateSlide } = await import("@/lib/api");
        const versionId = pptProject?.current_version?.id;
        await updateSlide(slideId, htmlContent, undefined, versionId);
      }
      setPptProject(prev => {
        if (!prev) return prev;
        const slides = (prev as any).slides;
        if (!slides) return prev;
        const updatedSlides = slides.map((slide: any) =>
          slide.id === slideId ? { ...slide, html_content: htmlContent, updated_at: new Date().toISOString() } : slide
        );
        const htmlCode = updatedSlides.sort((a: any, b: any) => a.page_number - b.page_number).map((s: any) => s.html_content).join("\n");
        setPptHtmlCode(htmlCode);
        return { ...prev, slides: updatedSlides } as any;
      });
      // 如果在"原始"视图下编辑保存，自动切换到"修改"视图
      const versionId = pptProject?.current_version?.id;
      if (versionId && snapshotViewingOriginal[versionId]) {
        setSnapshotViewingOriginal(prev => ({ ...prev, [versionId]: false }));
      }
    } catch (error) {
      console.error("Failed to save slide:", error);
      throw error;
    }
  };

  const handleSelectProject = (project: PPTProject) => {
    setPptProject(project);
    if (project.versions && project.versions.length > 0) {
      const latestVersion = project.versions[project.versions.length - 1];
      if (latestVersion.slides) {
        setPptHtmlCode(latestVersion.slides.sort((a: any, b: any) => a.page_number - b.page_number).map((s: any) => s.html_content).join("\n"));
      }
    }
    setCurrentTopic(project.title);
    setRightPanelType("ppt_preview");
  };

  const handleSelectVersion = (project: PPTProject, versionId: number) => {
    const version = project.versions?.find(v => v.id === versionId);
    if (!version) return;
    const slides = version.slides || [];
    const htmlCode = slides
      .sort((a: any, b: any) => a.page_number - b.page_number)
      .map((s: any) => s.html_content)
      .join("\n");
    setPptProject({ ...project, current_version: version, slides });
    setPptHtmlCode(htmlCode);
    setIsEditMode(false);
    setRightPanelType("ppt_preview");
  };

  const handlePause = async () => {
    if (!currentSessionId) {
      toast.error("当前任务缺少会话ID，无法暂停");
      return;
    }
    try {
      const response = await fetch(`/api/sessions/${currentSessionId}/pause`, { method: "POST" });
      if (!response.ok) {
        let detail = `HTTP ${response.status}`;
        try {
          const data = await response.json();
          detail = data?.detail || detail;
        } catch {
          // ignore json parse errors
        }
        throw new Error(detail);
      }
      if (abortControllerRef.current) abortControllerRef.current.abort();
      setIsLoading(false);
      if (currentConversationId) {
        setConversations(prev => prev.map(c => c.id === currentConversationId ? { ...c, task_status: "paused" as const } : c));
      }
      toast.success("任务已暂停");
    } catch (e: any) {
      console.error("Pause failed:", e);
      toast.error(`暂停失败：${e?.message || "未知错误"}`);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);

      for (const file of files) {
        const localId = `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

        setActiveAttachments(prev => [
          ...prev,
          {
            id: localId,
            filename: file.name,
            file_path: "",
            content_type: file.type || "application/octet-stream",
            size: file.size,
            uploadProgress: 0,
            upload_status: "uploading",
            parse_status: "pending",
            parse_message: "文件上传中",
          },
        ]);

        try {
          const uploaded = await uploadFile(file, (progress) => {
            setActiveAttachments(prev => prev.map(item =>
              item.id === localId
                ? {
                    ...item,
                    uploadProgress: progress,
                    upload_status: "uploading",
                    parse_message: progress >= 100 ? "上传完成，准备解析" : "文件上传中",
                  }
                : item
            ));
          });

          setActiveAttachments(prev => prev.map(item =>
            item.id === localId
              ? {
                  ...item,
                  ...uploaded,
                  uploadProgress: 100,
                  upload_status: "uploaded",
                  parse_status: "parsing",
                  parse_message: "文件解析中",
                }
              : item
          ));

          const parsed = await parseUploadedFile(uploaded.file_path, uploaded.filename);

          setActiveAttachments(prev => prev.map(item =>
            item.id === localId || item.id === uploaded.id
              ? {
                  ...item,
                  ...uploaded,
                  uploadProgress: 100,
                  upload_status: "uploaded",
                  ...parsed,
                }
              : item
          ));

          if (parsed.parse_status === "completed") {
            toast.success(`已完成上传和解析：${file.name}`);
          } else if (parsed.parse_status === "unsupported") {
            toast.success(`已上传：${file.name}`);
          } else {
            toast.error(`解析失败：${file.name}`);
          }
        } catch {
          setActiveAttachments(prev => prev.filter(item => item.id !== localId));
          toast.error(`文件处理失败：${file.name}`);
        }
      }

      setHomePopoverOpen(false);
      setChatPopoverOpen(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleKbSelect = (docs: DocumentResponse[]) => {
    const newAttachments: UploadResponse[] = docs.map(doc => ({
      id: String(doc.id), filename: doc.display_name || doc.filename, file_path: "",
      content_type: doc.file_type, size: doc.file_size, knowledge_document_id: doc.id,
      upload_status: "uploaded",
      parse_status: doc.parse_status as UploadResponse["parse_status"],
      parse_message: doc.parse_status === "completed" ? "知识库文件已解析完成" : "知识库文件解析中",
    }));
    setActiveAttachments(prev => [...prev, ...newAttachments]);
    setShowKbSelector(false); setHomePopoverOpen(false); setChatPopoverOpen(false);
    toast.success(`已添加 ${docs.length} 个知识库文件`);
  };

  // ==================== 渲染 ====================
  return (
    <div className="h-screen flex bg-background">
      <ConversationSidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={handleDeleteConversation}
        onRenameConversation={renameConv}
        onPinConversation={pinConv}
        onNewChat={handleNewChat}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* 中间区域 */}
      <div className="flex-1 flex flex-col min-w-0 relative chat-surface">
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

        {mode === "chat" && downloadProgress && (() => {
          const percent = Math.round(downloadProgress.percent);
          const label = downloadProgress.label || "PPT";
          const message = downloadProgress.status === "running"
            ? `正在导出${label}文件，耗时可能较长，文件合成 ${percent}%...`
            : downloadProgress.status === "error" ? (downloadProgress.label || "导出失败") : "下载完成";
          return (
            <div className="absolute top-13 left-full -translate-x-1/2 z-50 pointer-events-none">
              <div className="pointer-events-auto flex items-center gap-2 rounded-full border px-3 py-2 shadow-md bg-slate-900 text-white border-slate-700/60 max-w-[460px]">
                {downloadProgress.status === "running" && <Loader2 className="h-3 w-3 animate-spin opacity-90" />}
                <div className="text-xs leading-tight truncate text-white/90 max-w-[380px]">{message}</div>
                <button onClick={() => setDownloadProgress(null)} className="text-white/70 hover:text-white transition-colors" aria-label="关闭">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          );
        })()}

        <div className="flex-1 overflow-hidden">
          {mode === "home" ? (
            <HomeScreen
              greeting={greeting}
              inputValue={inputValue}
              setInputValue={setInputValue}
              inputRef={inputRef}
              activeAttachments={activeAttachments}
              setActiveAttachments={setActiveAttachments}
              isLoading={isLoading}
              hasPendingAttachmentProcessing={hasPendingAttachmentProcessing}
              searchMode={searchMode}
              setSearchMode={setSearchMode}
              isSearchDisabled={isSearchDisabled}
              homePopoverOpen={homePopoverOpen}
              setHomePopoverOpen={setHomePopoverOpen}
              selectedCategory={selectedCategory}
              setSelectedCategory={setSelectedCategory}
              selectedTemplate={selectedTemplate}
              setSelectedTemplate={setSelectedTemplate}
              onSend={handleSendMessage}
              onOpenKbSelector={() => setShowKbSelector(true)}
              onOpenFileInput={() => fileInputRef.current?.click()}
              onCompositionStart={homeComposition.onCompositionStart}
              onCompositionEnd={homeComposition.onCompositionEnd}
              onKeyDown={homeComposition.onKeyDown}
            />
          ) : (
            <ChatArea
              messages={messages}
              isLoading={isLoading}
              isConfirming={isConfirming}
              inputValue={inputValue}
              setInputValue={setInputValue}
              inputRef={inputRef}
              messagesEndRef={messagesEndRef}
              activeAttachments={activeAttachments}
              setActiveAttachments={setActiveAttachments}
              hasPendingAttachmentProcessing={hasPendingAttachmentProcessing}
              searchMode={searchMode}
              setSearchMode={setSearchMode}
              isSearchDisabled={isSearchDisabled}
              chatPopoverOpen={chatPopoverOpen}
              setChatPopoverOpen={setChatPopoverOpen}
              currentTopic={currentTopic}
              autoConfirmCountdown={autoConfirmCountdown}
              currentSessionId={currentSessionId}
              currentConversationId={currentConversationId}
              onSend={handleSendMessage}
              onOpenPanel={openRightPanel}
              onConfirmInfo={handleConfirmInfo}
              onCancelAutoConfirm={cancelAutoConfirm}
              onSetSearchRound={setCurrentSearchRound}
              onSetImageSearchRound={setCurrentImageSearchRound}
              onScrollToSlide={handleScrollToSlide}
              onOpenKbSelector={() => setShowKbSelector(true)}
              onOpenFileInput={() => fileInputRef.current?.click()}
              onPause={handlePause}
              onCompositionStart={chatComposition.onCompositionStart}
              onCompositionEnd={chatComposition.onCompositionEnd}
              onKeyDown={chatComposition.onKeyDown}
              setConversations={setConversations}
            />
          )}
        </div>
      </div>

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
        setIsEditMode={(val) => val ? handleEnterEditMode() : setIsEditMode(false)}
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
        onSelectVersion={handleSelectVersion}
        editSnapshots={editSnapshots}
        subVersionIds={subVersionIds}
        snapshotViewingOriginal={snapshotViewingOriginal}
        onRestoreSnapshot={(versionId, viewOriginal) => {
          const snapshot = editSnapshots[versionId];
          if (!snapshot) return;
          if (viewOriginal) {
            setPptHtmlCode(snapshot);
            setIsEditMode(false);
            setSnapshotViewingOriginal(prev => ({ ...prev, [versionId]: true }));
          } else {
            setSnapshotViewingOriginal(prev => ({ ...prev, [versionId]: false }));
            // 从当前 pptProject slides 恢复修改版，不重新拉取（避免切换到最新版本）
            const slides = (pptProject as any)?.slides;
            if (slides && slides.length > 0) {
              const html = slides
                .slice()
                .sort((a: any, b: any) => a.page_number - b.page_number)
                .map((s: any) => s.html_content)
                .join("\n");
              setPptHtmlCode(html);
            }
          }
        }}
        onDownload={() => pptProject && setShowDownloadModal(true)}
        onShare={() => pptProject && setShowShareModal(true)}
        onPlay={() => pptProject && window.open(`/play/${pptProject.id}`, "_blank")}
        onFullscreen={() => {}}
        onDownloadProgress={handleDownloadProgress}
        onSaveSlide={handleSaveSlide}
      />

      {pptProject && (
        <DownloadModal
          isOpen={showDownloadModal}
          onClose={() => setShowDownloadModal(false)}
          projectId={pptProject.id}
          versionId={(() => {
            const cvId = pptProject.current_version?.id;
            if (cvId && snapshotViewingOriginal[cvId] && subVersionIds[cvId]) return subVersionIds[cvId];
            return cvId;
          })()}
          title={pptProject.title}
          onProgress={handleDownloadProgress}
        />
      )}

      {pptProject && (
        <ShareModal
          isOpen={showShareModal}
          onClose={() => setShowShareModal(false)}
          projectId={pptProject.id}
          versionId={pptProject.current_version?.id}
          viewMode={(() => {
            const cvId = pptProject.current_version?.id;
            if (!cvId) return "modified";
            return snapshotViewingOriginal[cvId] ? "original" : "modified";
          })()}
          title={pptProject.title}
        />
      )}

      <TaskFilesModal
        isOpen={showTaskFilesModal}
        onClose={() => setShowTaskFilesModal(false)}
        pptProject={pptProject}
        pptProjects={pptProjects}
        onSelectProject={(project) => {
          handleSelectProject(project);
          setShowRightPanel(true);
          setRightPanelType("ppt_preview");
        }}
        onSelectVersion={(project, versionId) => {
          handleSelectVersion(project, versionId);
          setShowRightPanel(true);
          setRightPanelType("ppt_preview");
        }}
      />

      <KnowledgeBaseSelector open={showKbSelector} onOpenChange={setShowKbSelector} onSelect={handleKbSelect} />
      <input type="file" ref={fileInputRef} className="hidden" multiple onChange={handleFileSelect} />
    </div>
  );
}

/**
 * 分享页面 - 查看分享的完整对话历史和 PPT
 *
 * 展示内容：
 * - 用户原始输入
 * - AI 思考和执行过程
 * - 工具调用（搜索、规划、PPT 生成）
 * - 最终生成的 PPT
 * 
 * 特点：
 * - 复用对话页面的 MessageItem、ToolCallCard 和 RightPanel 组件
 * - 只读模式，无左侧对话列表侧边栏
 * - 保留右侧工具面板（任务规划、搜索结果、PPT预览等）
 * - 自动展开所有工具调用内容
 */

import { useState, useEffect, useRef } from "react";
import { useParams } from "wouter";
import { Loader2, AlertCircle, Send, Globe, Paperclip } from "lucide-react";
import {
  getShareData,
  type ShareData,
  type ShareMessageData,
  type ShareToolCallData,
  type ShareSearchRoundData,
  type ShareTaskPlanData,
  type ShareSlideData,
} from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import MessageItem from "@/components/MessageItem";
import RightPanel from "@/components/RightPanel";
import type { Message, ToolCall, TaskPlan, SearchRound, ImageSearchRound, RightPanelType, PPTViewMode, PPTProject } from "@/types";

const normalizeToolType = (toolType: string): ToolCall["type"] => {
  if (toolType === "search" || toolType === "web_search") return "web_search";
  if (toolType === "task_plan") return "task_plan";
  if (toolType === "image_search") return "image_search";
  if (toolType === "supplement_info") return "supplement_info";
  if (toolType === "ppt_outline") return "ppt_outline";
  if (toolType === "ppt_generate") return "ppt_generate";
  if (toolType === "deep_thinking") return "deep_thinking";
  return "web_search";
};

const normalizeToolStatus = (status: string): ToolCall["status"] => {
  if (status === "pending") return "pending";
  if (status === "confirmed") return "confirmed";
  if (status === "auto_execute") return "auto_execute";
  if (status === "running") return "running";
  if (status === "completed") return "completed";
  if (status === "error") return "error";
  return "completed";
};

const normalizeTaskPlan = (plan: ShareTaskPlanData | undefined): TaskPlan | undefined => {
  if (!plan) return undefined;
  const rawSteps = Array.isArray(plan.steps) ? plan.steps : [];
  const steps = rawSteps.map((step, index) => {
    if (typeof step === "string") {
      return { id: index + 1, text: step };
    }
    if (step && typeof step === "object") {
      const value = step as Record<string, unknown>;
      const idValue = value.id;
      const textValue = value.text;
      return {
        id: typeof idValue === "number" ? idValue : index + 1,
        text: typeof textValue === "string" ? textValue : JSON.stringify(value),
      };
    }
    return { id: index + 1, text: String(step) };
  });

  return {
    streamContent: plan.plan_content || undefined,
    steps,
  };
};

const normalizeImageResults = (images: unknown): ImageSearchRound["images"] => {
  if (!Array.isArray(images)) return [];
  const normalized: ImageSearchRound["images"] = [];
  for (const image of images) {
    if (!image || typeof image !== "object") continue;
    const value = image as Record<string, unknown>;
    const url = typeof value.url === "string" ? value.url : "";
    if (!url) continue;
    normalized.push({
      url,
      description: typeof value.description === "string" ? value.description : undefined,
      width: typeof value.width === "number" ? value.width : undefined,
      height: typeof value.height === "number" ? value.height : undefined,
      local_path: typeof value.local_path === "string" ? value.local_path : undefined,
    });
  }
  return normalized;
};

export default function ShareView() {
  const { shareId } = useParams<{ shareId: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [shareData, setShareData] = useState<ShareData | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [fullMessages, setFullMessages] = useState<Message[]>([]);
  const [playbackEnabled, setPlaybackEnabled] = useState(true);
  const [playbackSpeed] = useState(3);
  
  // 右侧面板状态
  const [showRightPanel, setShowRightPanel] = useState(false);
  const [rightPanelType, setRightPanelType] = useState<RightPanelType>(null);
  
  // 任务规划状态
  const [taskPlan, setTaskPlan] = useState<TaskPlan | null>(null);
  
  // 搜索状态
  const [searchRounds, setSearchRounds] = useState<SearchRound[]>([]);
  const [currentSearchRound, setCurrentSearchRound] = useState(1);
  const [imageSearchRounds, setImageSearchRounds] = useState<ImageSearchRound[]>([]);
  const [currentImageSearchRound, setCurrentImageSearchRound] = useState(1);
  
  // PPT 状态
  const [pptOutline, setPptOutline] = useState("");
  const [pptHtmlCode, setPptHtmlCode] = useState("");
  const [pptViewMode, setPptViewMode] = useState<PPTViewMode>("preview");
  const [pptProject, setPptProject] = useState<PPTProject | null>(null);
  const [isEditMode, setIsEditMode] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const playbackCancelRef = useRef(false);

  useEffect(() => {
    if (!shareId) {
      setError("无效的分享链接");
      setLoading(false);
      return;
    }

    const loadShareData = async () => {
      try {
        const data = await getShareData(shareId);
        setShareData(data);
        
        // 转换消息格式为 MessageItem 组件所需的格式
        const convertedMessages: Message[] = data.messages.map((msg: ShareMessageData) => {
          const toolCalls: ToolCall[] = (msg.tool_calls || []).map((tc: ShareToolCallData) => {
            const normalizedToolType = normalizeToolType(tc.tool_type);
            // 构建工具调用数据
            const toolData: ToolCall["data"] = {
              ...(tc.arguments || {}),
              ...(tc.result || {}),
            };

            // 处理搜索轮次
            if (tc.search_rounds && tc.search_rounds.length > 0) {
              toolData.searchRounds = tc.search_rounds.map((sr: ShareSearchRoundData) => ({
                round: sr.round_number,
                query: sr.query,
                thinking: sr.thinking,
                results: (sr.results || []).map((r) => ({
                  title: r.title,
                  url: r.url,
                  snippet: r.snippet,
                })),
                isCompleted: true,
              }));
            }

            // 处理任务规划
            if (tc.task_plan) {
              toolData.taskPlan = normalizeTaskPlan(tc.task_plan);
            }

            return {
              id: tc.id.toString(),
              type: normalizedToolType,
              name: tc.tool_name,
              status: normalizeToolStatus(tc.status),
              data: toolData,
            };
          });

          const role: Message["role"] = msg.role === "user" ? "user" : "assistant";
          return {
            id: msg.id.toString(),
            role,
            content: msg.content,
            timestamp: new Date(msg.created_at).getTime(),
            toolCalls,
          };
        });

        setFullMessages(convertedMessages);
        
        // 提取任务规划、搜索轮次和PPT数据
        if (data.messages) {
          // 提取任务规划
          for (const msg of data.messages) {
            if (msg.tool_calls) {
              for (const tc of msg.tool_calls) {
                if (tc.tool_type === "task_plan" && tc.task_plan) {
                  setTaskPlan(normalizeTaskPlan(tc.task_plan) || null);
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
                      thinking: sr.thinking,
                      results: (sr.results || []).map((r) => ({
                        title: r.title,
                        url: r.url,
                        snippet: r.snippet,
                      })),
                      isCompleted: true,
                    });
                  }
                }
              }
            }
          }
          setSearchRounds(extractedRounds);
          
          // 提取图片搜索轮次
          const extractedImageRoundsMap = new Map<number, ImageSearchRound>();
          for (const msg of data.messages) {
            if (msg.tool_calls) {
              for (const tc of msg.tool_calls) {
                if (tc.tool_type === "image_search") {
                  const args = tc.arguments || {};
                  const result = tc.result || {};
                  const rawRound = args.round ?? result.round ?? 1;
                  const round = typeof rawRound === "number" ? rawRound : Number(rawRound) || 1;
                  const query = (typeof args.query === "string" ? args.query : undefined)
                    || (typeof result.query === "string" ? result.query : "")
                    || "";
                  const images = normalizeImageResults(result.images ?? args.images);
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

          // 提取PPT大纲
          for (const msg of data.messages) {
            if (msg.tool_calls) {
              for (const tc of msg.tool_calls) {
                const outline = tc.result?.outline;
                if (tc.tool_type === "ppt_outline" && typeof outline === "string" && outline) {
                  setPptOutline(outline);
                }
              }
            }
          }
        }
        
        // 处理PPT项目
        if (data.ppt_project) {
          const project = data.ppt_project;
          
          // 转换为前端PPTProject格式
          const createdAt = data.share_info.created_at || new Date().toISOString();
          const slides = project.slides || [];
          const convertedProject: PPTProject = {
            id: project.id,
            conversation_id: data.conversation.id,
            title: project.title,
            outline_content: project.outline_content || undefined,
            created_at: createdAt,
            updated_at: createdAt,
            versions: [{
              id: 1,
              version_number: 1,
              version_name: "V1",
              created_at: createdAt,
              slides: slides.map((slide: ShareSlideData) => ({
                id: slide.id,
                version_id: 1,
                page_number: slide.page_number,
                page_title: slide.page_title || undefined,
                html_content: slide.html_content,
                created_at: createdAt,
                updated_at: createdAt,
              })),
            }],
            current_version: {
              id: 1,
              version_number: 1,
              version_name: "V1",
              created_at: createdAt,
              slides: slides.map((slide: ShareSlideData) => ({
                id: slide.id,
                version_id: 1,
                page_number: slide.page_number,
                page_title: slide.page_title || undefined,
                html_content: slide.html_content,
                created_at: createdAt,
                updated_at: createdAt,
              })),
            },
          };
          
          setPptProject(convertedProject);
          
          // 生成HTML代码
          if (slides.length > 0) {
            const htmlCode = slides
              .sort((a: ShareSlideData, b: ShareSlideData) => a.page_number - b.page_number)
              .map((slide: ShareSlideData) => slide.html_content)
              .join("\n");
            setPptHtmlCode(htmlCode);
          }
          
          // 默认打开PPT预览面板
          setRightPanelType("ppt_preview");
          setShowRightPanel(true);
        }
      } catch (err) {
        setError("分享链接已失效或不存在");
      } finally {
        setLoading(false);
      }
    };

    loadShareData();
  }, [shareId]);

  useEffect(() => {
    if (fullMessages.length === 0) return;
    playbackCancelRef.current = false;

    const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
    const chunkSize = 12;
    const baseChunkDelay = 30;
    const baseUserDelay = 120;
    const baseMessageDelay = 140;

    const openPanelForToolCalls = (tools: ToolCall[]) => {
      if (!tools || tools.length === 0) return;

      const hasTaskPlan = tools.some((tool) => tool.type === "task_plan");
      const hasWebSearch = tools.some((tool) => tool.type === "web_search");
      const hasImageSearch = tools.some((tool) => tool.type === "image_search");
      const hasPptOutline = tools.some((tool) => tool.type === "ppt_outline");
      const hasPptGenerate = tools.some((tool) => tool.type === "ppt_generate");

      if (hasTaskPlan) {
        setRightPanelType("task_plan");
      } else if (hasWebSearch) {
        setRightPanelType("web_search");
        const webSearchTool = tools.find((tool) => tool.type === "web_search");
        const rounds = webSearchTool?.data?.searchRounds;
        const round = rounds && rounds.length > 0 ? rounds[rounds.length - 1]?.round : undefined;
        if (typeof round === "number") {
          setCurrentSearchRound(round);
        }
      } else if (hasImageSearch) {
        setRightPanelType("image_search");
        const imageRound = tools.find((tool) => tool.type === "image_search")?.data?.round;
        if (typeof imageRound === "number") {
          setCurrentImageSearchRound(imageRound);
        }
      } else if (hasPptOutline) {
        setRightPanelType("ppt_outline");
      } else if (hasPptGenerate) {
        setRightPanelType("ppt_preview");
      }

      setShowRightPanel(true);
    };

    const play = async () => {
      if (!playbackEnabled) {
        setMessages(fullMessages);
        return;
      }

      setMessages([]);

      for (const msg of fullMessages) {
        if (playbackCancelRef.current) return;

        if (msg.role === "user") {
          setMessages(prev => [...prev, msg]);
          await sleep(Math.max(40, Math.round(baseUserDelay / playbackSpeed)));
          continue;
        }

        const content = msg.content || "";
        const hasToolCalls = msg.toolCalls && msg.toolCalls.length > 0;

        if (!content) {
          setMessages(prev => [...prev, msg]);
          if (hasToolCalls) {
            openPanelForToolCalls(msg.toolCalls || []);
          }
          await sleep(80);
          continue;
        }

        const base: Message = {
          ...msg,
          content: "",
          streaming: true,
          toolCalls: hasToolCalls ? [] : msg.toolCalls,
        };
        setMessages(prev => [...prev, base]);

        const perChunkDelay = Math.max(10, Math.round(baseChunkDelay / playbackSpeed));
        for (let i = 0; i < content.length; i += chunkSize) {
          if (playbackCancelRef.current) return;
          const next = content.slice(i, i + chunkSize);
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (!last || last.id !== msg.id) return prev;
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                content: last.content + next,
                streaming: i + chunkSize < content.length,
              },
            ];
          });
          await sleep(perChunkDelay);
        }

        if (hasToolCalls) {
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (!last || last.id !== msg.id) return prev;
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                toolCalls: msg.toolCalls,
                streaming: false,
              },
            ];
          });
          openPanelForToolCalls(msg.toolCalls || []);
        }
        await sleep(Math.max(60, Math.round(baseMessageDelay / playbackSpeed)));
      }
    };

    play();

    return () => {
      playbackCancelRef.current = true;
    };
  }, [fullMessages, playbackEnabled, playbackSpeed]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // 空函数用于只读模式
  const noopFunction = () => {};

  const handleOpenPanel = (type: RightPanelType) => {
    setRightPanelType(type);
    setShowRightPanel(true);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-10 w-10 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">加载中...</p>
        </div>
      </div>
    );
  }

  if (error || !shareData) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center bg-card p-8 rounded-2xl shadow-lg max-w-md border">
          <AlertCircle className="h-16 w-16 text-destructive mx-auto mb-4" />
          <h1 className="text-xl font-semibold mb-2">分享链接已失效</h1>
          <p className="text-muted-foreground">{error || "该链接可能已过期或被删除"}</p>
        </div>
      </div>
    );
  }

  const stopPlayback = () => {
    playbackCancelRef.current = true;
    setPlaybackEnabled(false);
    setMessages(fullMessages);
  };

  const togglePlayback = () => {
    if (playbackEnabled) {
      stopPlayback();
    } else {
      playbackCancelRef.current = true;
      setPlaybackEnabled(true);
    }
  };

  return (
    <div className="h-screen bg-background flex flex-col">
      {/* 头部 */}
      <header className="sticky top-0 left-0 right-0 h-16 bg-card border-b z-50 flex items-center justify-between px-6 shadow-sm">
        <div>
          <h1 className="text-foreground font-semibold truncate max-w-md">
            {shareData.conversation.title}
          </h1>
          <p className="text-xs text-muted-foreground">
            由 SlideAgent 生成 · {shareData.share_info.view_count} 次查看
          </p>
        </div>
      </header>

      {/* 主内容区域 - 使用与对话页面相同的布局 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 中间聊天区域 */}
        <div className="flex-1 flex flex-col min-w-0 relative chat-surface">
          {/* 顶部占位栏 */}
          <div className="h-[58px] shrink-0" />
          {/* 消息列表 */}
          <ScrollArea className="flex-1 chat-surface">
            <div className="max-w-4xl mx-auto px-6 pt-0 pb-8">
              {messages.map((message, index) => {
                // 判断是否是第一条 AI 消息
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
                      onOpenPanel={handleOpenPanel}
                      onConfirmInfo={noopFunction}
                      currentTopic={shareData.conversation.title}
                    autoConfirmCountdown={null}
                    onCancelAutoConfirm={noopFunction}
                    isFirstAiMessage={isFirstAiMessage}
                    isFirstUserMessage={isFirstUserMessage}
                    onSetSearchRound={setCurrentSearchRound}
                    onSetImageSearchRound={setCurrentImageSearchRound}
                    onScrollToSlide={noopFunction}
                    isShareMode={true}
                    showThinking={true}
                  />
                );
              })}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>
        </div>

        {/* 右侧工具面板 */}
        <RightPanel
          rightPanelType={rightPanelType}
          setRightPanelType={setRightPanelType}
          showRightPanel={showRightPanel}
          setShowRightPanel={setShowRightPanel}
          pptHtmlCode={pptHtmlCode}
          pptViewMode={pptViewMode}
          setPptViewMode={setPptViewMode}
          pptProject={pptProject}
          currentTopic={shareData.conversation.title}
          isEditMode={isEditMode}
          setIsEditMode={setIsEditMode}
          taskPlan={taskPlan}
          taskPlanStreaming={false}
          searchRounds={searchRounds}
          currentSearchRound={currentSearchRound}
          setCurrentSearchRound={setCurrentSearchRound}
          deepThinking=""
          deepThinkingStreaming={false}
          imageSearchRounds={imageSearchRounds}
          currentImageSearchRound={currentImageSearchRound}
          setCurrentImageSearchRound={setCurrentImageSearchRound}
          pptOutline={pptOutline}
          pptOutlineStreaming={false}
          pptProjects={[]}
          onSelectProject={noopFunction}
          onDownload={noopFunction}
          onShare={noopFunction}
          onPlay={noopFunction}
          onFullscreen={noopFunction}
        />
      </div>

      {/* 底部输入区域（只读） */}
      <div className="p-4 shrink-0">
        <div className="max-w-4xl mx-auto">
          <div className="relative rounded-2xl border border-border bg-muted/50">
            <textarea
              disabled
              value=""
              placeholder="分享页面仅查看，无法继续对话"
              className="w-full px-4 py-4 bg-transparent resize-none focus:outline-none min-h-[56px] text-sm text-muted-foreground"
              rows={1}
            />
            <div className="flex items-center justify-between px-4 py-2 border-t border-border/50">
              <div className="flex items-center gap-2">
                <div className="h-8 rounded-full px-3 flex items-center gap-2 text-sm bg-background/80 border border-border/50 text-muted-foreground">
                  <Globe className="h-3.5 w-3.5" />
                  <span>联网搜索</span>
                  <span className="text-muted-foreground">· 仅查看</span>
                </div>
                <button
                  disabled
                  className="p-1.5 hover:bg-muted/80 rounded-lg transition-colors"
                >
                  <Paperclip className="h-4 w-4 text-muted-foreground" />
                </button>
                <button
                  onClick={togglePlayback}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  {playbackEnabled ? "关闭流式回放" : "开启流式回放"}
                </button>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={stopPlayback}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  直接显示最终结果
                </button>
                <button
                  disabled
                  className="w-8 h-8 rounded-full flex items-center justify-center bg-muted text-muted-foreground"
                >
                  <Send className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

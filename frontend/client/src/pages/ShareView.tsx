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
import { Loader2, AlertCircle } from "lucide-react";
import { getShareData } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import MessageItem from "@/components/MessageItem";
import RightPanel from "@/components/RightPanel";
import type { Message, ToolCall, TaskPlan, SearchRound, RightPanelType, PPTViewMode, PPTProject } from "@/types";

interface ShareMessage {
  id: number;
  role: string;
  content: string;
  created_at: string;
  tool_calls: ShareToolCall[];
}

interface ShareToolCall {
  id: number;
  tool_type: string;
  tool_name: string;
  status: string;
  arguments: any;
  result: any;
  search_rounds?: SearchRound[];
  task_plan?: TaskPlan;
}

interface SearchRoundData {
  id: number;
  round_number: number;
  query: string;
  thinking: string;
  results: SearchResultData[];
}

interface SearchResultData {
  id: number;
  title: string;
  url: string;
  snippet: string;
}

interface TaskPlanData {
  id: number;
  plan_content: string;
  steps: any;
}

interface PPTProjectData {
  id: number;
  title: string;
  outline_content: string;
  slides: Slide[];
}

interface Slide {
  id: number;
  page_number: number;
  page_title: string;
  html_content: string;
}

interface ShareData {
  conversation: {
    id: number;
    uuid: string;
    title: string;
    created_at: string;
  };
  messages: ShareMessage[];
  ppt_project: PPTProjectData | null;
  share_info: {
    share_id: string;
    view_count: number;
    created_at: string;
    expires_at: string;
  };
}

export default function ShareView() {
  const { shareId } = useParams<{ shareId: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [shareData, setShareData] = useState<ShareData | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  
  // 右侧面板状态
  const [showRightPanel, setShowRightPanel] = useState(false);
  const [rightPanelType, setRightPanelType] = useState<RightPanelType>(null);
  
  // 任务规划状态
  const [taskPlan, setTaskPlan] = useState<TaskPlan | null>(null);
  
  // 搜索状态
  const [searchRounds, setSearchRounds] = useState<SearchRound[]>([]);
  const [currentSearchRound, setCurrentSearchRound] = useState(1);
  
  // PPT 状态
  const [pptOutline, setPptOutline] = useState("");
  const [pptHtmlCode, setPptHtmlCode] = useState("");
  const [pptViewMode, setPptViewMode] = useState<PPTViewMode>("preview");
  const [pptProject, setPptProject] = useState<PPTProject | null>(null);
  const [isEditMode, setIsEditMode] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

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
        const convertedMessages: Message[] = data.messages.map((msg: ShareMessage) => {
          const toolCalls: ToolCall[] = msg.tool_calls?.map((tc: ShareToolCall) => {
            // 构建工具调用数据
            const toolData: any = {
              ...(tc.arguments || {}),
              ...(tc.result || {}),
            };

            // 处理搜索轮次
            if (tc.search_rounds && tc.search_rounds.length > 0) {
              toolData.searchRounds = tc.search_rounds.map((sr: SearchRoundData) => ({
                round: sr.round_number,
                query: sr.query,
                thinking: sr.thinking,
                results: sr.results?.map((r: SearchResultData) => ({
                  title: r.title,
                  url: r.url,
                  snippet: r.snippet,
                })) || [],
                isCompleted: true,
              }));
            }

            // 处理任务规划
            if (tc.task_plan) {
              toolData.taskPlan = {
                content: tc.task_plan.plan_content,
                steps: tc.task_plan.steps || [],
              };
            }

            return {
              id: tc.id.toString(),
              type: tc.tool_type as any,
              name: tc.tool_name,
              status: tc.status as any,
              data: toolData,
            };
          }) || [];

          return {
            id: msg.id.toString(),
            role: msg.role as "user" | "assistant",
            content: msg.content,
            timestamp: new Date(msg.created_at).getTime(),
            toolCalls,
          };
        });

        setMessages(convertedMessages);
        
        // 提取任务规划、搜索轮次和PPT数据
        if (data.messages) {
          // 提取任务规划
          for (const msg of data.messages) {
            if (msg.tool_calls) {
              for (const tc of msg.tool_calls) {
                if (tc.tool_type === "task_plan" && tc.task_plan) {
                  setTaskPlan({
                    content: tc.task_plan.plan_content,
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
                      thinking: sr.thinking,
                      results: sr.results?.map((r: any) => ({
                        title: r.title,
                        url: r.url,
                        snippet: r.snippet,
                      })) || [],
                      isCompleted: true,
                    });
                  }
                }
              }
            }
          }
          setSearchRounds(extractedRounds);
          
          // 提取PPT大纲
          for (const msg of data.messages) {
            if (msg.tool_calls) {
              for (const tc of msg.tool_calls) {
                if (tc.tool_type === "ppt_outline" && tc.result?.outline) {
                  setPptOutline(tc.result.outline);
                }
              }
            }
          }
        }
        
        // 处理PPT项目
        if (data.ppt_project) {
          const project = data.ppt_project;
          
          // 转换为前端PPTProject格式
          const convertedProject: PPTProject = {
            id: project.id,
            conversation_id: data.conversation.id,
            title: project.title,
            outline_content: project.outline_content,
            versions: [{
              id: 1,
              version_number: 1,
              version_name: "V1",
              slides: project.slides.map((slide: Slide) => ({
                id: slide.id,
                page_number: slide.page_number,
                page_title: slide.page_title,
                html_content: slide.html_content,
              })),
            }],
            current_version: {
              id: 1,
              version_number: 1,
              version_name: "V1",
              slides: project.slides.map((slide: Slide) => ({
                id: slide.id,
                page_number: slide.page_number,
                page_title: slide.page_title,
                html_content: slide.html_content,
              })),
            },
          };
          
          setPptProject(convertedProject);
          
          // 生成HTML代码
          if (project.slides && project.slides.length > 0) {
            const htmlCode = project.slides
              .sort((a: Slide, b: Slide) => a.page_number - b.page_number)
              .map((slide: Slide) => slide.html_content)
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

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* 头部 */}
      <header className="sticky top-0 left-0 right-0 h-16 bg-card border-b z-50 flex items-center justify-between px-6 shadow-sm">
        <div>
          <h1 className="text-foreground font-semibold truncate max-w-md">
            {shareData.conversation.title}
          </h1>
          <p className="text-xs text-muted-foreground">
            由 PPTAgent 生成 · {shareData.share_info.view_count} 次查看
          </p>
        </div>
      </header>

      {/* 主内容区域 - 使用与对话页面相同的布局 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 中间聊天区域 */}
        <div className="flex-1 flex flex-col">
          {/* 消息列表 */}
          <ScrollArea className="flex-1 chat-surface">
            <div className="max-w-4xl mx-auto px-6 py-8">
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

      {/* 底部 */}
      <footer className="py-6 text-center text-muted-foreground text-sm border-t bg-card">
        <p>使用 SlideAgent 创建您自己的演示文稿</p>
      </footer>
    </div>
  );
}

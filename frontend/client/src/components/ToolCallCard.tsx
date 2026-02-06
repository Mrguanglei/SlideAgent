import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import {
  ChevronDown,
  ChevronRight,
  FileSliders,
  Search,
  Image as ImageIcon,
  CheckCircle2,
  Loader2,
  CalendarCheck,
  Brain,
} from "lucide-react";
import type { ToolCall, RightPanelType } from "@/types";
import ThinkingBlock from "./ThinkingBlock";

// 工具调用卡片 Props
interface ToolCallCardProps {
  tool: ToolCall;
  onOpenPanel: (type: RightPanelType) => void;
  onConfirm: (selectedData: Record<string, unknown>) => void;
  topic: string;
  autoConfirmCountdown: number | null;
  onCancelAutoConfirm: () => void;
  onSetSearchRound?: (round: number) => void;
  onScrollToSlide?: (slideIndex: number) => void;
  isShareMode?: boolean; // 分享模式，自动展开所有内容
}

export default function ToolCallCard({
  tool,
  onOpenPanel,
  onConfirm,
  topic,
  autoConfirmCountdown,
  onCancelAutoConfirm,
  onSetSearchRound,
  onScrollToSlide,
  isShareMode = false,
}: ToolCallCardProps) {
  // 根据工具状态决定默认展开状态：分享模式下全部展开，否则 pending 时展开
  const [isExpanded, setIsExpanded] = useState(isShareMode || tool.status === "pending");
  const [selectedAudience, setSelectedAudience] = useState<string>("");
  const [selectedModules, setSelectedModules] = useState<string[]>([]);
  const [selectedStyle, setSelectedStyle] = useState<string>("");
  const [selectedNumPages, setSelectedNumPages] = useState<string>("8-10页");
  const [keywords, setKeywords] = useState<string>("");

  // 当工具状态变为 confirmed 时，自动折叠
  useEffect(() => {
    console.log(`[ToolCallCard] Tool ${tool.id} status changed to: ${tool.status}`);
    if (tool.status === "confirmed") {
      console.log(`[ToolCallCard] Collapsing tool ${tool.id}`);
      setIsExpanded(false);
    }
  }, [tool.status, tool.id]);

  // 从 tool.data 获取动态选项
  const dynamicData = tool.data as {
    topic?: string;
    audienceQuestion?: string;
    audienceOptions?: string[];
    modulesQuestion?: string;
    modulesOptions?: string[];
    styleQuestion?: string;
    styleOptions?: string[];
    numPagesQuestion?: string;
    numPagesOptions?: string[];
    emphasisQuestion?: string;
    emphasisPlaceholder?: string;
    // Confirmed data fields
    audience?: string;
    modules?: string[];
    style?: string;
    num_pages?: string;
    keywords?: string;
  };

  const getIcon = () => {
    switch (tool.type) {
      case "supplement_info":
        return <FileSliders className="h-3.5 w-3.5 text-primary" />;
      case "task_plan":
        return <FileSliders className="h-3.5 w-3.5 text-primary" />;
      case "web_search":
        return <Search className="h-3.5 w-3.5 text-primary" />;
      case "image_search":
        return <ImageIcon className="h-3.5 w-3.5 text-primary" />;
      case "ppt_outline":
        return <FileSliders className="h-3.5 w-3.5 text-primary" />;
      case "ppt_generate":
        return <FileSliders className="h-3.5 w-3.5 text-white" />;
      case "deep_thinking":
        return <Brain className="h-3.5 w-3.5 text-primary" />;
      default:
        return <FileSliders className="h-3.5 w-3.5 text-primary" />;
    }
  };

  const getStatusBadge = () => {
    switch (tool.status) {
      case "pending":
        return null;
      case "confirmed":
        return <span className="status-confirmed">已跳过</span>;
      case "auto_execute":
        return <span className="status-auto">自动执行</span>;
      case "running":
        return (
          <span className="text-xs px-2 py-0.5 rounded bg-primary/10 text-primary flex items-center gap-1">
            <Loader2 className="h-3 w-3 animate-spin" />
            执行中
          </span>
        );
      case "completed":
        return (
          <span className="text-xs px-2 py-0.5 rounded bg-green-500/10 text-green-600 flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3" />
            已完成
          </span>
        );
      default:
        return null;
    }
  };

  const handleConfirm = () => {
    if (!tool.id) {
      console.error("Tool ID is missing");
      return;
    }
    onCancelAutoConfirm();
    onConfirm({
      audience: selectedAudience,
      modules: selectedModules,
      style: selectedStyle,
      num_pages: selectedNumPages,
      keywords,
    });
  };

  const toggleModule = (module: string) => {
    setSelectedModules((prev) =>
      prev.includes(module)
        ? prev.filter((m) => m !== module)
        : [...prev, module]
    );
  };

  const renderContent = () => {
    switch (tool.type) {
      case "supplement_info":
        return (
          <div className="tool-card">
            <div
              className="flex items-center justify-between px-4 py-3 cursor-pointer"
              onClick={() => setIsExpanded(!isExpanded)}
            >
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">
                  {getIcon()}
                </div>
                <span className="font-medium text-sm">{tool.name}</span>
                {tool.status === "pending" && (
                  <span className="status-auto">自动执行</span>
                )}
                {getStatusBadge()}
              </div>
              <div className="flex items-center gap-2 text-muted-foreground text-sm">
                {tool.status === "confirmed" && <span>已确认相关信息</span>}
                {tool.status !== "confirmed" && (
                  <ChevronDown
                    className={cn(
                      "h-4 w-4 transition-transform",
                      isExpanded && "rotate-180"
                    )}
                  />
                )}
              </div>
            </div>
            {isExpanded && (
              <div className="px-4 pb-4 space-y-4 border-t border-border/50 pt-4">
                {tool.status === "pending" ? (
                  // 待确认状态：显示表单
                  <>
                    <p className="text-sm text-muted-foreground">
                      为了保证生成质量，我需要向您确认更多需求细节
                    </p>

                    {/* 受众选择 */}
                    {dynamicData.audienceOptions &&
                      dynamicData.audienceOptions.length > 0 && (
                        <div>
                          <p className="text-sm mb-2.5">
                            {dynamicData.audienceQuestion ||
                              `这份PPT的目标受众是？`}
                            <span className="text-muted-foreground ml-1">
                              （单选）
                            </span>
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {dynamicData.audienceOptions.map((opt) => (
                              <button
                                key={opt}
                                onClick={() => setSelectedAudience(opt)}
                                className={cn(
                                  "px-4 py-1.5 rounded-full text-sm border transition-colors",
                                  selectedAudience === opt
                                    ? "border-primary bg-primary/10 text-primary"
                                    : "border-border hover:border-primary/50"
                                )}
                              >
                                {opt}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                    {/* 内容模块选择 */}
                    {dynamicData.modulesOptions &&
                      dynamicData.modulesOptions.length > 0 && (
                        <div>
                          <p className="text-sm mb-2.5">
                            {dynamicData.modulesQuestion ||
                              `PPT中需要包含哪些内容模块？`}
                            <span className="text-muted-foreground ml-1">
                              （多选）
                            </span>
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {dynamicData.modulesOptions.map((opt) => (
                              <button
                                key={opt}
                                onClick={() => toggleModule(opt)}
                                className={cn(
                                  "px-4 py-1.5 rounded-full text-sm border transition-colors",
                                  selectedModules.includes(opt)
                                    ? "border-primary bg-primary/10 text-primary"
                                    : "border-border hover:border-primary/50"
                                )}
                              >
                                {opt}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                    {/* 设计风格选择 */}
                    {dynamicData.styleOptions &&
                      dynamicData.styleOptions.length > 0 && (
                        <div>
                          <p className="text-sm mb-2.5">
                            {dynamicData.styleQuestion ||
                              `你期望的PPT设计风格是？`}
                            <span className="text-muted-foreground ml-1">
                              （单选）
                            </span>
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {dynamicData.styleOptions.map((opt) => (
                              <button
                                key={opt}
                                onClick={() => setSelectedStyle(opt)}
                                className={cn(
                                  "px-4 py-1.5 rounded-full text-sm border transition-colors",
                                  selectedStyle === opt
                                    ? "border-primary bg-primary/10 text-primary"
                                    : "border-border hover:border-primary/50"
                                )}
                              >
                                {opt}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                    {/* 页数范围选择 */}
                    {dynamicData.numPagesOptions &&
                      dynamicData.numPagesOptions.length > 0 && (
                        <div>
                          <p className="text-sm mb-2.5">
                            {dynamicData.numPagesQuestion ||
                              `您期望的PPT页数范围是？`}
                            <span className="text-muted-foreground ml-1">
                              （单选）
                            </span>
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {dynamicData.numPagesOptions.map((opt) => (
                              <button
                                key={opt}
                                onClick={() => setSelectedNumPages(opt)}
                                className={cn(
                                  "px-4 py-1.5 rounded-full text-sm border transition-colors",
                                  selectedNumPages === opt
                                    ? "border-primary bg-primary/10 text-primary"
                                    : "border-border hover:border-primary/50"
                                )}
                              >
                                {opt}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                    {/* 关键词输入 */}
                    {dynamicData.emphasisQuestion && (
                      <div>
                        <p className="text-sm mb-2.5">
                          {dynamicData.emphasisQuestion}
                        </p>
                        <textarea
                          value={keywords}
                          onChange={(e) => setKeywords(e.target.value)}
                          placeholder={
                            dynamicData.emphasisPlaceholder ||
                            "请输入您希望强调的关键词或内容..."
                          }
                          className="w-full px-3 py-2 text-sm border border-border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary/20"
                          rows={3}
                        />
                      </div>
                    )}

                    {/* 操作按钮 */}
                    <div className="flex items-center justify-between pt-2">
                      <div className="flex items-center gap-2">
                        {autoConfirmCountdown !== null && (
                          <span className="text-xs text-muted-foreground">
                            {autoConfirmCountdown}秒后自动确认
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => {
                            onCancelAutoConfirm();
                            onConfirm({});
                          }}
                          className="px-4 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                        >
                          跳过
                        </button>
                        <button
                          onClick={handleConfirm}
                          className="px-4 py-1.5 text-sm bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
                        >
                          确认
                        </button>
                      </div>
                    </div>
                  </>
                ) : (
                  // 已确认或已完成状态：显示只读信息
                  <div className="text-sm space-y-2">
                    <p className="text-muted-foreground">
                      {tool.status === "confirmed" ? "已确认的信息：" : tool.status === "auto_execute" ? "已自动执行" : "此任务已完成"}
                    </p>
                    {dynamicData.topic && (
                      <div className="bg-muted/30 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground mb-1">主题</p>
                        <p className="text-sm">{dynamicData.topic}</p>
                      </div>
                    )}
                    {dynamicData.audience && (
                      <div className="bg-muted/30 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground mb-1">目标受众</p>
                        <p className="text-sm">{dynamicData.audience}</p>
                      </div>
                    )}
                    {dynamicData.modules && Array.isArray(dynamicData.modules) && dynamicData.modules.length > 0 && (
                      <div className="bg-muted/30 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground mb-1">内容模块</p>
                        <p className="text-sm">{dynamicData.modules.join('、')}</p>
                      </div>
                    )}
                    {dynamicData.style && (
                      <div className="bg-muted/30 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground mb-1">设计风格</p>
                        <p className="text-sm">{dynamicData.style}</p>
                      </div>
                    )}
                    {dynamicData.num_pages && (
                      <div className="bg-muted/30 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground mb-1">页数</p>
                        <p className="text-sm">{dynamicData.num_pages}</p>
                      </div>
                    )}
                    {dynamicData.keywords && (
                      <div className="bg-muted/30 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground mb-1">重点内容</p>
                        <p className="text-sm">{dynamicData.keywords}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        );

      case "task_plan":
        const planData = tool.data as {
          coreRequirement?: string;
          core_requirement?: string;
          goal?: string;
          problemAnalysis?: { title?: string; items: string[] };
          problem_analysis?: { title?: string; items: string[] };
          details?: string[];
          requirements?: string[];
        };
        const coreReq =
          planData.coreRequirement ||
          planData.core_requirement ||
          planData.goal ||
          "";
        const problemAnalysis =
          planData.problemAnalysis || planData.problem_analysis;
        const details = planData.details || planData.requirements || [];

        return (
          <div className="space-y-3">
            {coreReq && (
              <div className="text-sm leading-relaxed">
                <p className="text-muted-foreground">
                  用户询问"{coreReq}"，我需要分析这个请求...
                </p>
              </div>
            )}
            {problemAnalysis &&
              problemAnalysis.items &&
              problemAnalysis.items.length > 0 && (
                <div className="text-sm leading-relaxed">
                  <span className="font-medium">
                    1. {problemAnalysis.title || "核心问题识别"}：
                  </span>
                  <ul className="text-muted-foreground mt-1 space-y-0.5 ml-2">
                    {problemAnalysis.items.slice(0, 2).map((item, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-primary">•</span>
                        <span className="line-clamp-1">{item}</span>
                      </li>
                    ))}
                    {problemAnalysis.items.length > 2 && (
                      <li className="text-muted-foreground/60 ml-4">...</li>
                    )}
                  </ul>
                </div>
              )}
            {!problemAnalysis && details && details.length > 0 && (
              <div className="text-sm leading-relaxed">
                <span className="font-medium">细节需求</span>
                <ul className="text-muted-foreground mt-1 space-y-1">
                  {details.slice(0, 2).map((detail, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-primary">•</span>
                      <span>{detail}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <button
              onClick={() => onOpenPanel("task_plan")}
              className="tool-button group"
            >
              <div className="w-5 h-5 rounded-full bg-amber-50 flex items-center justify-center">
                <CalendarCheck className="h-3 w-3 text-amber-500" />
              </div>
              <span className="tool-button-text">任务执行规划</span>
              <ChevronRight className="tool-button-arrow h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
            </button>
          </div>
        );

      case "web_search":
        const searchData = tool.data as {
          query?: string;
          search_query?: string;
          keyword?: string;
          round?: number;
          total?: number;
        };
        const searchQuery =
          searchData.query ||
          searchData.search_query ||
          searchData.keyword ||
          topic;
        const roundNum = searchData.round || 1;
        const totalRounds = searchData.total || 1;

        console.log("[ToolCallCard] web_search data:", {
          query: searchData.query,
          search_query: searchData.search_query,
          keyword: searchData.keyword,
          topic: topic,
          finalQuery: searchQuery
        });

        return (
          <button
            onClick={() => {
              onOpenPanel("web_search");
              if (onSetSearchRound) {
                onSetSearchRound(roundNum);
              }
            }}
            className="tool-button group"
          >
            <div className="w-5 h-5 rounded-full bg-blue-50 flex items-center justify-center">
              <Search className="h-3 w-3 text-blue-500" />
            </div>
            <span className="tool-button-text">搜索网页</span>
            <span className="text-muted-foreground text-sm truncate max-w-[200px]">{searchQuery}</span>
            <ChevronRight className="tool-button-arrow h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
          </button>
        );

      case "image_search":
        return (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="tool-button"
          >
            <ImageIcon className="tool-button-icon h-4 w-4" />
            <span className="tool-button-text">搜索图片</span>
            <span className="tool-button-query">
              {tool.data.query as string}
            </span>
            <ChevronRight className="tool-button-arrow h-4 w-4" />
          </button>
        );

      case "ppt_outline":
        return (
          <button
            onClick={() => onOpenPanel("ppt_outline")}
            className="tool-button group"
          >
            <div className="w-5 h-5 rounded-full bg-green-50 flex items-center justify-center">
              <FileSliders className="h-3 w-3 text-green-500" />
            </div>
            <span className="tool-button-text">PPT 大纲目录</span>
            <ChevronRight className="tool-button-arrow h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
          </button>
        );

      case "ppt_generate":
        const slideData = tool.data as {
          description?: string;
          title?: string;
          topic?: string;
          pageNumber?: number;
        };
        // 过滤掉 think 标签内容
        const rawSlideTitle =
          slideData.description || slideData.title || slideData.topic || topic;
        const slideTitle = rawSlideTitle.replace(/<think>[\s\S]*?<\/think>/gi, '').replace(/<think>[\s\S]*$/gi, '').trim();
        const slideIndex = (slideData.pageNumber || 1) - 1;
        return (
          <button
            onClick={() => {
              onOpenPanel("ppt_preview");
              if (onScrollToSlide) {
                setTimeout(() => {
                  onScrollToSlide(slideIndex);
                }, 100);
              }
            }}
            className="tool-button group"
          >
            <div className="w-5 h-5 rounded-full bg-purple-50 flex items-center justify-center">
              <FileSliders className="h-3 w-3 text-purple-500" />
            </div>
            <span className="tool-button-text">新增页面</span>
            <span className="text-muted-foreground text-sm truncate max-w-[300px]">{slideTitle}</span>
            <ChevronRight className="tool-button-arrow h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
          </button>
        );

      case "deep_thinking":
        const thinkingData = tool.data as { content?: string };
        const thinkingContent = thinkingData.content || "";
        const thinkingStatus = tool.status === "running" ? "thinking" : "completed";
        const hasThinkingContent = thinkingContent.trim().length > 0;

        return (
          <div className="tool-card">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">
                  {getIcon()}
                </div>
                <span className="font-medium text-sm">思考过程</span>
                {tool.status === "running" && (
                  <span className="status-auto">进行中</span>
                )}
                {tool.status === "completed" && (
                  <span className="status-confirmed">已完成</span>
                )}
              </div>
            </div>
            <div className="px-4 pb-4 pt-3">
              {hasThinkingContent ? (
                <ThinkingBlock
                  content={thinkingContent}
                  status={thinkingStatus}
                  defaultExpanded={thinkingStatus === "thinking" || isShareMode}
                />
              ) : (
                <div className="thinking-pill">
                  {tool.status === "running" ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>思考中...</span>
                    </>
                  ) : (
                    <span>思考完毕</span>
                  )}
                </div>
              )}
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return renderContent();
}

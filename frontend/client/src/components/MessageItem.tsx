import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  ChevronDown,
  Sparkles,
  User,
} from "lucide-react";
import ToolCallCard from "./ToolCallCard";
import type { Message, RightPanelType } from "@/types";

// 智谱风格 AI 头像
function AIAvatar() {
  return (
    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-sm shrink-0">
      <svg viewBox="0 0 24 24" className="w-5 h-5 text-white" fill="currentColor">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
      </svg>
    </div>
  );
}

// 消息组件 Props
interface MessageItemProps {
  message: Message;
  onOpenPanel: (type: RightPanelType) => void;
  onConfirmInfo: (toolCallId: string, selectedData: Record<string, unknown>) => void;
  currentTopic: string;
  autoConfirmCountdown: number | null;
  onCancelAutoConfirm: () => void;
  isFirstAiMessage: boolean;
  onSetSearchRound?: (round: number) => void;
  onScrollToSlide?: (slideIndex: number) => void;
  isShareMode?: boolean; // 分享模式
}

export default function MessageItem({
  message,
  onOpenPanel,
  onConfirmInfo,
  currentTopic,
  autoConfirmCountdown,
  onCancelAutoConfirm,
  isFirstAiMessage,
  onSetSearchRound,
  onScrollToSlide,
  isShareMode = false,
}: MessageItemProps) {
  const isUser = message.role === "user";
  // 分享模式下默认展开深度思考
  const [thinkingExpanded, setThinkingExpanded] = useState(isShareMode);

  return (
    <div className={cn("mb-6", isUser && "flex justify-end")}>
      {isUser ? (
        /* 用户消息 - 右对齐 */
        <div className="flex items-start gap-3">
          <div className="bg-card border border-border rounded-2xl px-4 py-3 max-w-[80%]">
            <p className="text-sm">{message.content}</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
            <User className="h-4 w-4 text-primary" />
          </div>
        </div>
      ) : (
        /* AI 消息 - 左对齐，智谱风格 */
        <div className="space-y-3">
          {/* AI 头像和名称 - 只在第一条 AI 消息显示 */}
          {isFirstAiMessage && (
            <div className="flex items-center gap-2">
              <AIAvatar />
              <span className="text-sm font-medium text-foreground">SlideAgent</span>
              <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">AI</span>
            </div>
          )}

          {/* 深度思考内容 - 可折叠 */}
          {message.isDeepThinking && message.content && (
            <div className="border border-border/50 rounded-xl overflow-hidden bg-card ml-10">
              <button
                onClick={() => setThinkingExpanded(!thinkingExpanded)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-primary" />
                  <span className="text-sm font-medium">深度思考</span>
                  <span className="text-xs text-muted-foreground">内容分析中...</span>
                </div>
                <ChevronDown
                  className={cn(
                    "h-4 w-4 text-muted-foreground transition-transform",
                    thinkingExpanded && "rotate-180"
                  )}
                />
              </button>

              {thinkingExpanded && (
                <div className="px-4 py-3 border-t border-border/50 bg-muted/20">
                  <div className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto">
                    {message.content}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* AI 普通文字内容 - 带打字效果光标 */}
          {!message.isDeepThinking && message.content && (
            <div className="ml-10">
              <p className="text-sm leading-relaxed inline">
                {message.content}
              </p>
              {/* 流式输入时显示闪烁的圆点光标 */}
              {message.streaming && (
                <span className="inline-flex items-center ml-1">
                  <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                </span>
              )}
            </div>
          )}

          {/* 工具调用卡片 - 过滤掉流式更新消息和未开始的工具 */}
          <div className="ml-10 space-y-2">
            {(() => {
              const filtered = message.toolCalls?.filter((tool) => {
                // 搜索工具：只显示 completed 状态
                if (tool.type === "web_search") {
                  return tool.status === "completed";
                }
                // 深度思考：不在对话区显示
                if (tool.type === "task_plan" && tool.data?.streaming) {
                  return false;
                }
                // 流式更新消息：不在对话区显示
                if (tool.type === "ppt_outline" && tool.data?.streaming) {
                  return false;
                }
                // 任务规划和PPT大纲：只在完成后显示
                if (tool.type === "task_plan" || tool.type === "ppt_outline") {
                  return tool.status === "completed";
                }
                return true;
              });
              return filtered?.map((tool, idx) => (
                <ToolCallCard
                  key={`${message.id}-tool-${idx}`}
                  tool={tool}
                  onOpenPanel={onOpenPanel}
                  onConfirm={(selectedData) =>
                    onConfirmInfo(tool.id || `tool-${idx}`, selectedData)
                  }
                  topic={currentTopic}
                  autoConfirmCountdown={
                    tool.type === "supplement_info" && tool.status === "pending"
                      ? autoConfirmCountdown
                      : null
                  }
                  onCancelAutoConfirm={onCancelAutoConfirm}
                  onSetSearchRound={onSetSearchRound}
                  onScrollToSlide={onScrollToSlide}
                  isShareMode={isShareMode}
                />
              ));
            })()}
          </div>
        </div>
      )}
    </div>
  );
}

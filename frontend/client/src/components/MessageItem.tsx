import { useState } from "react";
import { cn } from "@/lib/utils";
import { User, Bot, Loader2 } from "lucide-react";
import ToolCallCard from "./ToolCallCard";
import ThinkingBlock from "./ThinkingBlock";
import type { Message, RightPanelType } from "@/types";

// 解析消息中的 <think> 标签
// 返回结构化数据，status 用于控制组件显隐
interface ThinkBlock {
  content: string;
  status: "thinking" | "completed";
}

interface ThinkParseResult {
  thinkBlocks: ThinkBlock[];
  normalContent: string;
  hasPending: boolean;
}

function parseThinkTags(content: string): ThinkParseResult {
  // 1. 提取完整的 <think>...</think> 块 (大小写不敏感)
  const thinkRegex = /<think>([\s\S]*?)<\/think>/gi;
  const thinkBlocks: ThinkBlock[] = [];

  // 使用 replace 提取完整块并从原文移除
  let normalContent = content.replace(thinkRegex, (match, p1) => {
    thinkBlocks.push({ content: p1.trim(), status: 'completed' });
    return "";
  });

  // 2. 处理末尾未闭合的 <think> 标签（流式输出场景）(大小写不敏感)
  let hasPending = false;
  const pendingThinkRegex = /<think>([\s\S]*)$/i;
  const pendingMatch = pendingThinkRegex.exec(normalContent);

  if (pendingMatch) {
    hasPending = true;
    normalContent = normalContent.replace(pendingThinkRegex, "");
  }

  // 3. 处理潜在的标签开始（防止 "<" 或 "<t" 等闪烁）(大小写不敏感)
  const potentialTagRegex = /<(?:t(?:h(?:i(?:n(?:k)?)?)?)?)?$/i;
  // 如果以 < 开头，且看起来像是 <think> 的一部分，则暂时移除这部分显示
  if (potentialTagRegex.test(normalContent) && !normalContent.endsWith(">")) {
    normalContent = normalContent.replace(potentialTagRegex, "");
  }

  return { thinkBlocks, normalContent: normalContent.trim(), hasPending };
}

// 智谱风格 AI 头像
const AIAvatar = () => (
  <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary/20 to-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5 border border-primary/20 shadow-sm">
    <Bot className="w-5 h-5 text-primary" />
  </div>
);

// 消息组件 Props
interface MessageItemProps {
  message: Message;
  onOpenPanel: (type: RightPanelType) => void;
  onConfirmInfo: (toolCallId: string, selectedData: Record<string, unknown>) => void;
  currentTopic: string;
  autoConfirmCountdown: number | null;
  onCancelAutoConfirm: () => void;
  isFirstAiMessage: boolean;
  isFirstUserMessage?: boolean;
  onSetSearchRound?: (round: number) => void;
  onScrollToSlide?: (slideIndex: number) => void;
  isShareMode?: boolean; // 分享模式
  showThinking?: boolean; // 是否展示思考内容
}

export default function MessageItem({
  message,
  onOpenPanel,
  onConfirmInfo,
  currentTopic,
  autoConfirmCountdown,
  onCancelAutoConfirm,
  isFirstAiMessage,
  isFirstUserMessage = false,
  onSetSearchRound,
  onScrollToSlide,
  isShareMode = false,
  showThinking = true,
}: MessageItemProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("mb-8", isUser && "flex justify-end")}>
      {isUser ? (
        /* 用户消息 - 右对齐 */
        <div className="flex items-start gap-3 flex-row-reverse">
          {isFirstUserMessage ? (
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary to-primary/80 flex items-center justify-center shrink-0 shadow-sm mt-0.5 ring-1 ring-primary/20">
              <User className="h-4 w-4 text-primary-foreground" />
            </div>
          ) : (
            <div className="w-9 h-9 shrink-0 mt-0.5" aria-hidden />
          )}
          <div className="user-bubble max-w-[85%]">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
          </div>
        </div>
      ) : (
        /* AI 消息 - 左对齐，智谱风格 */
        <div className="flex gap-3">
          {/* AI 头像 */}
          {isFirstAiMessage ? <AIAvatar /> : <div className="w-9 h-9 shrink-0 mt-0.5" aria-hidden />}

          <div className="flex-1 space-y-3 min-w-0">
            {/* 这里的 IIFE 用于处理 content 解析逻辑 */}
            {(() => {
              // 解析消息中的 think 标签
              const { thinkBlocks, normalContent, hasPending } = parseThinkTags(message.content || "");

              return (
                <div className="space-y-3">
                  {/* AI 名称 - 只在第一条 AI 消息显示 */}
                  {isFirstAiMessage && (
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-foreground/80">SlideAgent</span>
                      <span className="text-xs text-muted-foreground/60">
                        {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  )}

                  {/* 思考中占位 - 不直接显示思考内容 */}
                  {showThinking && hasPending && (
                    <div className="thinking-pill">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>思考中...</span>
                    </div>
                  )}

                  {/* 思维链内容 - 使用 ThinkingBlock 组件 */}
                  {showThinking && thinkBlocks.length > 0 && (
                    <div className="space-y-2">
                      {thinkBlocks.map((block, idx) => (
                        <ThinkingBlock
                          key={idx}
                          content={block.content}
                          status={block.status}
                          defaultExpanded={block.status === 'thinking' || isShareMode}
                        />
                      ))}
                    </div>
                  )}

                  {/* AI 普通文字内容 */}
                  {(!message.isDeepThinking && normalContent) && (
                    <div className="assistant-bubble">
                      <div className="prose prose-sm dark:prose-invert max-w-none text-foreground leading-normal break-words">
                        <div className="whitespace-pre-wrap">{normalContent}</div>
                        {message.streaming && (
                          <span className="inline-block w-1.5 h-4 ml-1 bg-primary animate-pulse align-middle" />
                        )}
                      </div>
                    </div>
                  )}

                  {/* 仅有思维链且正在流式输出时显示光标 */}
                  {!message.isDeepThinking && !normalContent && message.streaming && thinkBlocks.length === 0 && (
                    <div className="assistant-bubble inline-flex items-center">
                      <span className="inline-block w-1.5 h-4 ml-1 bg-primary animate-pulse align-middle" />
                    </div>
                  )}

                  {/* 工具调用卡片 */}
                  {(() => {
                    // 兼容 message.toolCalls (camelCase from some types) or message.tool_calls (snake_case from API)
                    const tools = message.toolCalls || message.tool_calls || [];

                    const filtered = tools.filter((tool) => {
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

                    if (filtered.length === 0) return null;

                    return (
                      <div className="space-y-2 mt-2">
                        {filtered.map((tool, idx) => (
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
                        ))}
                      </div>
                    );
                  })()}

                </div>
              );
            })()}
          </div>
        </div>
      )}
    </div>
  );
}

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { User, Loader2 } from "lucide-react";
import Lottie, { LottieRefCurrentProps } from "lottie-react";
import planetAnimationRaw from "@/assets/planet.json?raw";
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

const planetAnimationData = JSON.parse(planetAnimationRaw) as object;

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

// AI 头像组件 - 使用 Lottie 动画
export const AI_AVATAR_OFFSET_X = -0.5;

interface AIAvatarProps {
  isActive?: boolean; // 是否正在活动（循环播放动画）
  offsetX?: number; // 头像水平偏移（px）
}

export const AIAvatar = ({ isActive = false, offsetX = AI_AVATAR_OFFSET_X }: AIAvatarProps) => {
  const lottieRef = useRef<LottieRefCurrentProps>(null);
  // 根据 isActive 控制播放/暂停
  useEffect(() => {
    if (lottieRef.current) {
      if (isActive) {
        lottieRef.current.play();
      } else {
        // 停在最后一帧显示静态效果
        const totalFrames = lottieRef.current.getDuration(true);
        if (totalFrames) {
          lottieRef.current.goToAndStop(totalFrames - 1, true);
        }
      }
    }
  }, [isActive]);

  return (
    <div
      className="w-12 h-12 flex items-center justify-center flex-shrink-0"
      style={{ filter: 'saturate(1.4) contrast(1.1)' }}
    >
      <Lottie
        lottieRef={lottieRef}
        animationData={planetAnimationData}
        loop={isActive}
        autoplay={true}
        style={{ width: 48, height: 48, transform: `translateX(${offsetX}px)` }}
        onComplete={() => {
          // 动画播放完成后，如果不是活动状态，停在最后一帧
          if (!isActive && lottieRef.current) {
            const totalFrames = lottieRef.current.getDuration(true);
            if (totalFrames) {
              lottieRef.current.goToAndStop(totalFrames - 1, true);
            }
          }
        }}
      />
    </div>
  );
};

// 用户头像
const UserAvatar = () => (
  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-blue-500 flex items-center justify-center flex-shrink-0 shadow-sm">
    <User className="w-4 h-4 text-white" />
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
  isLoading?: boolean; // AI 是否正在处理任务
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
  isLoading = false,
}: MessageItemProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("mb-6", isUser && "")}>
      {isUser ? (
        /* 用户消息 - 左对齐，类似智谱清言风格 */
        <div className="space-y-1.5">
          {/* 用户头像和名称 - 同一行居中对齐，往左突出 */}
          {isFirstUserMessage && (
            <div className="flex items-center gap-2 -ml-2 min-h-12">
              <div className="w-12 h-12 flex items-center justify-center shrink-0">
                <UserAvatar />
              </div>
              <span className="text-base font-medium text-foreground leading-none">用户</span>
            </div>
          )}
          {/* 用户消息内容 - 与名称对齐 */}
          <div className="pl-8">
            <p className="leading-relaxed whitespace-pre-wrap text-foreground">{message.content}</p>
          </div>
        </div>
      ) : (
        /* AI 消息 - 左对齐，智谱风格 */
        <div className="space-y-1.5">
          {/* AI 头像和名称 - 只在首条 AI 消息显示 */}
          {isFirstAiMessage && (
            <div className="flex items-center gap-1 -ml-2 min-h-12">
              <div className="w-12 h-12 flex items-center justify-center shrink-0">
                <AIAvatar isActive={isLoading} />
              </div>
              <span className="text-base font-medium text-foreground leading-none">SlideAgent</span>
            </div>
          )}

          {/* AI 消息内容 - 与名称对齐 */}
          <div className="pl-8">
            {/* 这里的 IIFE 用于处理 content 解析逻辑 */}
            {(() => {
              // 解析消息中的 think 标签
              const { thinkBlocks, normalContent, hasPending } = parseThinkTags(message.content || "");

              return (
                <div className="space-y-3">

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
                    <div className="prose prose-sm dark:prose-invert max-w-none text-foreground leading-relaxed break-words">
                      <div className="whitespace-pre-wrap">{normalContent}</div>
                      {message.streaming && (
                        <span className="inline-block w-1.5 h-4 ml-1 bg-primary animate-pulse align-middle" />
                      )}
                    </div>
                  )}

                  {/* 仅有思维链且正在流式输出时显示光标 */}
                  {!message.isDeepThinking && !normalContent && message.streaming && thinkBlocks.length === 0 && (
                    <div className="inline-flex items-center">
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

/**
 * ChatArea - 聊天消息列表 + 底部输入框
 */
import { RefObject } from "react";
import { Send, Paperclip, Database, Globe, X, Pause } from "lucide-react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Popover, PopoverContent, PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select, SelectContent, SelectItem, SelectTrigger,
} from "@/components/ui/select";
import MessageItem, { AIAvatar, AI_AVATAR_OFFSET_X } from "@/components/MessageItem";
import LoadingDots from "@/components/LoadingDots";
import type { Message, RightPanelType } from "@/types";
import type { UploadResponse } from "@/lib/api";

const SEARCH_MODE_OPTIONS = [
  { value: "auto", label: "自动", description: "自动判断联网获取信息" },
  { value: "on", label: "开启联网", description: "始终联网获取信息" },
  { value: "off", label: "关闭", description: "不再联网获取信息" },
] as const;

const getSearchModeLabel = (value: "auto" | "on" | "off") =>
  SEARCH_MODE_OPTIONS.find(item => item.value === value)?.label || "自动";

interface ChatAreaProps {
  messages: Message[];
  isLoading: boolean;
  isConfirming: boolean;
  inputValue: string;
  setInputValue: (v: string) => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  messagesEndRef: RefObject<HTMLDivElement | null>;
  activeAttachments: UploadResponse[];
  setActiveAttachments: React.Dispatch<React.SetStateAction<UploadResponse[]>>;
  searchMode: "auto" | "on" | "off";
  setSearchMode: (v: "auto" | "on" | "off") => void;
  isSearchDisabled: boolean;
  chatPopoverOpen: boolean;
  setChatPopoverOpen: (v: boolean) => void;
  currentTopic: string;
  autoConfirmCountdown: number | null;
  currentSessionId: string | null;
  currentConversationId: number | null;
  onSend: () => void;
  onOpenPanel: (type: RightPanelType) => void;
  onConfirmInfo: (toolCallId: string, data: Record<string, unknown>) => void;
  onCancelAutoConfirm: () => void;
  onSetSearchRound: (round: number) => void;
  onSetImageSearchRound: (round: number) => void;
  onScrollToSlide: (index: number) => void;
  onOpenKbSelector: () => void;
  onOpenFileInput: () => void;
  onPause: () => void;
  onCompositionStart: React.CompositionEventHandler<HTMLTextAreaElement>;
  onCompositionEnd: React.CompositionEventHandler<HTMLTextAreaElement>;
  onKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement>;
  setConversations: React.Dispatch<React.SetStateAction<any[]>>;
}

export default function ChatArea({
  messages,
  isLoading,
  isConfirming,
  inputValue,
  setInputValue,
  inputRef,
  messagesEndRef,
  activeAttachments,
  setActiveAttachments,
  searchMode,
  setSearchMode,
  isSearchDisabled,
  chatPopoverOpen,
  setChatPopoverOpen,
  currentTopic,
  autoConfirmCountdown,
  onSend,
  onOpenPanel,
  onConfirmInfo,
  onCancelAutoConfirm,
  onSetSearchRound,
  onSetImageSearchRound,
  onScrollToSlide,
  onOpenKbSelector,
  onOpenFileInput,
  onPause,
  onCompositionStart,
  onCompositionEnd,
  onKeyDown,
}: ChatAreaProps) {
  return (
    <div className="h-full flex flex-col relative">
      <div className="h-[58px] shrink-0" />
      <ScrollArea className="flex-1 chat-surface">
        <div className="max-w-4xl mx-auto px-6 pt-0 pb-8">
          {messages.map((message, index) => {
            const isFirstAiMessage = message.role === "assistant" && (index === 0 || messages[index - 1]?.role !== "assistant");
            const isFirstUserMessage = message.role === "user" && (index === 0 || messages[index - 1]?.role !== "user");
            return (
              <MessageItem
                key={message.id}
                message={message}
                onOpenPanel={onOpenPanel}
                onConfirmInfo={onConfirmInfo}
                currentTopic={currentTopic}
                autoConfirmCountdown={autoConfirmCountdown}
                onCancelAutoConfirm={onCancelAutoConfirm}
                isFirstAiMessage={isFirstAiMessage}
                isFirstUserMessage={isFirstUserMessage}
                onSetSearchRound={onSetSearchRound}
                onSetImageSearchRound={onSetImageSearchRound}
                onScrollToSlide={onScrollToSlide}
                showThinking={false}
                isLoading={isLoading}
              />
            );
          })}

          {isLoading && messages.length > 0 && messages[messages.length - 1]?.role === "user" && (() => {
            const hasAssistant = messages.some(m => m.role === "assistant");
            return (
              <div className="mb-6">
                {!hasAssistant ? (
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
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">正在生成中...</span>
                    <LoadingDots />
                  </div>
                )}
              </div>
            );
          })()}

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

      {/* 底部输入框 */}
      <div className="p-4 shrink-0">
        <div className="max-w-4xl mx-auto">
          <div className="relative rounded-2xl border border-border bg-muted/50">
            {activeAttachments.length > 0 && (
              <div className="flex flex-wrap gap-2 px-4 pt-3">
                {activeAttachments.map(file => (
                  <div key={file.id} className="flex items-center gap-1 bg-background px-2 py-1 rounded-md text-sm border border-border">
                    <span className="truncate max-w-[150px]">{file.filename}</span>
                    <button onClick={() => setActiveAttachments(prev => prev.filter(f => f.id !== file.id))} className="hover:text-destructive transition-colors">
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
              onCompositionStart={onCompositionStart}
              onCompositionEnd={onCompositionEnd}
              onKeyDown={onKeyDown}
              placeholder="想调整内容、样式或风格等吗，直接告诉我吧"
              className="w-full px-4 py-4 bg-transparent resize-none focus:outline-none min-h-[56px] max-h-[200px] text-sm"
              rows={1}
            />

            <div className="flex items-center justify-between px-4 py-2 border-t border-border/50">
              <Select value={searchMode} disabled={isSearchDisabled} onValueChange={(v) => { if (v === "auto" || v === "on" || v === "off") setSearchMode(v); }}>
                <SelectTrigger size="sm" className={cn("h-8 rounded-full px-3", isSearchDisabled && "opacity-50 cursor-not-allowed")}>
                  <div className="flex items-center gap-2 text-sm">
                    <Globe className="h-3.5 w-3.5 text-muted-foreground" />
                    <span>联网搜索</span>
                    <span className="text-muted-foreground">· {getSearchModeLabel(searchMode)}</span>
                  </div>
                </SelectTrigger>
                <SelectContent align="start" className="min-w-[240px]">
                  {SEARCH_MODE_OPTIONS.map(option => (
                    <SelectItem key={option.value} value={option.value}>
                      <div className="flex flex-col gap-0.5 text-left">
                        <span className="text-sm">{option.label}</span>
                        <span className="text-xs text-muted-foreground">{option.description}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <div className="flex items-center gap-2">
                <Popover open={chatPopoverOpen} onOpenChange={setChatPopoverOpen}>
                  <PopoverTrigger asChild>
                    <button className="p-1.5 hover:bg-muted/80 rounded-lg transition-colors">
                      <Paperclip className="h-4 w-4 text-muted-foreground" />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent className="w-48 p-0" align="start">
                    <div className="flex flex-col">
                      <button onClick={onOpenKbSelector} className="flex items-center gap-2 px-4 py-2 hover:bg-muted text-sm text-left transition-colors">
                        <Database className="h-4 w-4" /><span>云知识库选择</span>
                      </button>
                      <button onClick={onOpenFileInput} className="flex items-center gap-2 px-4 py-2 hover:bg-muted text-sm text-left transition-colors">
                        <Paperclip className="h-4 w-4" /><span>本地文件选择</span>
                      </button>
                    </div>
                  </PopoverContent>
                </Popover>

                {isLoading ? (
                  <button
                    onClick={onPause}
                    className="w-8 h-8 rounded-full flex items-center justify-center transition-colors bg-orange-500 text-white hover:bg-orange-600"
                    title="暂停任务"
                  >
                    <Pause className="h-4 w-4" />
                  </button>
                ) : (
                  <button
                    onClick={onSend}
                    disabled={!inputValue.trim()}
                    className={cn(
                      "w-8 h-8 rounded-full flex items-center justify-center transition-colors",
                      inputValue.trim() ? "bg-primary text-white hover:bg-primary/90" : "bg-muted text-muted-foreground"
                    )}
                  >
                    <Send className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

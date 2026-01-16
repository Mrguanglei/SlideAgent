import { useState, useRef, useCallback, KeyboardEvent } from "react";
import { usePPTAgent } from "@/contexts/PPTAgentContext";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { FileUpload } from "./FileUpload";
import { ConvertType, TEMPLATES, PAGE_OPTIONS, CONVERT_OPTIONS } from "@shared/pptagent";
import {
  Send,
  Paperclip,
  Settings2,
  Loader2,
  Sparkles,
} from "lucide-react";

interface ChatInputProps {
  onSend: (message: string, config: {
    convertType: ConvertType;
    template: string | null;
    numPages: number | null;
  }) => void;
  disabled?: boolean;
  className?: string;
}

export function ChatInput({ onSend, disabled, className }: ChatInputProps) {
  const { state } = usePPTAgent();
  const [message, setMessage] = useState("");
  const [convertType, setConvertType] = useState<ConvertType>(ConvertType.DEEPPRESENTER);
  const [template, setTemplate] = useState<string>("auto");
  const [numPages, setNumPages] = useState<string>("auto");
  const [showUpload, setShowUpload] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage && state.attachments.length === 0) return;

    onSend(trimmedMessage || "请根据上传的附件制作 PPT", {
      convertType,
      template: template === "auto" ? null : template,
      numPages: numPages === "auto" ? null : parseInt(numPages, 10),
    });

    setMessage("");
    setShowUpload(false);
  }, [message, state.attachments.length, convertType, template, numPages, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const isTemplateMode = convertType === ConvertType.PPTAGENT;

  return (
    <div className={cn("space-y-3", className)}>
      {/* File Upload Area */}
      {showUpload && (
        <div className="animate-in slide-in-from-bottom-2 duration-200">
          <FileUpload />
        </div>
      )}

      {/* Input Area */}
      <div className="relative bg-card rounded-2xl elegant-shadow border border-border/50 overflow-hidden">
        {/* Config Bar */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-border/50 bg-accent/30">
          <Settings2 className="h-4 w-4 text-muted-foreground" />
          <span className="text-xs text-muted-foreground mr-2">生成配置</span>
          
          {/* Convert Type */}
          <Select
            value={convertType}
            onValueChange={(v) => setConvertType(v as ConvertType)}
          >
            <SelectTrigger className="h-7 w-auto gap-1.5 text-xs bg-background/50 border-0">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CONVERT_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Template (only for template mode) */}
          {isTemplateMode && (
            <Select value={template} onValueChange={setTemplate}>
              <SelectTrigger className="h-7 w-auto gap-1.5 text-xs bg-background/50 border-0">
                <SelectValue placeholder="选择模板" />
              </SelectTrigger>
              <SelectContent>
                {TEMPLATES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {/* Page Count */}
          <Select value={numPages} onValueChange={setNumPages}>
            <SelectTrigger className="h-7 w-auto gap-1.5 text-xs bg-background/50 border-0">
              <SelectValue placeholder="页数" />
            </SelectTrigger>
            <SelectContent>
              {PAGE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Text Input */}
        <div className="flex items-end gap-2 p-3">
          <Button
            variant="ghost"
            size="icon"
            className={cn(
              "h-9 w-9 shrink-0 rounded-full",
              showUpload && "bg-primary/10 text-primary"
            )}
            onClick={() => setShowUpload(!showUpload)}
          >
            <Paperclip className="h-5 w-5" />
          </Button>

          <Textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入您的 PPT 需求，例如：帮我制作一份关于人工智能的演示文稿..."
            disabled={disabled}
            className={cn(
              "min-h-[44px] max-h-[200px] resize-none border-0 bg-transparent",
              "focus-visible:ring-0 focus-visible:ring-offset-0",
              "placeholder:text-muted-foreground/60"
            )}
            rows={1}
          />

          <Button
            onClick={handleSend}
            disabled={disabled || (!message.trim() && state.attachments.length === 0)}
            className={cn(
              "h-9 w-9 shrink-0 rounded-full",
              "bg-primary hover:bg-primary/90"
            )}
            size="icon"
          >
            {disabled ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </Button>
        </div>

        {/* Attachment Count Badge */}
        {state.attachments.length > 0 && (
          <div className="absolute bottom-14 left-3 flex items-center gap-1.5 px-2 py-1 rounded-full bg-primary/10 text-primary text-xs">
            <Paperclip className="h-3 w-3" />
            <span>{state.attachments.length} 个文件</span>
          </div>
        )}
      </div>

      {/* Quick Prompts */}
      <div className="flex flex-wrap gap-2">
        {[
          "帮我制作一份商业计划书 PPT",
          "创建一个产品介绍演示文稿",
          "制作一份技术分享的幻灯片",
        ].map((prompt) => (
          <Button
            key={prompt}
            variant="outline"
            size="sm"
            className="h-7 text-xs rounded-full bg-background/50 hover:bg-accent"
            onClick={() => setMessage(prompt)}
          >
            <Sparkles className="h-3 w-3 mr-1.5 text-primary" />
            {prompt}
          </Button>
        ))}
      </div>
    </div>
  );
}

export default ChatInput;

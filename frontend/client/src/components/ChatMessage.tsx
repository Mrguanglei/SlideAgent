import { ChatMessage as ChatMessageType, Role, AgentType, ToolCall } from "@shared/pptagent";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Card } from "@/components/ui/card";
import { Streamdown } from "streamdown";
import {
  User,
  Bot,
  Settings,
  Wrench,
  Search,
  Palette,
  FileSliders,
  Loader2,
} from "lucide-react";

interface ChatMessageProps {
  message: ChatMessageType;
}

const roleConfig = {
  [Role.USER]: {
    icon: User,
    label: "用户",
    bgClass: "bg-primary/10",
    textClass: "text-primary",
  },
  [Role.ASSISTANT]: {
    icon: Bot,
    label: "助手",
    bgClass: "bg-accent",
    textClass: "text-accent-foreground",
  },
  [Role.SYSTEM]: {
    icon: Settings,
    label: "系统",
    bgClass: "bg-muted",
    textClass: "text-muted-foreground",
  },
  [Role.TOOL]: {
    icon: Wrench,
    label: "工具",
    bgClass: "bg-secondary",
    textClass: "text-secondary-foreground",
  },
};

const agentConfig = {
  [AgentType.RESEARCH]: {
    icon: Search,
    label: "Research Agent",
    colorClass: "agent-research",
  },
  [AgentType.DESIGN]: {
    icon: Palette,
    label: "Design Agent",
    colorClass: "agent-design",
  },
  [AgentType.PPTAGENT]: {
    icon: FileSliders,
    label: "PPT Agent",
    colorClass: "agent-ppt",
  },
};

export function ChatMessageComponent({ message }: ChatMessageProps) {
  const isUser = message.role === Role.USER;
  const config = roleConfig[message.role];
  const Icon = config.icon;
  const agentInfo = message.agentType ? agentConfig[message.agentType] : null;
  const AgentIcon = agentInfo?.icon;

  return (
    <div
      className={cn(
        "flex gap-3 py-4 px-4 transition-colors",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <Avatar className={cn("h-9 w-9 shrink-0", config.bgClass)}>
        <AvatarFallback className={cn("bg-transparent", config.textClass)}>
          {agentInfo && AgentIcon ? (
            <AgentIcon className="h-4 w-4" />
          ) : (
            <Icon className="h-4 w-4" />
          )}
        </AvatarFallback>
      </Avatar>

      {/* Message Content */}
      <div
        className={cn(
          "flex flex-col gap-1.5 max-w-[80%]",
          isUser ? "items-end" : "items-start"
        )}
      >
        {/* Role/Agent Label */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {agentInfo ? (
            <span className={agentInfo.colorClass}>{agentInfo.label}</span>
          ) : (
            <span>{config.label}</span>
          )}
          <span>·</span>
          <span>{formatTime(message.timestamp)}</span>
        </div>

        {/* Message Bubble */}
        <Card
          className={cn(
            "px-4 py-3 elegant-shadow",
            isUser
              ? "bg-primary text-primary-foreground rounded-tr-sm"
              : "bg-card rounded-tl-sm"
          )}
        >
          {message.isStreaming && !message.content ? (
            <div className="flex items-center gap-1.5 py-1">
              <span className="w-2 h-2 rounded-full bg-current typing-dot opacity-60" />
              <span className="w-2 h-2 rounded-full bg-current typing-dot opacity-60" />
              <span className="w-2 h-2 rounded-full bg-current typing-dot opacity-60" />
            </div>
          ) : (
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <Streamdown>{message.content}</Streamdown>
            </div>
          )}

          {/* Streaming indicator */}
          {message.isStreaming && message.content && (
            <div className="flex items-center gap-1.5 mt-2 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              <span>正在生成...</span>
            </div>
          )}
        </Card>

        {/* Tool Calls */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="flex flex-col gap-2 mt-2 w-full">
            {message.toolCalls.map((toolCall) => (
              <ToolCallCard key={toolCall.id} toolCall={toolCall} />
            ))}
          </div>
        )}

        {/* Tool Result */}
        {message.toolResult && (
          <Card className="mt-2 p-3 bg-secondary/50 text-sm">
            <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
              <Wrench className="h-3 w-3" />
              <span>{message.toolResult.name} 执行结果</span>
            </div>
            <pre className="text-xs overflow-x-auto whitespace-pre-wrap break-words">
              {message.toolResult.result}
            </pre>
          </Card>
        )}
      </div>
    </div>
  );
}

interface ToolCallCardProps {
  toolCall: ToolCall;
}

function ToolCallCard({ toolCall }: ToolCallCardProps) {
  let parsedArgs: Record<string, unknown> = {};
  try {
    if (toolCall.function?.arguments) {
      parsedArgs = JSON.parse(toolCall.function.arguments);
    } else if (toolCall.data) {
      parsedArgs = toolCall.data;
    }
  } catch {
    // Keep empty object if parsing fails
  }

  const toolName = toolCall.function?.name || toolCall.name;

  return (
    <Card className="p-3 bg-accent/50 border-accent">
      <div className="flex items-center gap-2 text-xs font-medium mb-2">
        <Wrench className="h-3.5 w-3.5 text-primary" />
        <span className="text-primary">{toolName}</span>
      </div>
      <pre className="text-xs text-muted-foreground overflow-x-auto whitespace-pre-wrap break-words">
        {JSON.stringify(parsedArgs, null, 2)}
      </pre>
    </Card>
  );
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default ChatMessageComponent;

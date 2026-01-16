import { usePPTAgent } from "@/contexts/PPTAgentContext";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Progress } from "@/components/ui/progress";
import { AgentType, ToolExecution } from "@shared/pptagent";
import {
  Search,
  Palette,
  FileSliders,
  ChevronDown,
  ChevronRight,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  Wrench,
  Code2,
  Eye,
  FileJson,
  Zap,
} from "lucide-react";
import { useState } from "react";

const agentConfig = {
  [AgentType.RESEARCH]: {
    icon: Search,
    label: "Research Agent",
    description: "研究与信息收集",
    colorClass: "text-emerald-500",
    bgClass: "bg-emerald-500/10",
    borderClass: "border-emerald-500/30",
  },
  [AgentType.DESIGN]: {
    icon: Palette,
    label: "Design Agent",
    description: "设计与布局规划",
    colorClass: "text-violet-500",
    bgClass: "bg-violet-500/10",
    borderClass: "border-violet-500/30",
  },
  [AgentType.PPTAGENT]: {
    icon: FileSliders,
    label: "PPT Agent",
    description: "幻灯片生成",
    colorClass: "text-orange-500",
    bgClass: "bg-orange-500/10",
    borderClass: "border-orange-500/30",
  },
};

const statusConfig: Record<string, {
  icon: typeof Clock;
  label: string;
  colorClass: string;
  animate?: boolean;
}> = {
  idle: {
    icon: Clock,
    label: "等待中",
    colorClass: "text-muted-foreground",
  },
  pending: {
    icon: Clock,
    label: "等待中",
    colorClass: "text-muted-foreground",
  },
  running: {
    icon: Loader2,
    label: "执行中",
    colorClass: "text-primary",
    animate: true,
  },
  completed: {
    icon: CheckCircle2,
    label: "已完成",
    colorClass: "text-emerald-500",
  },
  error: {
    icon: XCircle,
    label: "错误",
    colorClass: "text-destructive",
  },
};

interface ToolPanelProps {
  className?: string;
}

export function ToolPanel({ className }: ToolPanelProps) {
  const { state } = usePPTAgent();
  const [activeTab, setActiveTab] = useState("agents");

  return (
    <div className={cn("flex flex-col h-full", className)}>
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col h-full">
        <div className="px-4 pt-4 pb-2 border-b border-border/50">
          <div className="flex items-center gap-2 mb-3">
            <Zap className="h-5 w-5 text-primary" />
            <h2 className="font-semibold">行动面板</h2>
          </div>
          <TabsList className="w-full grid grid-cols-3 h-9">
            <TabsTrigger value="agents" className="text-xs">
              <Search className="h-3.5 w-3.5 mr-1.5" />
              Agent 状态
            </TabsTrigger>
            <TabsTrigger value="tools" className="text-xs">
              <Wrench className="h-3.5 w-3.5 mr-1.5" />
              工具调用
            </TabsTrigger>
            <TabsTrigger value="raw" className="text-xs">
              <FileJson className="h-3.5 w-3.5 mr-1.5" />
              原始数据
            </TabsTrigger>
          </TabsList>
        </div>

        <ScrollArea className="flex-1 elegant-scroll">
          <TabsContent value="agents" className="m-0 p-4 space-y-3">
            {state.agentStatuses.map((agent) => (
              <AgentStatusCard key={agent.type} agent={agent} />
            ))}
          </TabsContent>

          <TabsContent value="tools" className="m-0 p-4 space-y-3">
            {state.toolExecutions.length === 0 ? (
              <EmptyState
                icon={Wrench}
                title="暂无工具调用"
                description="开始对话后，这里将显示工具调用记录"
              />
            ) : (
              state.toolExecutions.map((execution) => (
                <ToolExecutionCard key={execution.id} execution={execution} />
              ))
            )}
          </TabsContent>

          <TabsContent value="raw" className="m-0 p-4">
            <RawDataView />
          </TabsContent>
        </ScrollArea>
      </Tabs>
    </div>
  );
}

interface AgentStatusCardProps {
  agent: {
    type: AgentType;
    status: "idle" | "running" | "completed" | "error";
    currentStep?: string;
    progress?: number;
    startTime?: number;
    endTime?: number;
  };
}

function AgentStatusCard({ agent }: AgentStatusCardProps) {
  const config = agentConfig[agent.type];
  const status = statusConfig[agent.status];
  const Icon = config.icon;
  const StatusIcon = status.icon;

  return (
    <Card className={cn("border", config.borderClass, "transition-all duration-300")}>
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center", config.bgClass)}>
            <Icon className={cn("h-5 w-5", config.colorClass)} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <h3 className="font-medium text-sm">{config.label}</h3>
              <Badge
                variant="secondary"
                className={cn("text-xs", status.colorClass)}
              >
                <StatusIcon
                  className={cn(
                    "h-3 w-3 mr-1",
                    status.animate && "animate-spin"
                  )}
                />
                {status.label}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              {config.description}
            </p>
            {agent.currentStep && (
              <p className="text-xs text-primary mt-2 truncate">
                {agent.currentStep}
              </p>
            )}
            {agent.progress !== undefined && agent.status === "running" && (
              <Progress value={agent.progress} className="h-1 mt-2" />
            )}
            {agent.startTime && (
              <p className="text-xs text-muted-foreground mt-2">
                {formatDuration(agent.startTime, agent.endTime)}
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface ToolExecutionCardProps {
  execution: ToolExecution;
}

function ToolExecutionCard({ execution }: ToolExecutionCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const status = statusConfig[execution.status];
  const StatusIcon = status.icon;
  const agentInfo = agentConfig[execution.agentType];

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card className="border border-border/50 overflow-hidden">
        <CollapsibleTrigger className="w-full">
          <CardHeader className="p-3 hover:bg-accent/50 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <Wrench className="h-4 w-4 text-primary" />
              </div>
              <div className="flex-1 min-w-0 text-left">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm truncate">
                    {execution.name}
                  </span>
                  <Badge variant="outline" className={cn("text-xs", agentInfo.colorClass)}>
                    {agentInfo.label}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  {formatDuration(execution.startTime, execution.endTime)}
                </p>
              </div>
              <StatusIcon
                className={cn(
                  "h-4 w-4 shrink-0",
                  status.colorClass,
                  status.animate && "animate-spin"
                )}
              />
              {isOpen ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
              )}
            </div>
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="p-3 pt-0 space-y-3">
            {/* Arguments */}
            <div>
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1.5">
                <Code2 className="h-3 w-3" />
                <span>调用参数</span>
              </div>
              <pre className="text-xs bg-accent/50 rounded-lg p-3 overflow-x-auto">
                {JSON.stringify(execution.arguments, null, 2)}
              </pre>
            </div>

            {/* Result */}
            {execution.result !== undefined && (
              <div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1.5">
                  <Eye className="h-3 w-3" />
                  <span>执行结果</span>
                </div>
                <pre className="text-xs bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 rounded-lg p-3 overflow-x-auto">
                  {typeof execution.result === "string"
                    ? execution.result
                    : JSON.stringify(execution.result, null, 2)}
                </pre>
              </div>
            )}

            {/* Error */}
            {execution.error && (
              <div>
                <div className="flex items-center gap-1.5 text-xs text-destructive mb-1.5">
                  <XCircle className="h-3 w-3" />
                  <span>错误信息</span>
                </div>
                <pre className="text-xs bg-destructive/10 text-destructive rounded-lg p-3 overflow-x-auto">
                  {execution.error}
                </pre>
              </div>
            )}
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}

function RawDataView() {
  const { state } = usePPTAgent();

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium mb-2">会话状态</h3>
        <pre className="text-xs bg-accent/50 rounded-lg p-3 overflow-x-auto max-h-[300px]">
          {JSON.stringify(
            {
              messagesCount: state.messages.length,
              attachmentsCount: state.attachments.length,
              isProcessing: state.isProcessing,
              pptState: state.pptState,
            },
            null,
            2
          )}
        </pre>
      </div>

      <div>
        <h3 className="text-sm font-medium mb-2">Agent 状态</h3>
        <pre className="text-xs bg-accent/50 rounded-lg p-3 overflow-x-auto max-h-[300px]">
          {JSON.stringify(state.agentStatuses, null, 2)}
        </pre>
      </div>

      <div>
        <h3 className="text-sm font-medium mb-2">工具执行记录</h3>
        <pre className="text-xs bg-accent/50 rounded-lg p-3 overflow-x-auto max-h-[300px]">
          {JSON.stringify(state.toolExecutions, null, 2)}
        </pre>
      </div>
    </div>
  );
}

interface EmptyStateProps {
  icon: typeof Wrench;
  title: string;
  description: string;
}

function EmptyState({ icon: Icon, title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-full bg-accent flex items-center justify-center mb-3">
        <Icon className="h-6 w-6 text-muted-foreground" />
      </div>
      <h3 className="font-medium text-sm">{title}</h3>
      <p className="text-xs text-muted-foreground mt-1">{description}</p>
    </div>
  );
}

function formatDuration(startTime: number, endTime?: number): string {
  const end = endTime || Date.now();
  const duration = end - startTime;

  if (duration < 1000) {
    return `${duration}ms`;
  } else if (duration < 60000) {
    return `${(duration / 1000).toFixed(1)}s`;
  } else {
    const minutes = Math.floor(duration / 60000);
    const seconds = Math.floor((duration % 60000) / 1000);
    return `${minutes}m ${seconds}s`;
  }
}

export default ToolPanel;

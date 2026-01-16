// PPTAgent shared types

export enum Role {
  SYSTEM = "system",
  USER = "user",
  ASSISTANT = "assistant",
  TOOL = "tool",
}

export enum AgentType {
  RESEARCH = "research",
  DESIGN = "design",
  PPTAGENT = "pptagent",
}

export enum ConvertType {
  DEEPPRESENTER = "deeppresenter",
  PPTAGENT = "pptagent",
}

// 智谱清言风格的工具调用类型
export type ToolCallType = 
  | "supplement_info"  // 补充信息
  | "task_plan"        // 任务规划
  | "web_search"       // 搜索网页
  | "image_search"     // 搜索图片
  | "new_page"         // 新增页面
  | "function";        // 通用函数调用

export interface ToolCall {
  id: string;
  type: ToolCallType;
  name: string;
  status: "pending" | "running" | "completed" | "confirmed" | "auto_execute" | "error";
  data?: Record<string, unknown>;
  function?: {
    name: string;
    arguments: string;
  };
}

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  timestamp: number;
  toolCalls?: ToolCall[];
  toolResult?: {
    name: string;
    result: string;
  };
  agentType?: AgentType;
  isStreaming?: boolean;
}

export interface AgentStatus {
  type: AgentType;
  status: "idle" | "running" | "completed" | "error";
  currentStep?: string;
  progress?: number;
  startTime?: number;
  endTime?: number;
}

export interface ToolExecution {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  status: "pending" | "running" | "completed" | "error";
  result?: unknown;
  error?: string;
  startTime: number;
  endTime?: number;
  agentType: AgentType;
}

export interface PPTGenerationConfig {
  convertType: ConvertType;
  template: string | null;
  numPages: number | null;
}

export interface PPTGenerationState {
  status: "idle" | "generating" | "completed" | "error";
  config?: PPTGenerationConfig;
  outputPath?: string;
  previewUrl?: string;
  error?: string;
}

export interface FileAttachment {
  id: string;
  name: string;
  size: number;
  type: string;
  url?: string;
  uploadProgress?: number;
}

export interface ConversationState {
  messages: ChatMessage[];
  attachments: FileAttachment[];
  agentStatuses: AgentStatus[];
  toolExecutions: ToolExecution[];
  pptState: PPTGenerationState;
  isProcessing: boolean;
}

// Template options
export const TEMPLATES = [
  { value: "auto", label: "自动选择" },
  { value: "default", label: "默认模板" },
  { value: "beamer", label: "Beamer 学术风格" },
  { value: "thu", label: "清华大学" },
  { value: "ucas", label: "中国科学院大学" },
  { value: "hit", label: "哈尔滨工业大学" },
  { value: "cip", label: "CIP 商务风格" },
] as const;

// Page count options
export const PAGE_OPTIONS = [
  { value: "auto", label: "自动" },
  ...Array.from({ length: 30 }, (_, i) => ({
    value: String(i + 1),
    label: `${i + 1} 页`,
  })),
] as const;

// Convert type options
export const CONVERT_OPTIONS = [
  { value: ConvertType.DEEPPRESENTER, label: "自由生成 (Freeform)" },
  { value: ConvertType.PPTAGENT, label: "模板生成 (Templates)" },
] as const;

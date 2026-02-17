// PPTAgent 类型定义

// 消息类型
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  toolCalls?: ToolCall[];
  tool_calls?: any[]; // 为了兼容后端返回的原始数据
  isDeepThinking?: boolean;
  deepThinkingContent?: string;
  streaming?: boolean; // 是否正在流式输出
}

// 工具调用类型
export interface ToolCall {
  id: string;
  type:
    | "task_plan"
    | "web_search"
    | "image_search"
    | "supplement_info"
    | "ppt_outline"
    | "ppt_generate"
    | "deep_thinking";
  name: string;
  status: "pending" | "confirmed" | "auto_execute" | "running" | "completed" | "error";
  data: ToolCallData;
}

// 工具调用数据
export interface ToolCallData {
  // 通用字段
  query?: string;
  round?: number;

  // 任务规划
  taskPlan?: TaskPlan;

  // 搜索相关
  searchRounds?: SearchRound[];
  images?: ImageSearchResult[];
  imageSearchRounds?: ImageSearchRound[];

  // 补充信息
  audienceQuestion?: string;
  audienceOptions?: string[];
  modulesQuestion?: string;
  modulesOptions?: string[];
  styleQuestion?: string;
  styleOptions?: string[];
  numPagesQuestion?: string;
  numPagesOptions?: string[];

  // PPT 相关
  outline?: string;
  slideTitle?: string;
  slideIndex?: number;
  htmlCode?: string;

  [key: string]: unknown;
}

// 任务规划
export interface TaskPlan {
  coreRequirement?: string;
  problemAnalysis?: {
    title?: string;
    items: string[];
  };
  informationDimensions?: {
    title?: string;
    items: string[];
  };
  searchStrategy?: {
    title?: string;
    items: string[];
  };
  steps?: TaskStep[];
  streamContent?: string;
  streaming?: boolean;
}

// 任务步骤
export interface TaskStep {
  id: number;
  text: string;
}

// 搜索轮次
export interface SearchRound {
  round: number;
  query: string;
  results: SearchResult[];
  isCompleted: boolean;
  thinking?: string;
}

// 搜索结果
export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
  date?: string;
}

// 图片搜索结果
export interface ImageSearchResult {
  url: string;
  description?: string;
  width?: number;
  height?: number;
  local_path?: string;
}

// 图片搜索轮次
export interface ImageSearchRound {
  round: number;
  query: string;
  images: ImageSearchResult[];
  isCompleted: boolean;
}

// PPT 项目
export interface PPTProject {
  id: number;
  conversation_id: number;
  title: string;
  outline_content?: string;
  created_at: string;
  updated_at: string;
  versions?: PPTVersion[];
  current_version?: PPTVersion;
  slides?: any[]; // 为了兼容后端返回的原始数据
}

// PPT 版本
export interface PPTVersion {
  id: number;
  project_id?: number;
  version_number: number;
  version_name?: string;
  created_at: string;
  slide_count?: number;
  slides?: PPTSlide[];
}

// PPT 幻灯片
export interface PPTSlide {
  id: number;
  version_id: number;
  page_number: number;
  page_title?: string;
  html_content: string;
  created_at: string;
  updated_at: string;
}

// 对话
export interface Conversation {
  id: number;
  uuid: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
  has_ppt?: boolean;
  task_status?: "idle" | "running" | "paused" | "completed";  // 任务状态
  active_session_id?: string | null;
  active_stage?: string | null;
}

// 右侧面板类型
export type RightPanelType =
  | "task_plan"
  | "web_search"
  | "image_search"
  | "ppt_outline"
  | "ppt_preview"
  | "files"
  | null;

// PPT 视图模式
export type PPTViewMode = "preview" | "code";

// 模板
export interface Template {
  id: number;
  title: string;
  category: string;
  color: string;
  subtitle?: string;
  preview?: string; // 预览图 URL
}

// 模板分类
export const TEMPLATE_CATEGORIES = ["全部", "科技", "商务", "创意"] as const;
export type TemplateCategory = typeof TEMPLATE_CATEGORIES[number];

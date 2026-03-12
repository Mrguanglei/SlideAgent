/**
 * PPTAgent API 调用封装
 */

import type {
  Conversation,
  PPTProject,
  PPTVersion,
  PPTSlide,
  Message,
  ToolCall,
  TaskPlan,
  SearchRound,
} from "@/types";

const API_BASE = "/api";

// ==================== 对话相关 API ====================

export interface ConversationDetail {
  conversation: Conversation;
  session_id?: string;
  task_status?: string;
  search_mode?: "auto" | "on" | "off";
  messages?: Message[];
  ppt_project?: PPTProject;
  task_plans?: TaskPlan[];
  search_rounds?: SearchRound[];
}

/**
 * 获取对话列表
 */
export async function getConversations(
  userId: string = "default_user",
  skip: number = 0,
  limit: number = 50
): Promise<Conversation[]> {
  const response = await fetch(
    `${API_BASE}/conversations?user_id=${userId}&skip=${skip}&limit=${limit}`
  );
  if (!response.ok) {
    throw new Error("Failed to fetch conversations");
  }
  return response.json();
}

/**
 * 获取对话详情（包含消息和工具调用）
 */
export async function getConversationDetail(
  conversationUuid: string
): Promise<ConversationDetail> {
  const response = await fetch(`${API_BASE}/conversations/uuid/${conversationUuid}`);
  if (!response.ok) {
    throw new Error("Failed to fetch conversation detail");
  }
  return response.json();
}

/**
 * 创建新对话
 */
export async function createConversation(
  title: string = "新对话",
  userId: string = "default_user"
): Promise<Conversation> {
  const response = await fetch(`${API_BASE}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, user_id: userId }),
  });
  if (!response.ok) {
    throw new Error("Failed to create conversation");
  }
  return response.json();
}

/**
 * 更新对话标题
 */
export async function updateConversation(
  conversationId: number,
  title: string
): Promise<Conversation> {
  const response = await fetch(`${API_BASE}/conversations/${conversationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    throw new Error("Failed to update conversation");
  }
  return response.json();
}

/**
 * 删除对话
 */
export async function deleteConversation(conversationId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/conversations/${conversationId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("Failed to delete conversation");
  }
}

// ==================== 文件上传相关 API ====================

export interface UploadResponse {
  id: string;
  filename: string;
  file_path: string;
  content_type: string;
  size: number;
  knowledge_document_id?: number;
}

/**
 * 上传文件
 */
export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/files/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Failed to upload file");
  }

  return response.json();
}

export interface DocumentResponse {
  id: number;
  filename: string;
  display_name: string;
  file_type: string;
  file_size: number;
  parse_status: string;
  created_at: string;
}

/**
 * 获取知识库文档列表
 */
export async function getKnowledgeDocuments(
  folderId?: number
): Promise<DocumentResponse[]> {
  const url = folderId
    ? `${API_BASE}/knowledge/documents?folder_id=${folderId}`
    : `${API_BASE}/knowledge/documents`;

  try {
    const response = await fetch(url);
    if (!response.ok) {
      console.error("Failed to fetch knowledge documents", response.statusText);
      return [];
    }
    return response.json();
  } catch (error) {
    console.error("Error fetching knowledge documents:", error);
    return [];
  }
}

/**
 * 获取 PPT 项目列表（文件面板用）
 */
export async function getPPTProjects(
  userId: string = "default_user",
  skip: number = 0,
  limit: number = 50
): Promise<PPTProject[]> {
  const response = await fetch(
    `${API_BASE}/ppt/projects?user_id=${userId}&skip=${skip}&limit=${limit}`
  );
  if (!response.ok) {
    throw new Error("Failed to fetch PPT projects");
  }
  return response.json();
}

/**
 * 获取 PPT 项目详情
 */
export async function getPPTProject(projectId: number): Promise<PPTProject> {
  const response = await fetch(`${API_BASE}/ppt/projects/${projectId}`);
  if (!response.ok) {
    throw new Error("Failed to fetch PPT project");
  }
  return response.json();
}

/**
 * 更新幻灯片内容（编辑功能）
 */
export async function updateSlide(
  slideId: number,
  htmlContent: string,
  pageTitle?: string,
  versionId?: number
): Promise<PPTSlide> {
  const response = await fetch(`${API_BASE}/ppt/slides/${slideId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      html_content: htmlContent,
      page_title: pageTitle,
      version_id: versionId,
    }),
  });
  if (!response.ok) {
    throw new Error("Failed to update slide");
  }
  return response.json();
}

/**
 * 创建新版本
 */
export async function createPPTVersion(
  projectId: number,
  versionName?: string
): Promise<PPTVersion> {
  const response = await fetch(`${API_BASE}/ppt/projects/${projectId}/versions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      version_name: versionName,
    }),
  });
  if (!response.ok) {
    throw new Error("Failed to create PPT version");
  }
  return response.json();
}

/**
 * 删除 PPT 项目
 */
export async function deletePPTProject(projectId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/ppt/projects/${projectId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("Failed to delete PPT project");
  }
}

// ==================== 导出相关 API ====================

export interface ExportRequest {
  project_id: number;
  version_id?: number;
  format: "pdf" | "png" | "pptx";
}

export interface ExportFormat {
  id: string;
  name: string;
  extension: string;
  description: string;
}

/**
 * 获取支持的导出格式
 */
export async function getExportFormats(): Promise<{ formats: ExportFormat[] }> {
  const response = await fetch(`${API_BASE}/ppt/export/formats`);
  if (!response.ok) {
    throw new Error("Failed to fetch export formats");
  }
  return response.json();
}

/**
 * 导出 PPT 文件
 */
export async function exportPPT(request: ExportRequest): Promise<Blob> {
  const response = await fetch(`${API_BASE}/ppt/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Export failed");
  }
  return response.blob();
}

// ==================== 分享相关 API ====================

export interface ShareRequest {
  project_id: number;
  version_id?: number;
  expire_days?: number;
}

export interface ShareResponse {
  share_id: string;
  share_url: string;
  expires_at: string;
  expire_days: number;
}

export interface ShareData {
  title: string;
  slides_html: string[];
  created_at: string;
  view_count: number;
}

/**
 * 创建分享链接
 */
export async function createShare(request: ShareRequest): Promise<ShareResponse> {
  const response = await fetch(`${API_BASE}/ppt/share`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to create share");
  }
  return response.json();
}

/**
 * 获取分享数据
 */
export async function getShareData(shareId: string): Promise<any> {
  const response = await fetch(`${API_BASE}/ppt/share/${shareId}`);
  if (!response.ok) {
    throw new Error("Share not found or expired");
  }
  return response.json();
}

/**
 * 删除分享链接
 */
export async function deleteShare(shareId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/ppt/share/${shareId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("Failed to delete share");
  }
}

/**
 * 获取项目的所有分享链接
 */
export async function getProjectShares(projectId: number): Promise<{ shares: ShareResponse[] }> {
  const response = await fetch(`${API_BASE}/ppt/projects/${projectId}/shares`);
  if (!response.ok) {
    throw new Error("Failed to fetch project shares");
  }
  return response.json();
}

// 重新导出类型，方便其他文件使用
export type {
  Conversation,
  PPTProject,
  PPTVersion,
  PPTSlide,
  Message,
  ToolCall,
  TaskPlan,
  SearchRound,
};

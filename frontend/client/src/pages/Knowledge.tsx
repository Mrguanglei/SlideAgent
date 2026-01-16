/**
 * 知识库页面 - 参考天工 Agent 风格
 * 
 * 功能：
 * - 文件上传（拖拽/点击，支持批量，需确认后上传）
 * - 文件夹管理
 * - 文档列表展示
 * - 文档状态显示（解析中/已完成/失败）
 * - 文档操作（重命名/移动/删除/下载）
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { useLocation } from "wouter";
import { toast } from "sonner";
import ConversationSidebar from "@/components/ConversationSidebar";
import type { Conversation } from "@/types";
import { getConversations, deleteConversation } from "@/lib/api";
import {
  Upload,
  FolderPlus,
  File,
  FileText,
  FileSpreadsheet,
  Globe,
  MoreHorizontal,
  Trash2,
  Download,
  Edit3,
  FolderInput,
  Plus,
  X,
  Link,
  Type,
  Loader2,
  CheckCircle,
  XCircle,
  RefreshCw,
  ChevronRight,
  Folder,
  Clock,
  FileUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

// API 基础 URL
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// 类型定义
interface KnowledgeFolder {
  id: number;
  name: string;
  parent_id: number | null;
  created_at: string;
}

interface KnowledgeDocument {
  id: number;
  filename: string;
  display_name: string | null;
  file_type: string;
  file_size: number | null;
  parse_status: "pending" | "parsing" | "completed" | "failed";
  parse_error: string | null;
  chunk_count: number;
  keywords: string[] | null;
  summary: string | null;
  created_at: string;
  updated_at: string;
}

interface PendingFile {
  id: string;
  file: File;
  name: string;
  size: number;
}

// 文件类型图标映射
const FILE_TYPE_ICONS: Record<string, React.ReactNode> = {
  pdf: <FileText className="h-10 w-10 text-red-500" />,
  docx: <FileText className="h-10 w-10 text-blue-500" />,
  doc: <FileText className="h-10 w-10 text-blue-500" />,
  xlsx: <FileSpreadsheet className="h-10 w-10 text-green-500" />,
  xls: <FileSpreadsheet className="h-10 w-10 text-green-500" />,
  txt: <File className="h-10 w-10 text-gray-500" />,
  md: <File className="h-10 w-10 text-gray-600" />,
  html: <Globe className="h-10 w-10 text-orange-500" />,
  url: <Link className="h-10 w-10 text-purple-500" />,
  text: <Type className="h-10 w-10 text-gray-500" />,
};

// 格式化文件大小
function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === 0) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

// 格式化时间
function formatTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  
  if (diff < 60000) return "刚刚";
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
  if (diff < 604800000) return `${Math.floor(diff / 86400000)} 天前`;
  
  return date.toLocaleDateString("zh-CN");
}

export default function Knowledge() {
  const [, setLocation] = useLocation();
  
  // 侧边栏状态
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  
  // 加载对话列表
  useEffect(() => {
    const loadConversations = async () => {
      try {
        const data = await getConversations();
        setConversations(data);
      } catch (error) {
        console.error("加载对话列表失败:", error);
      }
    };
    loadConversations();
  }, []);
  
  // 删除对话
  const handleDeleteConversation = async (id: number) => {
    try {
      await deleteConversation(id);
      setConversations(prev => prev.filter(c => c.id !== id));
    } catch (error) {
      console.error("删除对话失败:", error);
    }
  };
  
  // 状态
  const [folders, setFolders] = useState<KnowledgeFolder[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [currentFolderId, setCurrentFolderId] = useState<number | null>(null);
  const [folderPath, setFolderPath] = useState<KnowledgeFolder[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  
  // 弹窗状态
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showNewFolderModal, setShowNewFolderModal] = useState(false);
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [showMoveModal, setShowMoveModal] = useState(false);
  const [renameTarget, setRenameTarget] = useState<{ type: "folder" | "document"; id: number; name: string } | null>(null);
  const [moveTarget, setMoveTarget] = useState<{ id: number; name: string } | null>(null);
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(null);
  const [allFolders, setAllFolders] = useState<KnowledgeFolder[]>([]);
  const [showNewFolderInput, setShowNewFolderInput] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  
  // 上传状态
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);
  const [urlInput, setUrlInput] = useState("");
  const [textInput, setTextInput] = useState("");
  const [textTitle, setTextTitle] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const prevParsingCountRef = useRef<number>(0);

  // 加载数据
  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      // 加载文件夹
      const foldersRes = await fetch(
        `${API_BASE}/api/knowledge/folders${currentFolderId ? `?parent_id=${currentFolderId}` : ""}`
      );
      const foldersData = await foldersRes.json();
      setFolders(foldersData);

      // 加载文档
      const docsRes = await fetch(
        `${API_BASE}/api/knowledge/documents${currentFolderId ? `?folder_id=${currentFolderId}` : ""}`
      );
      const docsData = await docsRes.json();
      setDocuments(docsData);
    } catch (error) {
      console.error("加载数据失败:", error);
    } finally {
      setIsLoading(false);
    }
  }, [currentFolderId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // 定时刷新解析中的文档
  useEffect(() => {
    const parsingDocs = documents.filter(d => d.parse_status === "parsing" || d.parse_status === "pending");
    const parsingCount = parsingDocs.length;

    // 只有当解析中文档数量变化时才重新设置定时器
    if (parsingCount !== prevParsingCountRef.current) {
      prevParsingCountRef.current = parsingCount;

      // 清除之前的定时器
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }

      // 只有当有解析中的文档时才启动轮询
      if (parsingCount > 0) {
        pollingTimerRef.current = setInterval(() => {
          loadData();
        }, 3000);
      }
    }
  }, [documents, loadData]);

  // 组件卸载时清理定时器
  useEffect(() => {
    return () => {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    };
  }, []);
  
  // 进入文件夹
  const enterFolder = (folder: KnowledgeFolder) => {
    setFolderPath([...folderPath, folder]);
    setCurrentFolderId(folder.id);
  };
  
  // 返回上级
  const goBack = (index: number) => {
    if (index < 0) {
      setFolderPath([]);
      setCurrentFolderId(null);
    } else {
      setFolderPath(folderPath.slice(0, index + 1));
      setCurrentFolderId(folderPath[index].id);
    }
  };
  
  // 创建文件夹
  const createFolder = async (name: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/folders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, parent_id: currentFolderId }),
      });

      if (!res.ok) {
        const error = await res.json();
        toast.error(error.detail || "创建文件夹失败");
        return;
      }

      loadData();
      setShowNewFolderModal(false);
    } catch (error) {
      console.error("创建文件夹失败:", error);
      toast.error("创建文件夹失败，请检查网络连接");
    }
  };

  // 在移动对话框中创建文件夹
  const createFolderInMoveDialog = async () => {
    if (!newFolderName.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/folders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newFolderName.trim(), parent_id: null }),
      });

      if (!res.ok) {
        const error = await res.json();
        toast.error(error.detail || "创建文件夹失败");
        return;
      }

      const newFolder = await res.json();
      await loadAllFolders();
      setSelectedFolderId(newFolder.id);
      setShowNewFolderInput(false);
      setNewFolderName("");
    } catch (error) {
      console.error("创建文件夹失败:", error);
      toast.error("创建文件夹失败，请检查网络连接");
    }
  };
  
  // 添加待上传文件
  const addPendingFiles = (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    const newPendingFiles: PendingFile[] = fileArray.map((file, index) => ({
      id: `${Date.now()}-${index}`,
      file,
      name: file.name,
      size: file.size,
    }));
    setPendingFiles(prev => [...prev, ...newPendingFiles]);
  };
  
  // 移除待上传文件
  const removePendingFile = (id: string) => {
    setPendingFiles(prev => prev.filter(f => f.id !== id));
  };
  
  // 确认上传所有文件
  const confirmUpload = async () => {
    if (pendingFiles.length === 0 && !urlInput.trim() && !textInput.trim()) return;
    
    setIsUploading(true);
    
    try {
      // 上传文件
      for (const pendingFile of pendingFiles) {
        const formData = new FormData();
        formData.append("file", pendingFile.file);
        if (currentFolderId) {
          formData.append("folder_id", currentFolderId.toString());
        }
        
        await fetch(`${API_BASE}/api/knowledge/documents/upload`, {
          method: "POST",
          body: formData,
        });
      }
      
      // 上传 URL
      if (urlInput.trim()) {
        await fetch(`${API_BASE}/api/knowledge/documents/url`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: urlInput, folder_id: currentFolderId }),
        });
      }
      
      // 上传文本
      if (textInput.trim()) {
        await fetch(`${API_BASE}/api/knowledge/documents/text`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            text: textInput, 
            title: textTitle || "文本内容",
            folder_id: currentFolderId 
          }),
        });
      }
      
      // 清空并关闭
      setPendingFiles([]);
      setUrlInput("");
      setTextInput("");
      setTextTitle("");
      setShowUploadModal(false);
      loadData();
    } catch (error) {
      console.error("上传失败:", error);
    } finally {
      setIsUploading(false);
    }
  };
  
  // 重命名
  const handleRename = async (newName: string) => {
    if (!renameTarget) return;
    try {
      const endpoint = renameTarget.type === "folder" 
        ? `${API_BASE}/api/knowledge/folders/${renameTarget.id}`
        : `${API_BASE}/api/knowledge/documents/${renameTarget.id}/rename`;
      
      await fetch(endpoint, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName }),
      });
      loadData();
      setShowRenameModal(false);
      setRenameTarget(null);
    } catch (error) {
      console.error("重命名失败:", error);
    }
  };
  
  // 删除文件夹
  const deleteFolder = async (id: number) => {
    if (!confirm("确定要删除此文件夹吗？文件夹内的所有文档也会被删除。")) return;
    try {
      await fetch(`${API_BASE}/api/knowledge/folders/${id}`, { method: "DELETE" });
      loadData();
    } catch (error) {
      console.error("删除文件夹失败:", error);
    }
  };
  
  // 删除文档
  const deleteDocument = async (id: number) => {
    if (!confirm("确定要删除此文档吗？")) return;
    try {
      await fetch(`${API_BASE}/api/knowledge/documents/${id}`, { method: "DELETE" });
      loadData();
    } catch (error) {
      console.error("删除文档失败:", error);
    }
  };
  
  // 下载文档
  const downloadDocument = async (doc: KnowledgeDocument) => {
    window.open(`${API_BASE}/api/knowledge/documents/${doc.id}/download`, "_blank");
  };

  // 加载所有文件夹（用于移动对话框）
  const loadAllFolders = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/folders`);
      const data = await res.json();
      setAllFolders(data);
    } catch (error) {
      console.error("加载文件夹失败:", error);
    }
  };

  // 打开移动对话框
  const openMoveDialog = async (doc: KnowledgeDocument) => {
    setMoveTarget({ id: doc.id, name: doc.display_name || doc.filename });
    setSelectedFolderId(null);
    await loadAllFolders();
    setShowMoveModal(true);
  };

  // 移动文档
  const handleMoveDocument = async () => {
    if (!moveTarget) return;
    try {
      await fetch(`${API_BASE}/api/knowledge/documents/${moveTarget.id}/move`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder_id: selectedFolderId }),
      });
      loadData();
      setShowMoveModal(false);
      setMoveTarget(null);
      setSelectedFolderId(null);
    } catch (error) {
      console.error("移动文档失败:", error);
    }
  };
  
  // 重新处理文档
  const reprocessDocument = async (id: number) => {
    try {
      await fetch(`${API_BASE}/api/knowledge/documents/${id}/reprocess`, { method: "POST" });
      loadData();
    } catch (error) {
      console.error("重新处理失败:", error);
    }
  };
  
  // 拖拽处理
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };
  
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };
  
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      addPendingFiles(files);
    }
  };
  
  // 渲染解析状态
  const renderParseStatus = (doc: KnowledgeDocument) => {
    switch (doc.parse_status) {
      case "pending":
        return (
          <div className="flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded-full">
            <Clock className="h-3 w-3" />
            <span>等待中</span>
          </div>
        );
      case "parsing":
        return (
          <div className="flex items-center gap-1.5 text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded-full">
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>解析中</span>
          </div>
        );
      case "completed":
        return (
          <div className="flex items-center gap-1.5 text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full">
            <CheckCircle className="h-3 w-3" />
            <span>{doc.chunk_count} 块</span>
          </div>
        );
      case "failed":
        return (
          <div className="flex items-center gap-1.5 text-xs text-red-600 bg-red-50 px-2 py-1 rounded-full" title={doc.parse_error || "解析失败"}>
            <XCircle className="h-3 w-3" />
            <span>失败</span>
          </div>
        );
      default:
        return null;
    }
  };
  
  return (
    <div className="h-screen flex overflow-hidden">
      {/* 侧边栏 */}
      <ConversationSidebar
        conversations={conversations}
        currentConversationId={null}
        onSelectConversation={(conv) => setLocation(`/?conversation=${conv.id}`)}
        onDeleteConversation={handleDeleteConversation}
        onNewChat={() => setLocation("/")}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />
      
      {/* 主内容区 */}
      <div className="flex-1 flex flex-col bg-gray-50 overflow-hidden">
        {/* 头部 */}
        <div className="flex-shrink-0 px-6 py-4 bg-white border-b">
          <h1 className="text-xl font-bold mb-4">知识库</h1>
          
          {/* 操作按钮 */}
          <div className="flex items-center gap-2">
            <Button onClick={() => setShowUploadModal(true)} size="sm" className="gap-1.5">
              <Upload className="h-4 w-4" />
              上传文件
            </Button>
            <Button variant="outline" size="sm" onClick={() => setShowNewFolderModal(true)} className="gap-1.5">
              <Plus className="h-4 w-4" />
              新建文件夹
            </Button>
          </div>
          
          {/* 面包屑导航 */}
          {folderPath.length > 0 && (
            <div className="flex items-center gap-1 mt-3 text-sm">
              <button 
                onClick={() => goBack(-1)}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                知识库
              </button>
              {folderPath.map((folder, index) => (
                <div key={folder.id} className="flex items-center gap-1">
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  <button
                    onClick={() => goBack(index)}
                    className={cn(
                      "transition-colors",
                      index === folderPath.length - 1 
                        ? "font-medium text-foreground" 
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {folder.name}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
        
        {/* 内容区 */}
        <div className="flex-1 overflow-auto p-6">
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : folders.length === 0 && documents.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-24 h-24 bg-primary/5 rounded-full flex items-center justify-center mb-4">
                <FileText className="h-12 w-12 text-primary/40" />
              </div>
              <p className="text-muted-foreground mb-4">暂无文件，请上传</p>
              <Button onClick={() => setShowUploadModal(true)} className="gap-2">
                <Upload className="h-4 w-4" />
                上传文件
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
              {/* 文件夹 */}
              {folders.map(folder => (
                <div
                  key={`folder-${folder.id}`}
                  className="group bg-white rounded-xl border p-4 cursor-pointer hover:shadow-md hover:border-primary/30 transition-all"
                  onDoubleClick={() => enterFolder(folder)}
                >
                  <div className="flex items-start justify-between mb-3">
                    <Folder className="h-10 w-10 text-amber-400" />
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="p-1 rounded hover:bg-gray-100 opacity-0 group-hover:opacity-100 transition-opacity">
                          <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => enterFolder(folder)}>
                          <FolderInput className="h-4 w-4 mr-2" />
                          打开
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => {
                          setRenameTarget({ type: "folder", id: folder.id, name: folder.name });
                          setShowRenameModal(true);
                        }}>
                          <Edit3 className="h-4 w-4 mr-2" />
                          重命名
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem 
                          onClick={() => deleteFolder(folder.id)}
                          className="text-red-500 focus:text-red-500"
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          删除
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                  <h3 className="font-medium text-sm truncate">{folder.name}</h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    {formatTime(folder.created_at)}
                  </p>
                </div>
              ))}
              
              {/* 文档 */}
              {documents.map(doc => (
                <div
                  key={`doc-${doc.id}`}
                  className="group bg-white rounded-xl border p-4 hover:shadow-md hover:border-primary/30 transition-all"
                >
                  <div className="flex items-start justify-between mb-3">
                    <span className="text-xs text-muted-foreground">
                      {formatTime(doc.created_at)}
                    </span>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="p-1 rounded hover:bg-gray-100 opacity-0 group-hover:opacity-100 transition-opacity">
                          <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => {
                          setRenameTarget({
                            type: "document",
                            id: doc.id,
                            name: doc.display_name || doc.filename
                          });
                          setShowRenameModal(true);
                        }}>
                          <Edit3 className="h-4 w-4 mr-2" />
                          重命名
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => openMoveDialog(doc)}>
                          <FolderInput className="h-4 w-4 mr-2" />
                          移动到
                        </DropdownMenuItem>
                        {doc.file_type !== "url" && doc.file_type !== "text" && (
                          <DropdownMenuItem onClick={() => downloadDocument(doc)}>
                            <Download className="h-4 w-4 mr-2" />
                            下载
                          </DropdownMenuItem>
                        )}
                        {(doc.parse_status === "failed" || doc.parse_status === "pending") && (
                          <DropdownMenuItem onClick={() => reprocessDocument(doc.id)}>
                            <RefreshCw className="h-4 w-4 mr-2" />
                            重新解析
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() => deleteDocument(doc.id)}
                          className="text-red-500 focus:text-red-500"
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          删除
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                  
                  <div className="mb-3">
                    {FILE_TYPE_ICONS[doc.file_type] || <File className="h-10 w-10 text-gray-400" />}
                  </div>
                  
                  <h3 className="font-medium text-sm truncate mb-2" title={doc.display_name || doc.filename}>
                    {doc.display_name || doc.filename}
                  </h3>
                  
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">
                      .{doc.file_type} {formatFileSize(doc.file_size)}
                    </span>
                    {renderParseStatus(doc)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      
      {/* 上传弹窗 */}
      <Dialog open={showUploadModal} onOpenChange={(open) => {
        setShowUploadModal(open);
        if (!open) {
          setPendingFiles([]);
          setUrlInput("");
          setTextInput("");
          setTextTitle("");
        }
      }}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>上传</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4">
            {/* 文件上传区域 */}
            <div
              className={cn(
                "border-2 border-dashed rounded-xl p-6 text-center transition-all cursor-pointer",
                isDragging 
                  ? "border-primary bg-primary/5" 
                  : "border-gray-200 hover:border-primary/50 hover:bg-gray-50"
              )}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <FileUp className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">拖动或点击上传</p>
              <p className="text-xs text-muted-foreground/70 mt-1">
                支持 PDF、Word、Excel、TXT、Markdown 等格式
              </p>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.md,.html,.htm,.xml"
                multiple
                onChange={(e) => {
                  const files = e.target.files;
                  if (files && files.length > 0) {
                    addPendingFiles(files);
                  }
                  e.target.value = "";
                }}
              />
            </div>
            
            {/* 待上传文件列表 */}
            {pendingFiles.length > 0 && (
              <div className="space-y-2 max-h-40 overflow-auto">
                {pendingFiles.map(file => (
                  <div 
                    key={file.id} 
                    className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <File className="h-4 w-4 text-muted-foreground shrink-0" />
                      <span className="text-sm truncate">{file.name}</span>
                      <span className="text-xs text-muted-foreground shrink-0">
                        {formatFileSize(file.size)}
                      </span>
                    </div>
                    <button 
                      onClick={() => removePendingFile(file.id)}
                      className="p-1 hover:bg-gray-200 rounded transition-colors"
                    >
                      <X className="h-4 w-4 text-muted-foreground" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            
            {/* 分隔线 */}
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-200" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-white px-2 text-muted-foreground">或</span>
              </div>
            </div>
            
            {/* URL 输入 */}
            <div className="flex gap-2">
              <Input
                placeholder="粘贴链接"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                className="flex-1"
              />
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => {}}
                disabled={!urlInput.trim()}
                className="shrink-0"
              >
                添加网站
              </Button>
            </div>
            
            {/* 文本输入 */}
            <div className="space-y-2">
              <Textarea
                placeholder="粘贴文本"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                rows={3}
                className="resize-none"
              />
              {textInput.trim() && (
                <div className="flex justify-end">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => {}}
                    disabled={!textInput.trim()}
                  >
                    添加文字
                  </Button>
                </div>
              )}
            </div>
          </div>
          
          <DialogFooter className="mt-4">
            <Button 
              variant="outline" 
              onClick={() => setShowUploadModal(false)}
            >
              取消
            </Button>
            <Button 
              onClick={confirmUpload}
              disabled={isUploading || (pendingFiles.length === 0 && !urlInput.trim() && !textInput.trim())}
              className="gap-2"
            >
              {isUploading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  上传中...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4" />
                  确定上传
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      {/* 新建文件夹弹窗 */}
      <Dialog open={showNewFolderModal} onOpenChange={setShowNewFolderModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>新建文件夹</DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => {
            e.preventDefault();
            const formData = new FormData(e.currentTarget);
            const name = formData.get("name") as string;
            if (name.trim()) createFolder(name.trim());
          }}>
            <Input
              name="name"
              placeholder="文件夹名称"
              autoFocus
            />
            <DialogFooter className="mt-4">
              <Button type="button" variant="outline" onClick={() => setShowNewFolderModal(false)}>
                取消
              </Button>
              <Button type="submit">创建</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      
      {/* 重命名弹窗 */}
      <Dialog open={showRenameModal} onOpenChange={setShowRenameModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>重命名</DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => {
            e.preventDefault();
            const formData = new FormData(e.currentTarget);
            const name = formData.get("name") as string;
            if (name.trim()) handleRename(name.trim());
          }}>
            <Input
              name="name"
              placeholder="新名称"
              defaultValue={renameTarget?.name}
              autoFocus
            />
            <DialogFooter className="mt-4">
              <Button type="button" variant="outline" onClick={() => setShowRenameModal(false)}>
                取消
              </Button>
              <Button type="submit">确定</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* 移动到弹窗 */}
      <Dialog open={showMoveModal} onOpenChange={setShowMoveModal}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>移动到</DialogTitle>
          </DialogHeader>

          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              将 <span className="font-medium text-foreground">{moveTarget?.name}</span> 移动到：
            </p>

            {/* 文件夹列表 */}
            <div className="min-h-[350px] max-h-[450px] overflow-auto space-y-2 border rounded-lg p-3 bg-gray-50/50">
              {/* 新建文件夹输入框 */}
              {showNewFolderInput && (
                <div className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg border border-primary bg-white">
                  <Folder className="h-4 w-4 text-amber-400 shrink-0" />
                  <Input
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        createFolderInMoveDialog();
                      } else if (e.key === "Escape") {
                        setShowNewFolderInput(false);
                        setNewFolderName("");
                      }
                    }}
                    onBlur={() => {
                      if (!newFolderName.trim()) {
                        setShowNewFolderInput(false);
                      }
                    }}
                    placeholder="输入文件夹名称"
                    autoFocus
                    className="h-7 text-sm border-0 focus-visible:ring-0 px-0"
                  />
                </div>
              )}

              {/* 文件夹列表 */}
              {allFolders.map(folder => (
                <div
                  key={folder.id}
                  onClick={() => setSelectedFolderId(folder.id)}
                  className={cn(
                    "flex items-center gap-2.5 px-3 py-2.5 rounded-lg border cursor-pointer transition-all bg-white",
                    selectedFolderId === folder.id
                      ? "border-primary bg-primary/5"
                      : "border-gray-200 hover:border-primary/50 hover:bg-gray-50"
                  )}
                >
                  <Folder className="h-4 w-4 text-amber-400 shrink-0" />
                  <span className="text-sm">{folder.name}</span>
                </div>
              ))}
            </div>
          </div>

          <DialogFooter className="mt-4 sm:justify-between">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowNewFolderInput(true)}
              className="gap-2"
            >
              <Plus className="h-4 w-4" />
              新建文件夹
            </Button>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => setShowMoveModal(false)}
              >
                取消
              </Button>
              <Button onClick={handleMoveDocument}>
                移动到
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

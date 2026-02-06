/**
 * 历史对话侧边栏组件 - 天工 Agent 风格
 */

import { useState } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  MessageSquarePlus,
  MessageSquare,
  Trash2,
  ChevronRight,
  FileSliders,
  Clock,
  PanelLeftClose,
  Search,
  BookOpen,
  MoreHorizontal,
  Pin,
  Pencil,
} from "lucide-react";
import { useLocation } from "wouter";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { Conversation } from "@/types";
import SearchDialog from "./SearchDialog";

interface ConversationSidebarProps {
  conversations: Conversation[];
  currentConversationId: number | null;
  onSelectConversation: (conversation: Conversation) => void;
  onDeleteConversation: (conversationId: number) => void;
  onRenameConversation?: (conversationId: number, newTitle: string) => void;
  onPinConversation?: (conversationId: number, pinned: boolean) => void;
  onNewChat: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export default function ConversationSidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onDeleteConversation,
  onRenameConversation,
  onPinConversation,
  onNewChat,
  collapsed,
  onToggleCollapse,
}: ConversationSidebarProps) {
  const [location, setLocation] = useLocation();
  const [searchOpen, setSearchOpen] = useState(false);
  const isKnowledgeActive = location === "/knowledge-base";

  // 删除确认弹窗状态
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [conversationToDelete, setConversationToDelete] = useState<number | null>(null);

  // 重命名弹窗状态
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [conversationToRename, setConversationToRename] = useState<number | null>(null);
  const [newTitle, setNewTitle] = useState("");

  // 菜单打开状态
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);

  const handleDeleteClick = (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    setConversationToDelete(id);
    setDeleteDialogOpen(true);
    setOpenMenuId(null);
  };

  const handleConfirmDelete = () => {
    if (conversationToDelete !== null) {
      onDeleteConversation(conversationToDelete);
      setDeleteDialogOpen(false);
      setConversationToDelete(null);
    }
  };

  const handleRenameClick = (e: React.MouseEvent, conv: Conversation) => {
    e.stopPropagation();
    setConversationToRename(conv.id);
    setNewTitle(conv.title);
    setRenameDialogOpen(true);
    setOpenMenuId(null);
  };

  const handleConfirmRename = () => {
    if (conversationToRename !== null && onRenameConversation && newTitle.trim()) {
      onRenameConversation(conversationToRename, newTitle.trim());
      setRenameDialogOpen(false);
      setConversationToRename(null);
      setNewTitle("");
    }
  };

  const handlePinClick = (e: React.MouseEvent, conv: Conversation) => {
    e.stopPropagation();
    if (onPinConversation) {
      onPinConversation(conv.id, !(conv as any).pinned);
    }
    setOpenMenuId(null);
  };

  if (collapsed) {
    return (
      <button
        onClick={onToggleCollapse}
        className="absolute left-0 top-1/2 -translate-y-1/2 z-10 w-6 h-12 bg-gray-100 hover:bg-gray-200 border border-l-0 border-border rounded-r-lg flex items-center justify-center transition-colors"
        title="展开侧边栏"
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    );
  }

  return (
    <>
      <div className="w-52 h-full bg-gray-50/80 border-r border-border flex flex-col shrink-0">
        {/* 顶部 Logo + 折叠按钮 */}
        <div className="h-14 flex items-center justify-between px-3 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-primary rounded-lg flex items-center justify-center">
              <FileSliders className="h-3.5 w-3.5 text-white" />
            </div>
            <span className="font-bold text-sm">SlideAgent</span>
          </div>
          <button
            onClick={onToggleCollapse}
            className="p-1 hover:bg-gray-200 rounded-lg transition-colors"
            title="收起侧边栏"
          >
            <PanelLeftClose className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>

        {/* 搜索框 */}
        <div className="px-2 py-1">
          <button
            onClick={() => setSearchOpen(true)}
            className="w-full flex items-center gap-2 px-2.5 py-2 bg-gray-100/80 hover:bg-gray-200/80 rounded-lg transition-colors text-muted-foreground"
          >
            <Search className="h-3.5 w-3.5" />
            <span className="text-xs flex-1 text-left">搜索 (⌘+k)</span>
          </button>
        </div>

        {/* 新建对话按钮 */}
        <div className="px-2 py-1.5">
          <button
            onClick={onNewChat}
            className="w-full flex items-center gap-2 px-2.5 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors shadow-sm"
          >
            <MessageSquarePlus className="h-4 w-4" />
            <span className="text-sm font-medium">新建对话</span>
          </button>
        </div>

        {/* 最近对话标题 */}
        <div className="px-3 py-1.5 flex items-center gap-2">
          <Clock className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs font-medium text-muted-foreground">最近对话</span>
        </div>

        {/* 对话列表 */}
        <ScrollArea className="flex-1 px-2">
          {conversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-6 text-center">
              <MessageSquare className="h-6 w-6 text-muted-foreground/50 mb-2" />
              <span className="text-xs text-muted-foreground">暂无对话</span>
              <span className="text-xs text-muted-foreground/70 mt-0.5">
                开始新对话来创建 PPT
              </span>
            </div>
          ) : (
            <div className="space-y-0.5 pb-4">
              {conversations.map(conv => (
                <div
                  key={conv.id}
                  className={cn(
                    "group relative flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer transition-colors",
                    currentConversationId === conv.id
                      ? "bg-primary/10 text-primary"
                      : "hover:bg-gray-100"
                  )}
                  onClick={() => onSelectConversation(conv)}
                >
                  {/* 置顶图标 */}
                  {(conv as any).pinned && (
                    <Pin className="h-3 w-3 shrink-0 text-primary" />
                  )}

                  {/* 图标 */}
                  {!(conv as any).pinned && (
                    conv.has_ppt ? (
                      <FileSliders className="h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                    )
                  )}

                  {/* 运行中动画指示器 */}
                  {conv.task_status === "running" && (
                    <span className="relative flex h-2 w-2 shrink-0">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                    </span>
                  )}

                  {/* 标题 */}
                  <span className="flex-1 text-xs truncate">
                    {conv.title}
                  </span>

                  {/* 三点菜单按钮 */}
                  <Popover open={openMenuId === conv.id} onOpenChange={(open) => setOpenMenuId(open ? conv.id : null)}>
                    <PopoverTrigger asChild>
                      <button
                        onClick={(e) => e.stopPropagation()}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-gray-200 transition-all"
                      >
                        <MoreHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-36 p-1" align="end" side="right">
                      <div className="flex flex-col">
                        {/* 置顶/取消置顶 */}
                        <button
                          onClick={(e) => handlePinClick(e, conv)}
                          className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-100 rounded-md transition-colors text-left"
                        >
                          <Pin className="h-4 w-4" />
                          <span>{(conv as any).pinned ? "取消置顶" : "置顶对话"}</span>
                        </button>
                        {/* 重命名 */}
                        <button
                          onClick={(e) => handleRenameClick(e, conv)}
                          className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-100 rounded-md transition-colors text-left"
                        >
                          <Pencil className="h-4 w-4" />
                          <span>重命名</span>
                        </button>
                        {/* 删除 */}
                        <button
                          onClick={(e) => handleDeleteClick(e, conv.id)}
                          className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-red-50 text-red-600 rounded-md transition-colors text-left"
                        >
                          <Trash2 className="h-4 w-4" />
                          <span>删除</span>
                        </button>
                      </div>
                    </PopoverContent>
                  </Popover>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>

        {/* 底部功能区 - 知识库 */}
        <div className="border-t border-border p-2">
          <button
            onClick={() => setLocation("/knowledge-base")}
            className={cn(
              "w-full flex items-center gap-2 px-2.5 py-2 rounded-lg transition-colors text-sm",
              isKnowledgeActive
                ? "bg-primary/10 text-primary"
                : "hover:bg-gray-100 text-muted-foreground hover:text-foreground"
            )}
          >
            <BookOpen className={cn("h-4 w-4", isKnowledgeActive && "text-primary")} />
            <span className="font-medium">知识库</span>
          </button>
        </div>
      </div>

      {/* 搜索弹窗 */}
      <SearchDialog open={searchOpen} onOpenChange={setSearchOpen} />


      {/* 删除确认弹窗 */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除对话</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除这个对话吗？此操作无法撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 重命名弹窗 */}
      <AlertDialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>重命名对话</AlertDialogTitle>
            <AlertDialogDescription>
              请输入新的对话名称
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-4">
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="w-full px-3 py-2 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20"
              placeholder="请输入对话名称"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleConfirmRename();
                }
              }}
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmRename} disabled={!newTitle.trim()}>
              确定
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

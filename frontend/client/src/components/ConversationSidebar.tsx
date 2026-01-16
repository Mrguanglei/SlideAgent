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
} from "lucide-react";
import { useLocation } from "wouter";
import type { Conversation } from "@/types";
import SearchDialog from "./SearchDialog";

interface ConversationSidebarProps {
  conversations: Conversation[];
  currentConversationId: number | null;
  onSelectConversation: (conversation: Conversation) => void;
  onDeleteConversation: (conversationId: number) => void;
  onNewChat: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export default function ConversationSidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onDeleteConversation,
  onNewChat,
  collapsed,
  onToggleCollapse,
}: ConversationSidebarProps) {
  const [location, setLocation] = useLocation();
  const [searchOpen, setSearchOpen] = useState(false);
  const isKnowledgeActive = location === "/knowledge-base";

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
                  {/* 图标 */}
                  {conv.has_ppt ? (
                    <FileSliders className="h-3.5 w-3.5 shrink-0" />
                  ) : (
                    <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                  )}

                  {/* 标题 */}
                  <span className="flex-1 text-xs truncate">
                    {conv.title}
                  </span>

                  {/* 删除按钮 */}
                  <button
                    onClick={e => {
                      e.stopPropagation();
                      if (confirm("确定要删除这个对话吗？")) {
                        onDeleteConversation(conv.id);
                      }
                    }}
                    className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-100 hover:text-red-600 transition-all"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
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
    </>
  );
}

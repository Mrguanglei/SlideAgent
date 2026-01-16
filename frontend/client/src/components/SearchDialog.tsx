/**
 * 全局搜索弹窗组件 - 天工 Agent 风格
 * 
 * 功能：
 * - 全屏居中弹窗
 * - 实时搜索（防抖）
 * - 搜索对话和 PPT 项目
 * - 关键词高亮
 * - 点击跳转
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { useLocation } from "wouter";
import { cn } from "@/lib/utils";
import { 
  Search, 
  X, 
  Loader2, 
  MessageSquare, 
  FileSliders,
  Zap,
  FileText,
} from "lucide-react";

// API 基础 URL
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// 搜索结果类型
interface SearchResult {
  id: number;
  title: string;
  type: "conversation" | "ppt";
  has_ppt?: boolean;
  conversation_id?: number;
  slide_count?: number;
  created_at: string;
  updated_at?: string;
}

interface SearchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// 防抖 Hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

// 高亮关键词
function highlightKeyword(text: string, keyword: string): React.ReactNode {
  if (!keyword.trim()) return text;
  
  const regex = new RegExp(`(${keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  const parts = text.split(regex);
  
  return parts.map((part, index) => 
    regex.test(part) ? (
      <span key={index} className="text-primary font-medium">{part}</span>
    ) : (
      part
    )
  );
}

export default function SearchDialog({ open, onOpenChange }: SearchDialogProps) {
  const [, setLocation] = useLocation();
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  
  const debouncedQuery = useDebounce(query, 300);
  
  // 搜索
  const search = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([]);
      setHasSearched(false);
      return;
    }
    
    setIsLoading(true);
    setHasSearched(true);
    
    try {
      const response = await fetch(
        `${API_BASE}/api/conversations/search/global?q=${encodeURIComponent(searchQuery)}`
      );
      const data = await response.json();
      
      // 合并结果
      const allResults: SearchResult[] = [
        ...data.conversations,
        ...data.ppt_projects,
      ];
      
      setResults(allResults);
    } catch (error) {
      console.error("搜索失败:", error);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  // 监听防抖后的查询
  useEffect(() => {
    search(debouncedQuery);
  }, [debouncedQuery, search]);
  
  // 打开时聚焦输入框
  useEffect(() => {
    if (open) {
      setTimeout(() => {
        inputRef.current?.focus();
      }, 100);
    } else {
      // 关闭时清空
      setQuery("");
      setResults([]);
      setHasSearched(false);
    }
  }, [open]);
  
  // 键盘快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl + K 打开搜索
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
      // ESC 关闭
      if (e.key === "Escape" && open) {
        onOpenChange(false);
      }
    };
    
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onOpenChange]);
  
  // 点击结果
  const handleResultClick = (result: SearchResult) => {
    onOpenChange(false);
    
    if (result.type === "conversation") {
      setLocation(`/?conversation=${result.id}`);
    } else if (result.type === "ppt" && result.conversation_id) {
      setLocation(`/?conversation=${result.conversation_id}`);
    }
  };
  
  if (!open) return null;
  
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
      {/* 背景遮罩 */}
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />
      
      {/* 搜索弹窗 */}
      <div className="relative w-full max-w-2xl mx-4 bg-white rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* 搜索输入框 */}
        <div className="flex items-center gap-3 px-5 py-4 border-b">
          <Search className="h-5 w-5 text-muted-foreground shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索"
            className="flex-1 text-lg outline-none placeholder:text-muted-foreground/60"
          />
          <button
            onClick={() => onOpenChange(false)}
            className="p-1.5 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="h-5 w-5 text-muted-foreground" />
          </button>
        </div>
        
        {/* 搜索结果区域 */}
        <div className="max-h-[50vh] overflow-auto">
          {isLoading ? (
            // 加载中
            <div className="flex flex-col items-center justify-center py-16">
              <div className="relative">
                <div className="w-12 h-12 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-full flex items-center justify-center">
                  <Search className="h-6 w-6 text-white animate-pulse" />
                </div>
                <Loader2 className="absolute -top-1 -right-1 h-5 w-5 text-primary animate-spin" />
              </div>
              <p className="mt-4 text-muted-foreground">加载中</p>
            </div>
          ) : hasSearched && results.length === 0 ? (
            // 无结果
            <div className="flex flex-col items-center justify-center py-16">
              <div className="w-12 h-12 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-full flex items-center justify-center">
                <Search className="h-6 w-6 text-white" />
              </div>
              <p className="mt-4 text-muted-foreground">无搜索结果</p>
            </div>
          ) : results.length > 0 ? (
            // 搜索结果列表
            <div className="py-2">
              {results.map((result) => (
                <button
                  key={`${result.type}-${result.id}`}
                  onClick={() => handleResultClick(result)}
                  className="w-full flex items-center gap-3 px-5 py-3 hover:bg-gray-50 transition-colors text-left"
                >
                  {/* 图标 */}
                  {result.type === "ppt" ? (
                    <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center shrink-0">
                      <FileText className="h-4 w-4 text-blue-600" />
                    </div>
                  ) : result.has_ppt ? (
                    <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center shrink-0">
                      <FileSliders className="h-4 w-4 text-primary" />
                    </div>
                  ) : (
                    <div className="w-8 h-8 bg-amber-100 rounded-lg flex items-center justify-center shrink-0">
                      <Zap className="h-4 w-4 text-amber-600" />
                    </div>
                  )}
                  
                  {/* 标题 */}
                  <span className="flex-1 truncate">
                    {highlightKeyword(result.title || "未命名", query)}
                  </span>
                  
                  {/* 类型标签 */}
                  <span className="text-xs text-muted-foreground shrink-0">
                    {result.type === "ppt" ? "PPT" : "对话"}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            // 初始状态 - 空白
            <div className="py-16" />
          )}
        </div>
        
        {/* 底部提示 */}
        <div className="px-5 py-3 border-t bg-gray-50/50 flex items-center justify-between text-xs text-muted-foreground">
          <span>输入关键词搜索对话和 PPT</span>
          <div className="flex items-center gap-2">
            <kbd className="px-1.5 py-0.5 bg-gray-100 rounded text-[10px] font-mono">ESC</kbd>
            <span>关闭</span>
          </div>
        </div>
      </div>
    </div>
  );
}

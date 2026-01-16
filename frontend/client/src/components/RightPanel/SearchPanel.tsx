import { useRef, useEffect } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Globe } from "lucide-react";
import type { SearchRound } from "@/types";

interface SearchPanelProps {
  searchRounds: SearchRound[];
  currentSearchRound: number;
  setCurrentSearchRound: (round: number) => void;
  deepThinking: string;
  deepThinkingStreaming: boolean;
}

export default function SearchPanel({
  searchRounds,
  currentSearchRound,
}: SearchPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // 根据 currentSearchRound 获取对应的搜索轮次
  const currentRound = searchRounds.find(r => r.round === currentSearchRound)
    || (searchRounds.length > 0 ? searchRounds[searchRounds.length - 1] : null);

  // 自动滚动到顶部当新搜索开始时
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [currentRound?.round]);

  return (
    <div className="flex flex-col h-full">
      {/* 搜索关键词显示 */}
      {currentRound?.query && (
        <div className="px-4 py-3 border-b border-border">
          <div className="text-xs text-muted-foreground">
            搜索关键词：{currentRound.query}
          </div>
        </div>
      )}

      {/* 搜索结果列表 */}
      <ScrollArea className="flex-1" ref={scrollRef}>
        <div className="p-4 space-y-3">
          {!currentRound ? (
            <div className="text-sm text-muted-foreground text-center py-8">
              暂无搜索结果
            </div>
          ) : currentRound.results.length > 0 ? (
            currentRound.results.map((result, index) => (
              <a
                key={index}
                href={result.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block hover:bg-muted/50 rounded-lg p-3 -mx-1 transition-colors"
              >
                {/* 来源信息 */}
                <div className="flex items-center gap-2 mb-1.5">
                  <div className="w-4 h-4 rounded-full bg-muted flex items-center justify-center">
                    <Globe className="h-2.5 w-2.5 text-muted-foreground" />
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {(() => {
                      try {
                        return new URL(result.url).hostname;
                      } catch {
                        return result.url || "unknown";
                      }
                    })()}
                  </span>
                  {result.date && (
                    <>
                      <span className="text-xs text-muted-foreground">·</span>
                      <span className="text-xs text-muted-foreground">
                        {result.date}
                      </span>
                    </>
                  )}
                </div>

                {/* 标题 */}
                <h4 className="font-medium text-sm mb-1 text-foreground hover:text-primary transition-colors line-clamp-2">
                  {result.title}
                </h4>

                {/* 摘要 */}
                {result.snippet && (
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {result.snippet}
                  </p>
                )}
              </a>
            ))
          ) : (
            <div className="flex items-center justify-center py-8">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                <span>正在搜索...</span>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Image as ImageIcon } from "lucide-react";
import type { ImageSearchRound } from "@/types";

interface ImageSearchPanelProps {
  imageSearchRounds: ImageSearchRound[];
  currentImageSearchRound: number;
  setCurrentImageSearchRound: (round: number) => void;
}

export default function ImageSearchPanel({
  imageSearchRounds,
  currentImageSearchRound,
}: ImageSearchPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const currentRound = imageSearchRounds.find(r => r.round === currentImageSearchRound)
    || (imageSearchRounds.length > 0 ? imageSearchRounds[imageSearchRounds.length - 1] : null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [currentRound?.round]);

  return (
    <div className="flex flex-col h-full">
      {currentRound?.query && (
        <div className="px-4 py-3 border-b border-border">
          <div className="text-xs text-muted-foreground">
            搜索关键词：{currentRound.query}
          </div>
        </div>
      )}

      <ScrollArea className="flex-1" ref={scrollRef}>
        <div className="p-4">
          {!currentRound ? (
            <div className="text-sm text-muted-foreground text-center py-8">
              暂无搜索结果
            </div>
          ) : currentRound.images.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {currentRound.images.map((image, index) => (
                <a
                  key={`${image.url}-${index}`}
                  href={image.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group block"
                >
                  <div className="relative aspect-[4/3] overflow-hidden rounded-lg border bg-muted">
                    <img
                      src={image.url}
                      alt={image.description || `image-${index + 1}`}
                      loading="lazy"
                      className="h-full w-full object-cover transition-transform group-hover:scale-[1.02]"
                    />
                    {(image.width && image.height) && (
                      <div className="absolute bottom-2 right-2 rounded bg-black/60 px-1.5 py-0.5 text-[10px] text-white">
                        {image.width}×{image.height}
                      </div>
                    )}
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground line-clamp-2">
                    {image.description || (() => {
                      try {
                        return new URL(image.url).hostname;
                      } catch {
                        return "未知来源";
                      }
                    })()}
                  </div>
                </a>
              ))}
            </div>
          ) : currentRound.isCompleted ? (
            <div className="text-sm text-muted-foreground text-center py-8">
              未找到相关图片
            </div>
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

      {currentRound && currentRound.images.length > 0 && (
        <div className="px-4 py-2 border-t border-border text-xs text-muted-foreground flex items-center gap-2">
          <ImageIcon className="h-3 w-3" />
          <span>共 {currentRound.images.length} 张图片</span>
        </div>
      )}
    </div>
  );
}

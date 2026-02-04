import { RefObject } from "react";
import ThinkingBlock from "@/components/ThinkingBlock";

interface ThinkBlock {
  content: string;
  status: "thinking" | "completed";
}

function parseThinkTags(content: string): { thinkBlocks: ThinkBlock[]; normalContent: string } {
  const thinkRegex = /<think>([\s\S]*?)<\/think>/gi;
  const thinkBlocks: ThinkBlock[] = [];

  let normalContent = content.replace(thinkRegex, (_match, p1) => {
    thinkBlocks.push({ content: p1.trim(), status: "completed" });
    return "";
  });

  const pendingThinkRegex = /<think>([\s\S]*)$/i;
  const pendingMatch = pendingThinkRegex.exec(normalContent);
  if (pendingMatch) {
    thinkBlocks.push({ content: pendingMatch[1].trim(), status: "thinking" });
    normalContent = normalContent.replace(pendingThinkRegex, "");
  }

  const potentialTagRegex = /<(?:t(?:h(?:i(?:n(?:k)?)?)?)?)?$/i;
  if (potentialTagRegex.test(normalContent) && !normalContent.endsWith(">")) {
    normalContent = normalContent.replace(potentialTagRegex, "");
  }

  return { thinkBlocks, normalContent: normalContent.trim() };
}

interface PPTOutlinePanelProps {
  pptOutline: string;
  pptOutlineStreaming: boolean;
  pptOutlineContentRef: RefObject<HTMLDivElement>;
}

export default function PPTOutlinePanel({
  pptOutline,
  pptOutlineStreaming,
  pptOutlineContentRef,
}: PPTOutlinePanelProps) {
  const { thinkBlocks, normalContent } = parseThinkTags(pptOutline || "");

  return (
    <div className="p-4 space-y-4">
      <div ref={pptOutlineContentRef} className="space-y-3">
        {thinkBlocks.length > 0 && (
          <div className="space-y-2">
            {thinkBlocks.map((block, idx) => (
              <ThinkingBlock
                key={idx}
                content={block.content}
                status={block.status}
                defaultExpanded={block.status === "thinking"}
              />
            ))}
          </div>
        )}
        {normalContent && (
          <div className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
            {normalContent}
            {pptOutlineStreaming && (
              <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-1" />
            )}
          </div>
        )}
      </div>
      {!pptOutline && !pptOutlineStreaming && (
        <div className="text-sm text-muted-foreground text-center py-8">
          等待生成大纲...
        </div>
      )}
    </div>
  );
}

import { RefObject } from "react";

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
  return (
    <div className="p-4 space-y-4">
      <div
        ref={pptOutlineContentRef}
        className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap"
      >
        {pptOutline}
        {pptOutlineStreaming && (
          <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-1" />
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

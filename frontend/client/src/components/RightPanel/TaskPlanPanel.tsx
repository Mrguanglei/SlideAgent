import { RefObject } from "react";
import { Loader2 } from "lucide-react";
import ThinkingBlock from "@/components/ThinkingBlock";
import type { TaskPlan } from "@/types";

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

interface TaskPlanPanelProps {
  taskPlan: TaskPlan | null;
  taskPlanStreaming: boolean;
  taskPlanContentRef: RefObject<HTMLDivElement>;
}

export default function TaskPlanPanel({
  taskPlan,
  taskPlanStreaming,
  taskPlanContentRef,
}: TaskPlanPanelProps) {
  return (
    <div className="p-4 space-y-4">
      {taskPlanStreaming && !taskPlan?.coreRequirement && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>正在分析任务...</span>
        </div>
      )}

      {/* 流式内容显示 */}
      {taskPlan?.streamContent && (() => {
        const { thinkBlocks, normalContent } = parseThinkTags(taskPlan.streamContent);
        return (
          <div ref={taskPlanContentRef} className="space-y-3">
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
                {taskPlanStreaming && (
                  <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-1" />
                )}
              </div>
            )}
          </div>
        );
      })()}

      {/* 结构化内容显示 */}
      {taskPlan && !taskPlan.streamContent && (
        <>
          {/* 核心需求 */}
          {taskPlan.coreRequirement && (
            <div className="space-y-2">
              <h3 className="font-medium text-sm">核心需求</h3>
              <p className="text-sm text-muted-foreground">
                {taskPlan.coreRequirement}
              </p>
            </div>
          )}

          {/* 问题分析 */}
          {taskPlan.problemAnalysis && taskPlan.problemAnalysis.items && (
            <div className="space-y-2">
              <h3 className="font-medium text-sm">
                {taskPlan.problemAnalysis.title || "核心问题识别"}
              </h3>
              <ul className="space-y-1.5">
                {taskPlan.problemAnalysis.items.map((item, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm text-muted-foreground"
                  >
                    <span className="text-primary mt-1">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 信息维度 */}
          {taskPlan.informationDimensions &&
            taskPlan.informationDimensions.items && (
              <div className="space-y-2">
                <h3 className="font-medium text-sm">
                  {taskPlan.informationDimensions.title || "信息需求维度"}
                </h3>
                <ul className="space-y-1.5">
                  {taskPlan.informationDimensions.items.map((item, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm text-muted-foreground"
                    >
                      <span className="text-primary mt-1">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

          {/* 搜索策略 */}
          {taskPlan.searchStrategy && taskPlan.searchStrategy.items && (
            <div className="space-y-2">
              <h3 className="font-medium text-sm">
                {taskPlan.searchStrategy.title || "搜索策略"}
              </h3>
              <ul className="space-y-1.5">
                {taskPlan.searchStrategy.items.map((item, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm text-muted-foreground"
                  >
                    <span className="text-primary mt-1">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 执行步骤 */}
          {taskPlan.steps && taskPlan.steps.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-medium text-sm">执行步骤</h3>
              <div className="space-y-2">
                {taskPlan.steps.map((step, i) => (
                  <div
                    key={step.id || i}
                    className="flex items-start gap-3 text-sm"
                  >
                    <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-xs text-primary font-medium">
                        {i + 1}
                      </span>
                    </div>
                    <span className="text-muted-foreground">{step.text}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

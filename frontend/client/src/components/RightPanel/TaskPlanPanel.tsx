import { RefObject } from "react";
import { Loader2 } from "lucide-react";
import type { TaskPlan } from "@/types";

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
      {taskPlan?.streamContent && (
        <div
          ref={taskPlanContentRef}
          className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap"
        >
          {taskPlan.streamContent}
          {taskPlanStreaming && (
            <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-1" />
          )}
        </div>
      )}

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

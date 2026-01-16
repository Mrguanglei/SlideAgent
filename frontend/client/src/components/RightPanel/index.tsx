import { useRef } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  X,
  Download,
  Share2,
  Play,
  Maximize2,
  Edit3,
  FolderOpen,
} from "lucide-react";
import PPTPreviewPanel from "./PPTPreviewPanel";
import TaskPlanPanel from "./TaskPlanPanel";
import SearchPanel from "./SearchPanel";
import PPTOutlinePanel from "./PPTOutlinePanel";
import FilePanel from "../FilePanel";
import type {
  RightPanelType,
  PPTViewMode,
  TaskPlan,
  SearchRound,
  PPTProject,
} from "@/types";

interface RightPanelProps {
  // 面板状态
  rightPanelType: RightPanelType;
  setRightPanelType: (type: RightPanelType) => void;
  showRightPanel: boolean;
  setShowRightPanel: (show: boolean) => void;

  // PPT 相关
  pptHtmlCode: string;
  pptViewMode: PPTViewMode;
  setPptViewMode: (mode: PPTViewMode) => void;
  pptProject: PPTProject | null;
  currentTopic: string;
  isEditMode: boolean;
  setIsEditMode: (edit: boolean) => void;
  targetSlideIndex?: number; // 目标幻灯片索引

  // 任务规划
  taskPlan: TaskPlan | null;
  taskPlanStreaming: boolean;

  // 搜索
  searchRounds: SearchRound[];
  currentSearchRound: number;
  setCurrentSearchRound: (round: number) => void;
  deepThinking: string;
  deepThinkingStreaming: boolean;

  // PPT 大纲
  pptOutline: string;
  pptOutlineStreaming: boolean;

  // 文件面板
  pptProjects: PPTProject[];
  onSelectProject: (project: PPTProject) => void;

  // 下载和分享
  onDownload: () => void;
  onShare: () => void;
  onPlay: () => void;
  onFullscreen: () => void;
}

export default function RightPanel({
  rightPanelType,
  setRightPanelType,
  showRightPanel,
  setShowRightPanel,
  pptHtmlCode,
  pptViewMode,
  setPptViewMode,
  pptProject,
  currentTopic,
  isEditMode,
  setIsEditMode,
  targetSlideIndex,
  taskPlan,
  taskPlanStreaming,
  searchRounds,
  currentSearchRound,
  setCurrentSearchRound,
  deepThinking,
  deepThinkingStreaming,
  pptOutline,
  pptOutlineStreaming,
  pptProjects,
  onSelectProject,
  onDownload,
  onShare,
  onPlay,
  onFullscreen,
}: RightPanelProps) {
  const taskPlanContentRef = useRef<HTMLDivElement>(null);
  const pptOutlineContentRef = useRef<HTMLDivElement>(null);
  const pptPreviewScrollRef = useRef<HTMLDivElement>(null);
  const pptCodeScrollRef = useRef<HTMLDivElement>(null);

  if (!showRightPanel) return null;

  // 获取当前版本号
  const currentVersion = pptProject?.current_version?.version_number || 1;
  const versionName = pptProject?.current_version?.version_name || `V${currentVersion}`;

  return (
    <div className="w-[900px] border-l border-border bg-background flex flex-col h-full">
      {/* 面板头部 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-background sticky top-0 z-10">
        {/* 左侧：标题和版本 */}
        <div className="flex items-center gap-3">
          {rightPanelType === "ppt_preview" && (
            <>
              <h3 className="font-medium text-sm truncate max-w-[200px]">
                {pptProject?.title || currentTopic || "PPT 预览"}
              </h3>
              <span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
                {versionName}
              </span>
            </>
          )}
          {rightPanelType === "task_plan" && (
            <h3 className="font-medium text-sm">任务执行规划</h3>
          )}
          {rightPanelType === "web_search" && (
            <h3 className="font-medium text-sm">
              搜索网页{searchRounds.length > 0 && searchRounds[searchRounds.length - 1]?.results?.length > 0 && ` (${searchRounds[searchRounds.length - 1].results.length})`}
            </h3>
          )}
          {rightPanelType === "ppt_outline" && (
            <h3 className="font-medium text-sm">PPT 大纲</h3>
          )}
          {rightPanelType === "files" && (
            <h3 className="font-medium text-sm">文件</h3>
          )}
        </div>

        {/* 中间：代码/预览切换（仅 PPT 预览时显示） */}
        {rightPanelType === "ppt_preview" && (
          <div className="flex items-center gap-1 bg-muted rounded-full p-1">
            <button
              onClick={() => setPptViewMode("code")}
              className={cn(
                "px-4 py-1.5 text-sm rounded-full transition-colors",
                pptViewMode === "code"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              代码
            </button>
            <button
              onClick={() => setPptViewMode("preview")}
              className={cn(
                "px-4 py-1.5 text-sm rounded-full transition-colors",
                pptViewMode === "preview"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              预览
            </button>
          </div>
        )}

        {/* 右侧：操作按钮 */}
        <div className="flex items-center gap-1">
          {rightPanelType === "ppt_preview" && (
            <>
              {/* 编辑按钮 */}
              {isEditMode ? (
                <>
                  <button
                    onClick={() => setIsEditMode(false)}
                    className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    取消
                  </button>
                  <button
                    onClick={() => {
                      // TODO: 保存编辑
                      setIsEditMode(false);
                    }}
                    className="px-3 py-1.5 text-sm bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
                  >
                    保存
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={() => setIsEditMode(true)}
                    className="p-2 hover:bg-muted rounded-lg transition-colors"
                    title="编辑"
                  >
                    <Edit3 className="h-4 w-4 text-muted-foreground" />
                  </button>
                  <button
                    onClick={onShare}
                    className="p-2 hover:bg-muted rounded-lg transition-colors"
                    title="分享"
                  >
                    <Share2 className="h-4 w-4 text-muted-foreground" />
                  </button>
                  <button
                    onClick={onDownload}
                    className="p-2 hover:bg-muted rounded-lg transition-colors"
                    title="下载"
                  >
                    <Download className="h-4 w-4 text-muted-foreground" />
                  </button>
                  <button
                    onClick={onPlay}
                    className="p-2 hover:bg-muted rounded-lg transition-colors"
                    title="播放"
                  >
                    <Play className="h-4 w-4 text-muted-foreground" />
                  </button>
                  <button
                    onClick={onFullscreen}
                    className="p-2 hover:bg-muted rounded-lg transition-colors"
                    title="全屏"
                  >
                    <Maximize2 className="h-4 w-4 text-muted-foreground" />
                  </button>
                </>
              )}
            </>
          )}
          <button
            onClick={() => setShowRightPanel(false)}
            className="p-2 hover:bg-muted rounded-lg transition-colors ml-2"
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>
      </div>

      {/* 面板内容 */}
      <div className="flex-1 overflow-hidden">
        {rightPanelType === "ppt_preview" && (
          <PPTPreviewPanel
            pptHtmlCode={pptHtmlCode}
            pptViewMode={pptViewMode}
            pptPreviewScrollRef={pptPreviewScrollRef as any}
            pptCodeScrollRef={pptCodeScrollRef as any}
            targetSlideIndex={targetSlideIndex}
          />
        )}

        {rightPanelType === "task_plan" && (
          <ScrollArea className="h-full">
            <TaskPlanPanel
              taskPlan={taskPlan}
              taskPlanStreaming={taskPlanStreaming}
              taskPlanContentRef={taskPlanContentRef as any}
            />
          </ScrollArea>
        )}

        {rightPanelType === "web_search" && (
          <SearchPanel
            searchRounds={searchRounds}
            currentSearchRound={currentSearchRound}
            setCurrentSearchRound={setCurrentSearchRound}
            deepThinking={deepThinking}
            deepThinkingStreaming={deepThinkingStreaming}
          />
        )}

        {rightPanelType === "ppt_outline" && (
          <ScrollArea className="h-full">
            <PPTOutlinePanel
              pptOutline={pptOutline}
              pptOutlineStreaming={pptOutlineStreaming}
              pptOutlineContentRef={pptOutlineContentRef as any}
            />
          </ScrollArea>
        )}

        {rightPanelType === "files" && (
          <FilePanel
            projects={pptProjects}
            onSelectProject={onSelectProject}
          />
        )}
      </div>
    </div>
  );
}

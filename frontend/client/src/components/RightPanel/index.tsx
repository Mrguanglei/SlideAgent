
import { useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";
import DownloadPopover from "../DownloadPopover";
import { ChevronDown, Maximize2, X, Edit3, Share2, Download, Play } from "lucide-react";
import PPTPreviewPanel from "./PPTPreviewPanel";
import TaskPlanPanel from "./TaskPlanPanel";
import SearchPanel from "./SearchPanel";
import ImageSearchPanel from "./ImageSearchPanel";
import PPTOutlinePanel from "./PPTOutlinePanel";
import FilePanel from "../FilePanel";
import type {
  RightPanelType,
  PPTViewMode,
  TaskPlan,
  SearchRound,
  ImageSearchRound,
  PPTProject,
} from "@/types";
import type { EditablePPTPreviewRef } from "./EditablePPTPreview";

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
  onSaveSlide?: (slideId: number, htmlContent: string) => Promise<void>; // 保存幻灯片回调

  // 任务规划
  taskPlan: TaskPlan | null;
  taskPlanStreaming: boolean;

  // 搜索
  searchRounds: SearchRound[];
  currentSearchRound: number;
  setCurrentSearchRound: (round: number) => void;
  deepThinking: string;
  deepThinkingStreaming: boolean;
  imageSearchRounds: ImageSearchRound[];
  currentImageSearchRound: number;
  setCurrentImageSearchRound: (round: number) => void;

  // PPT 大纲
  pptOutline: string;
  pptOutlineStreaming: boolean;

  // 文件面板
  pptProjects: PPTProject[];
  onSelectProject: (project: PPTProject) => void;
  onSelectVersion?: (project: PPTProject, versionId: number) => void;
  editSnapshots?: Record<number, string>; // versionId -> 编辑前原始 HTML
  snapshotViewingOriginal?: Record<number, boolean>; // versionId -> 当前是否显示原始
  onRestoreSnapshot?: (versionId: number, viewOriginal: boolean) => void; // 切换原始/修改
  subVersionIds?: Record<number, number>; // parentVersionId -> 原始子版本ID

  // 下载和分享
  onDownload: () => void;
  onShare: () => void;
  onPlay: () => void;
  onFullscreen: () => void;
  onDownloadProgress?: (payload: {
    status: "start" | "progress" | "complete" | "error";
    percent?: number;
    label?: string;
  }) => void;
  isLoading?: boolean;
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
  onSaveSlide,
  taskPlan,
  taskPlanStreaming,
  searchRounds,
  currentSearchRound,
  setCurrentSearchRound,
  deepThinking,
  deepThinkingStreaming,
  imageSearchRounds,
  currentImageSearchRound,
  setCurrentImageSearchRound,
  pptOutline,
  pptOutlineStreaming,
  pptProjects,
  onSelectProject,
  onSelectVersion,
  editSnapshots = {},
  snapshotViewingOriginal = {},
  onRestoreSnapshot,
  subVersionIds = {},
  onDownload,
  onShare,
  onPlay,
  onFullscreen,
  onDownloadProgress,
  isLoading = false,
}: RightPanelProps) {
  const taskPlanContentRef = useRef<HTMLDivElement>(null);
  const pptOutlineContentRef = useRef<HTMLDivElement>(null);
  const pptPreviewScrollRef = useRef<HTMLDivElement>(null);
  const pptCodeScrollRef = useRef<HTMLDivElement>(null);
  const editablePPTRef = useRef<EditablePPTPreviewRef>(null);
  const [versionDropdownOpen, setVersionDropdownOpen] = useState(false);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const pptHeaderTitle = pptProject?.title || currentTopic || "PPT 预览";

  // 收集所有版本：当前 project 的所有 versions
  const allVersions = pptProject?.versions || [];
  const currentVersionId = pptProject?.current_version?.id;
  // 当前版本是否有手动编辑快照（原始 vs 修改）
  const currentVersionSnapshot = currentVersionId ? editSnapshots[currentVersionId] : undefined;
  const hasSubVersions = !!currentVersionSnapshot;
  // 当前是否正在查看原始版本
  const isViewingOriginal = currentVersionId ? !!snapshotViewingOriginal[currentVersionId] : false;
  const downloadVersionId =
    currentVersionId && isViewingOriginal && subVersionIds[currentVersionId]
      ? subVersionIds[currentVersionId]
      : currentVersionId;

  // 保存编辑
  const handleSaveEdit = async () => {
    try {
      setIsSavingEdit(true);
      await editablePPTRef.current?.saveAllSlides();
      toast.success("保存成功");
      setIsEditMode(false);
    } catch (error) {
      console.error('保存失败:', error);
      toast.error("保存失败，请重试");
    } finally {
      setIsSavingEdit(false);
    }
  };

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
                {pptHeaderTitle}
              </h3>
              {/* 版本选择器 */}
              <div className="relative">
                <button
                  onClick={() => hasSubVersions && setVersionDropdownOpen(v => !v)}
                  className={cn(
                    "flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground transition-colors",
                    hasSubVersions && "hover:bg-muted/80 cursor-pointer"
                  )}
                >
                  {hasSubVersions ? `${versionName} ${isViewingOriginal ? "原始" : "修改"}` : versionName}
                  {hasSubVersions && <ChevronDown className={cn("h-3 w-3 transition-transform", versionDropdownOpen && "rotate-180")} />}
                </button>
                {versionDropdownOpen && hasSubVersions && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setVersionDropdownOpen(false)} />
                    <div className="absolute left-0 top-full mt-1 z-20 bg-background border border-border rounded-xl shadow-lg py-1 min-w-[260px]">
                      {/* 如果当前版本有手动编辑快照，显示子版本 */}
                      {hasSubVersions ? (
                        <>
                          <button
                            onClick={() => {
                              setVersionDropdownOpen(false);
                              if (onRestoreSnapshot && currentVersionId) {
                                onRestoreSnapshot(currentVersionId, true);
                              }
                            }}
                            className={cn(
                              "w-full flex items-center gap-3 px-4 py-2 text-sm hover:bg-muted transition-colors text-left",
                              isViewingOriginal && "text-primary"
                            )}
                          >
                            <div className="flex-1 min-w-0">
                              <span className="truncate block">{pptHeaderTitle}</span>
                            </div>
                            <span className={cn(
                              "text-[10px] px-1.5 py-0.5 rounded shrink-0",
                              isViewingOriginal ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                            )}>
                              {versionName} 原始
                            </span>
                            <div className={cn(
                              "w-4 h-4 rounded-full border-2 shrink-0 flex items-center justify-center",
                              isViewingOriginal ? "border-primary" : "border-muted-foreground/30"
                            )}>
                              {isViewingOriginal && <div className="w-2 h-2 rounded-full bg-primary" />}
                            </div>
                          </button>
                          <button
                            onClick={() => {
                              setVersionDropdownOpen(false);
                              if (onRestoreSnapshot && currentVersionId) {
                                onRestoreSnapshot(currentVersionId, false);
                              }
                            }}
                            className={cn(
                              "w-full flex items-center gap-3 px-4 py-2 text-sm hover:bg-muted transition-colors text-left",
                              !isViewingOriginal && "text-primary"
                            )}
                          >
                            <div className="flex-1 min-w-0">
                              <span className="truncate block">{pptHeaderTitle}</span>
                            </div>
                            <span className={cn(
                              "text-[10px] px-1.5 py-0.5 rounded shrink-0",
                              !isViewingOriginal ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                            )}>
                              {versionName} 修改
                            </span>
                            <div className={cn(
                              "w-4 h-4 rounded-full border-2 shrink-0 flex items-center justify-center",
                              !isViewingOriginal ? "border-primary" : "border-muted-foreground/30"
                            )}>
                              {!isViewingOriginal && <div className="w-2 h-2 rounded-full bg-primary" />}
                            </div>
                          </button>
                        </>
                      ) : (
                        allVersions.map((v) => {
                          const label = v.version_name || `V${v.version_number}`;
                          const isActive = v.id === currentVersionId;
                          return (
                            <button
                              key={v.id}
                              onClick={() => {
                                setVersionDropdownOpen(false);
                                if (!isActive && onSelectVersion && pptProject) {
                                  onSelectVersion(pptProject, v.id);
                                }
                              }}
                              className={cn(
                                "w-full flex items-center gap-3 px-4 py-2 text-sm hover:bg-muted transition-colors text-left",
                                isActive && "text-primary"
                              )}
                            >
                              <div className="flex-1 min-w-0">
                                <span className="truncate block">{pptHeaderTitle}</span>
                              </div>
                              <span className={cn(
                                "text-[10px] px-1.5 py-0.5 rounded shrink-0",
                                isActive ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                              )}>
                                {label}
                              </span>
                              <div className={cn(
                                "w-4 h-4 rounded-full border-2 shrink-0 flex items-center justify-center",
                                isActive ? "border-primary" : "border-muted-foreground/30"
                              )}>
                                {isActive && <div className="w-2 h-2 rounded-full bg-primary" />}
                              </div>
                            </button>
                          );
                        })
                      )}
                    </div>
                  </>
                )}
              </div>
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
          {rightPanelType === "image_search" && (
            <h3 className="font-medium text-sm">
              搜索图片{imageSearchRounds.length > 0 && imageSearchRounds[imageSearchRounds.length - 1]?.images?.length > 0 && ` (${imageSearchRounds[imageSearchRounds.length - 1].images.length})`}
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
              onClick={() => {
                if (isEditMode) setIsEditMode(false);
                setPptViewMode("code");
              }}
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
            <div
              className={cn(
                "flex items-center gap-1",
                pptViewMode !== "preview" && "invisible pointer-events-none"
              )}
            >
              {/* 编辑按钮 */}
              {isEditMode ? (
                <>
                  <button
                    onClick={() => !isSavingEdit && setIsEditMode(false)}
                    disabled={isSavingEdit}
                    className={cn(
                      "px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors",
                      isSavingEdit && "opacity-50 cursor-not-allowed"
                    )}
                  >
                    取消
                  </button>
                  <button
                    onClick={handleSaveEdit}
                    disabled={isSavingEdit}
                    className={cn(
                      "px-3 py-1.5 text-sm bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors",
                      isSavingEdit && "opacity-70 cursor-not-allowed"
                    )}
                  >
                    {isSavingEdit ? "保存中..." : "保存"}
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={() => !isLoading && setIsEditMode(true)}
                    disabled={isLoading}
                    className={cn(
                      "p-2 hover:bg-muted rounded-lg transition-colors",
                      isLoading && "opacity-50 cursor-not-allowed"
                    )}
                    title={isLoading ? "正在运行不可编辑" : "编辑"}
                  >
                    <Edit3 className="h-4 w-4 text-muted-foreground" />
                  </button>
                  <button
                    onClick={() => !isLoading && onShare()}
                    disabled={isLoading}
                    className={cn(
                      "p-2 hover:bg-muted rounded-lg transition-colors",
                      isLoading && "opacity-50 cursor-not-allowed"
                    )}
                    title={isLoading ? "正在运行不可分享" : "分享"}
                  >
                    <Share2 className="h-4 w-4 text-muted-foreground" />
                  </button>
                  {pptProject ? (
                    <DownloadPopover
                      projectId={pptProject.id}
                      versionId={downloadVersionId}
                      title={pptProject.title}
                      disabled={isLoading}
                      onProgress={onDownloadProgress}
                    />
                  ) : (
                    <button
                      disabled
                      className="p-2 hover:bg-muted rounded-lg transition-colors opacity-50 cursor-not-allowed"
                      title="生成中..."
                    >
                      <Download className="h-4 w-4 text-muted-foreground" />
                    </button>
                  )}
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
            </div>
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
        <div className={rightPanelType === "ppt_preview" ? "h-full" : "hidden"}>
          <PPTPreviewPanel
            pptHtmlCode={pptHtmlCode}
            pptViewMode={pptViewMode}
            pptPreviewScrollRef={pptPreviewScrollRef as any}
            pptCodeScrollRef={pptCodeScrollRef as any}
            targetSlideIndex={targetSlideIndex}
            editablePPTRef={editablePPTRef as React.RefObject<EditablePPTPreviewRef>}
            isEditMode={isEditMode}
            onSaveSlide={onSaveSlide}
            pptProject={pptProject}
          />
        </div>

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

        {rightPanelType === "image_search" && (
          <ImageSearchPanel
            imageSearchRounds={imageSearchRounds}
            currentImageSearchRound={currentImageSearchRound}
            setCurrentImageSearchRound={setCurrentImageSearchRound}
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

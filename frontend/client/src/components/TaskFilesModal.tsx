/**
 * 任务文件对话框组件
 *
 * 显示当前对话生成的 PPT 文件
 */

import { X, Code } from "lucide-react";
import type { PPTProject } from "@/types";

interface TaskFilesModalProps {
  isOpen: boolean;
  onClose: () => void;
  pptProject: PPTProject | null;
  onSelectProject?: (project: PPTProject) => void;
}

export default function TaskFilesModal({
  isOpen,
  onClose,
  pptProject,
  onSelectProject,
}: TaskFilesModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 背景遮罩 */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* 对话框 - 更宽更高 */}
      <div className="relative bg-background rounded-2xl shadow-2xl w-full max-w-2xl mx-4 h-[60vh] flex flex-col">
        {/* 头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold">任务文件</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-muted rounded-lg transition-colors"
          >
            <X className="h-5 w-5 text-muted-foreground" />
          </button>
        </div>

        {/* 内容 */}
        <div className="flex-1 overflow-y-auto p-8">
          {pptProject ? (
            <div
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer max-w-md"
              onClick={() => {
                if (onSelectProject) {
                  onSelectProject(pptProject);
                }
                onClose();
              }}
            >
              {/* 文件图标 - 更小 */}
              <div className="w-6 h-6 rounded bg-gradient-to-br from-blue-100 to-blue-200 flex items-center justify-center shrink-0">
                <Code className="h-3.5 w-3.5 text-blue-600" />
              </div>

              {/* 文件名和版本 - 更紧凑 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-xs truncate">
                    {pptProject.title}
                  </span>
                  {pptProject.current_version && (
                    <span className="text-[10px] px-1 py-0.5 rounded bg-muted text-muted-foreground shrink-0">
                      V{pptProject.current_version.version_number}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Code className="h-12 w-12 text-muted-foreground/20 mb-3" />
              <p className="text-sm text-muted-foreground">
                暂无文件
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

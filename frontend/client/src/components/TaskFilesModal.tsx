/**
 * 任务文件对话框组件
 *
 * 显示当前对话生成的所有 PPT 文件（支持多主题多版本）
 */

import { X, Code } from "lucide-react";
import type { PPTProject } from "@/types";

interface TaskFilesModalProps {
  isOpen: boolean;
  onClose: () => void;
  pptProject?: PPTProject | null;
  pptProjects?: PPTProject[];
  onSelectProject?: (project: PPTProject) => void;
  onSelectVersion?: (project: PPTProject, versionId: number) => void;
}

export default function TaskFilesModal({
  isOpen,
  onClose,
  pptProject,
  pptProjects,
  onSelectProject,
  onSelectVersion,
}: TaskFilesModalProps) {
  if (!isOpen) return null;

  // 合并 pptProject 和 pptProjects，以 pptProject 的完整数据优先（含 versions）
  const projectMap = new Map<number, PPTProject>();
  (pptProjects || []).forEach(p => projectMap.set(p.id, p));
  if (pptProject) projectMap.set(pptProject.id, pptProject);
  const projects: PPTProject[] = Array.from(projectMap.values());

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 背景遮罩 */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* 对话框 */}
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
        <div className="flex-1 overflow-y-auto p-6">
          {projects.length > 0 ? (
            <div className="flex flex-col gap-2">
              {projects.map((project) => {
                // 只显示顶层版本（无 parent_version_id）
                const topVersions = (project.versions || [])
                  .filter((v) => !v.parent_version_id)
                  .slice()
                  .sort((a, b) => a.version_number - b.version_number);

                // 如果没有 versions 数据，退化为显示 project 本身
                if (topVersions.length === 0) {
                  return (
                    <div
                      key={project.id}
                      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer"
                      onClick={() => { onSelectProject?.(project); onClose(); }}
                    >
                      <div className="w-6 h-6 rounded bg-gradient-to-br from-blue-100 to-blue-200 flex items-center justify-center shrink-0">
                        <Code className="h-3.5 w-3.5 text-blue-600" />
                      </div>
                      <span className="font-medium text-xs truncate">{project.title}</span>
                    </div>
                  );
                }

                return topVersions.map((version) => (
                  <div
                    key={`${project.id}-${version.id}`}
                    className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer"
                    onClick={() => {
                      if (onSelectVersion) {
                        onSelectVersion(project, version.id);
                      } else {
                        onSelectProject?.(project);
                      }
                      onClose();
                    }}
                  >
                    <div className="w-6 h-6 rounded bg-gradient-to-br from-blue-100 to-blue-200 flex items-center justify-center shrink-0">
                      <Code className="h-3.5 w-3.5 text-blue-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-xs truncate">{project.title}</span>
                        <span className="text-[10px] px-1 py-0.5 rounded bg-muted text-muted-foreground shrink-0">
                          {version.version_name || `V${version.version_number}`}
                        </span>
                      </div>
                    </div>
                  </div>
                ));
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Code className="h-12 w-12 text-muted-foreground/20 mb-3" />
              <p className="text-sm text-muted-foreground">暂无文件</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

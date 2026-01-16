/**
 * 文件面板组件
 * 
 * 功能：
 * - 显示生成的 PPT 项目列表
 * - 点击查看 PPT 预览
 * - 版本管理
 */

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  FileSliders,
  ChevronRight,
  Trash2,
  Clock,
  Layers,
} from "lucide-react";
import {
  getPPTProjects,
  deletePPTProject,
  type PPTProject,
} from "@/lib/api";

interface FilePanelProps {
  projects?: PPTProject[];
  onSelectProject: (project: PPTProject) => void;
  refreshTrigger?: number;
}

export default function FilePanel({
  projects: externalProjects,
  onSelectProject,
  refreshTrigger,
}: FilePanelProps) {
  const [internalProjects, setInternalProjects] = useState<PPTProject[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // 使用外部传入的 projects 或内部加载的
  const projects = externalProjects || internalProjects;

  // 加载项目列表（仅当没有外部传入时）
  const loadProjects = async () => {
    if (externalProjects) return;
    setIsLoading(true);
    try {
      const data = await getPPTProjects();
      setInternalProjects(data);
    } catch (error) {
      console.error("Failed to load PPT projects:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!externalProjects) {
      loadProjects();
    }
  }, [refreshTrigger, externalProjects]);

  // 删除项目
  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("确定要删除这个 PPT 项目吗？")) return;
    
    try {
      await deletePPTProject(id);
      setInternalProjects(prev => prev.filter(p => p.id !== id));
    } catch (error) {
      console.error("Failed to delete PPT project:", error);
    }
  };

  // 格式化时间
  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("zh-CN", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // 选择项目
  const handleSelect = (project: PPTProject) => {
    setSelectedId(project.id);
    onSelectProject(project);
  };

  return (
    <div className="h-full flex flex-col">
      {/* 头部 */}
      <div className="px-4 py-3 border-b border-border">
        <h3 className="font-medium text-sm">我的文件</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          {projects.length} 个 PPT 项目
        </p>
      </div>

      {/* 项目列表 */}
      <ScrollArea className="flex-1">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <span className="text-sm text-muted-foreground">加载中...</span>
          </div>
        ) : projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center px-4">
            <FileSliders className="h-10 w-10 text-muted-foreground/30 mb-3" />
            <span className="text-sm text-muted-foreground">暂无 PPT 项目</span>
            <span className="text-xs text-muted-foreground/70 mt-1">
              生成的 PPT 将显示在这里
            </span>
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {projects.map(project => (
              <div
                key={project.id}
                className={cn(
                  "group relative p-3 rounded-lg cursor-pointer transition-colors",
                  selectedId === project.id
                    ? "bg-primary/10"
                    : "hover:bg-gray-50"
                )}
                onClick={() => handleSelect(project)}
              >
                {/* 项目信息 */}
                <div className="flex items-start gap-3">
                  {/* 图标 */}
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                    <FileSliders className="h-5 w-5 text-primary" />
                  </div>

                  {/* 内容 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate">
                        {project.title}
                      </span>
                      {project.versions && project.versions.length > 0 && (
                        <span className="text-xs px-1.5 py-0.5 bg-gray-100 rounded text-muted-foreground">
                          V{project.versions[project.versions.length - 1].version_number}
                        </span>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatTime(project.updated_at)}
                      </span>
                      {project.versions && project.versions.length > 0 && (
                        <span className="flex items-center gap-1">
                          <Layers className="h-3 w-3" />
                          {project.versions[project.versions.length - 1].slide_count || 0} 页
                        </span>
                      )}
                    </div>
                  </div>

                  {/* 箭头 */}
                  <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0 mt-1" />
                </div>

                {/* 删除按钮 */}
                <button
                  onClick={e => handleDelete(project.id, e)}
                  className="absolute right-2 top-2 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-50 text-red-500 transition-all"
                  title="删除项目"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}

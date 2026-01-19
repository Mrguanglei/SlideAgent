/**
 * 下载弹窗组件
 * 
 * 支持导出格式：
 * - PDF 文档
 * - PNG 图片（ZIP 打包）
 * - PowerPoint 文件
 */

import { useState } from "react";
import { X, FileText, FileSliders, Loader2, Download, Globe } from "lucide-react";
import { cn } from "@/lib/utils";

interface DownloadModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: number;
  versionId?: number;
  title: string;
}

interface ExportFormat {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  extension: string;
}

const EXPORT_FORMATS: ExportFormat[] = [
  {
    id: "pdf",
    name: "PDF 文档",
    description: "适合打印和分享，保持原有排版",
    icon: <FileText className="h-6 w-6" />,
    extension: ".pdf"
  },
  {
    id: "html",
    name: "HTML 网页",
    description: "可在浏览器中直接播放，支持动画",
    icon: <Globe className="h-6 w-6" />,
    extension: ".html"
  },
  {
    id: "pptx",
    name: "PowerPoint",
    description: "可在 Office 中打开和编辑",
    icon: <FileSliders className="h-6 w-6" />,
    extension: ".pptx"
  }
];

export default function DownloadModal({
  isOpen,
  onClose,
  projectId,
  versionId,
  title
}: DownloadModalProps) {
  const [selectedFormat, setSelectedFormat] = useState<string>("pdf");
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);

    try {
      const response = await fetch("/api/ppt/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          version_id: versionId,
          format: selectedFormat
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "导出失败");
      }

      // 获取文件名
      const contentDisposition = response.headers.get("Content-Disposition");
      let filename = `${title}${EXPORT_FORMATS.find(f => f.id === selectedFormat)?.extension || ""}`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (match) {
          filename = match[1].replace(/['"]/g, "");
        }
      }

      // 下载文件
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      // 关闭弹窗
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "导出失败，请重试");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 背景遮罩 */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* 弹窗内容 */}
      <div className="relative bg-background rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        {/* 头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold">导出 PPT</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-muted rounded-lg transition-colors"
          >
            <X className="h-5 w-5 text-muted-foreground" />
          </button>
        </div>

        {/* 格式选择 */}
        <div className="p-6 space-y-3">
          <p className="text-sm text-muted-foreground mb-4">选择导出格式</p>

          {EXPORT_FORMATS.map((format) => (
            <button
              key={format.id}
              onClick={() => setSelectedFormat(format.id)}
              className={cn(
                "w-full flex items-center gap-4 p-4 rounded-xl border-2 transition-all text-left",
                selectedFormat === format.id
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/50 hover:bg-muted/50"
              )}
            >
              <div className={cn(
                "p-2 rounded-lg",
                selectedFormat === format.id
                  ? "bg-primary text-white"
                  : "bg-muted text-muted-foreground"
              )}>
                {format.icon}
              </div>
              <div className="flex-1">
                <div className="font-medium">{format.name}</div>
                <div className="text-sm text-muted-foreground">{format.description}</div>
              </div>
              <div className={cn(
                "w-5 h-5 rounded-full border-2 flex items-center justify-center",
                selectedFormat === format.id
                  ? "border-primary bg-primary"
                  : "border-muted-foreground/30"
              )}>
                {selectedFormat === format.id && (
                  <div className="w-2 h-2 rounded-full bg-white" />
                )}
              </div>
            </button>
          ))}

          {/* 错误提示 */}
          {error && (
            <div className="p-3 bg-destructive/10 text-destructive text-sm rounded-lg">
              {error}
            </div>
          )}
        </div>

        {/* 底部按钮 */}
        <div className="px-6 py-4 border-t border-border bg-muted/30 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleExport}
            disabled={isExporting}
            className="px-6 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {isExporting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                导出中...
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                导出
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

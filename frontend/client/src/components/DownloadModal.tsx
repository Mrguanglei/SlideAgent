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
import { toast } from "sonner";

interface DownloadModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: number;
  versionId?: number;
  title: string;
  onProgress?: (payload: {
    status: "start" | "progress" | "complete" | "error";
    percent?: number;
    label?: string;
  }) => void;
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

const extractFilename = (contentDisposition: string | null, fallback: string) => {
  if (!contentDisposition) return fallback;
  const filenameStarMatch = contentDisposition.match(/filename\*\s*=\s*([^;]+)/i);
  if (filenameStarMatch?.[1]) {
    const value = filenameStarMatch[1].trim().replace(/^"|"$/g, "");
    const parts = value.split("''");
    const encoded = parts.length > 1 ? parts.slice(1).join("''") : value;
    try {
      const decoded = decodeURIComponent(encoded);
      if (decoded) return decoded;
    } catch {
      // Fall back to filename= or default.
    }
  }
  const filenameMatch = contentDisposition.match(/filename\s*=\s*([^;]+)/i);
  if (filenameMatch?.[1]) {
    const value = filenameMatch[1].trim().replace(/^"|"$/g, "");
    if (value) return value;
  }
  return fallback;
};

export default function DownloadModal({
  isOpen,
  onClose,
  projectId,
  versionId,
  title,
  onProgress
}: DownloadModalProps) {
  const [selectedFormat, setSelectedFormat] = useState<string>("pdf");
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);
    const format = selectedFormat;
    let lastPercent = -1;
    let fakeTimer: number | null = null;
    let fakeProgress = 0;
    const formatLabel = EXPORT_FORMATS.find(f => f.id === format)?.name || "文件";

    const stopFake = () => {
      if (fakeTimer !== null) {
        window.clearInterval(fakeTimer);
        fakeTimer = null;
      }
    };

    const startFake = () => {
      if (fakeTimer !== null) return;
      fakeTimer = window.setInterval(() => {
        if (fakeProgress >= 80) {
          stopFake();
          return;
        }
        const step = 1;
        fakeProgress = Math.min(80, fakeProgress + step);
        if (fakeProgress > lastPercent) {
          lastPercent = fakeProgress;
          onProgress?.({
            status: "progress",
            percent: fakeProgress,
            label: formatLabel,
          });
        }
      }, 500);
    };
    onProgress?.({ status: "start", percent: 0, label: formatLabel });

    try {
      const { blob, filename } = await new Promise<{ blob: Blob; filename: string }>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/ppt/export", true);
        xhr.responseType = "blob";
        xhr.setRequestHeader("Content-Type", "application/json");

        xhr.onloadstart = () => {
          startFake();
        };

        xhr.onprogress = (event) => {
          if (event.lengthComputable && event.total > 0) {
            const rawPercent = Math.round((event.loaded / event.total) * 100);
            const percent = Math.min(80, rawPercent);
            if (percent !== lastPercent) {
              lastPercent = percent;
              stopFake();
              onProgress?.({
                status: "progress",
                percent,
                label: formatLabel,
              });
            }
          } else {
            startFake();
          }
        };

        xhr.onerror = () => reject(new Error("网络错误，请稍后重试"));

        xhr.onload = () => {
          const ok = xhr.status >= 200 && xhr.status < 300;
          const fallback = `${title}${EXPORT_FORMATS.find(f => f.id === format)?.extension || ""}`;
          if (!ok) {
            const errorBlob = xhr.response;
            if (errorBlob && typeof errorBlob.text === "function") {
              errorBlob
                .text()
                .then((text: string) => {
                  try {
                    const data = JSON.parse(text);
                    reject(new Error(data.detail || "导出失败"));
                  } catch {
                    reject(new Error(text || "导出失败"));
                  }
                })
                .catch(() => reject(new Error("导出失败")));
            } else {
              reject(new Error("导出失败"));
            }
            return;
          }

          const contentDisposition = xhr.getResponseHeader("Content-Disposition");
          const filename = extractFilename(contentDisposition, fallback);
          resolve({ blob: xhr.response, filename });
        };

        xhr.send(JSON.stringify({
          project_id: projectId,
          version_id: versionId,
          format
        }));
      });

      stopFake();
      stopFake();
      onProgress?.({ status: "complete", percent: 100, label: "下载完成" });

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
      toast.success("下载成功", { description: "文件已保存到本地" });
    } catch (err) {
      const message = err instanceof Error ? err.message : "导出失败，请重试";
      stopFake();
      onProgress?.({ status: "error", label: message });
      toast.error("导出失败", { description: message });
      setError(message);
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

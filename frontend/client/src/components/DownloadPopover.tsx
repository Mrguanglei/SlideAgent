
import { useState } from "react";
import { FileText, FileSliders, Globe, Download, Loader2 } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface DownloadPopoverProps {
    projectId: number;
    versionId?: number;
    title: string;
    disabled?: boolean;
    onProgress?: (payload: {
        status: "start" | "progress" | "complete" | "error";
        percent?: number;
        label?: string;
    }) => void;
}

interface ExportItemProps {
    id: string;
    name: string;
    icon: React.ReactNode;
    iconBgInfo: string;
    onDownload: () => void;
    isLoading: boolean;
    extraInfo?: string;
}

function ExportItem({ id, name, icon, iconBgInfo, onDownload, isLoading, extraInfo }: ExportItemProps) {
    return (
        <div className="flex items-center justify-between py-3">
            <div className="flex items-center gap-3">
                <div className={cn("p-2 rounded-lg", iconBgInfo)}>
                    {icon}
                </div>
                <div>
                    <div className="font-medium text-sm text-foreground">{name}</div>
                    {extraInfo && (
                        <div className="text-xs text-muted-foreground mt-0.5">{extraInfo}</div>
                    )}
                </div>
            </div>
            <button
                onClick={onDownload}
                disabled={isLoading}
                className="px-4 py-1.5 text-sm bg-muted/50 hover:bg-muted text-foreground rounded-md transition-colors min-w-[70px] flex justify-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
                {isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                    "下载"
                )}
            </button>
        </div>
    );
}

const extractFilename = (contentDisposition: string | null, fallback: string) => {
    if (!contentDisposition) return fallback;

    const filenameStarMatch = contentDisposition.match(/filename\*\s*=\s*([^;]+)/i);
    if (filenameStarMatch && filenameStarMatch[1]) {
        const value = filenameStarMatch[1].trim().replace(/^\"|\"$/g, "");
        const parts = value.split("''");
        const encoded = parts.length > 1 ? parts.slice(1).join("''") : value;
        try {
            const decoded = decodeURIComponent(encoded);
            if (decoded) return decoded;
        } catch {
            // ignore decode errors
        }
    }

    const filenameMatch = contentDisposition.match(/filename\s*=\s*([^;]+)/i);
    if (filenameMatch && filenameMatch[1]) {
        const value = filenameMatch[1].trim().replace(/^\"|\"$/g, "");
        if (value) return value;
    }

    return fallback;
};

export default function DownloadPopover({
    projectId,
    versionId,
    title,
    disabled,
    onProgress,
}: DownloadPopoverProps) {
    const [loadingMap, setLoadingMap] = useState<Record<string, boolean>>({});

    const handleExport = async (format: string, extension: string) => {
        setLoadingMap(prev => ({ ...prev, [format]: true }));
        let succeeded = false;
        let lastPercent = -1;
        let fakeTimer: number | null = null;
        let fakeProgress = 0;
        const formatLabelMap: Record<string, string> = {
            pdf: "PDF",
            html: "HTML",
            images: "图片",
            pptx: "PPT",
        };
        const label = formatLabelMap[format] || "文件";

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
                        label,
                    });
                }
            }, 500);
        };

        onProgress?.({ status: "start", percent: 0, label });

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
                                label,
                            });
                        }
                    } else {
                        startFake();
                    }
                };

                xhr.onerror = () => {
                    reject(new Error("网络错误，请稍后重试"));
                };

                xhr.onload = () => {
                    const ok = xhr.status >= 200 && xhr.status < 300;
                    const fallbackName = `${title}${extension}`;
                    if (!ok) {
                        const errorBlob = xhr.response;
                        if (errorBlob && typeof errorBlob.text === "function") {
                            errorBlob.text().then((text: string) => {
                                try {
                                    const data = JSON.parse(text);
                                    reject(new Error(data.detail || "导出失败"));
                                } catch {
                                    reject(new Error(text || "导出失败"));
                                }
                            }).catch(() => reject(new Error("导出失败")));
                        } else {
                            reject(new Error("导出失败"));
                        }
                        return;
                    }

                    const contentDisposition = xhr.getResponseHeader("Content-Disposition");
                    const filename = extractFilename(contentDisposition, fallbackName);
                    resolve({ blob: xhr.response, filename });
                };

                xhr.send(JSON.stringify({
                    project_id: projectId,
                    version_id: versionId,
                    format: format
                }));
            });

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
            succeeded = true;

        } catch (err) {
            console.error("Export failed:", err);
            const message = err instanceof Error ? err.message : "导出失败，请稍后重试";
            stopFake();
            onProgress?.({ status: "error", label: message });
            toast.error("导出失败", { description: message });
        } finally {
            setLoadingMap(prev => ({ ...prev, [format]: false }));
        }
        if (succeeded) {
            toast.success("下载成功", { description: "文件已保存到本地" });
        }
    };

    return (
        <Popover>
            <PopoverTrigger asChild>
                <button
                    disabled={disabled}
                    className={cn(
                        "p-2 hover:bg-muted rounded-lg transition-colors outline-none",
                        disabled && "opacity-50 cursor-not-allowed"
                    )}
                    title={disabled ? "正在运行不可操作" : "下载"}
                >
                    <Download className="h-4 w-4 text-muted-foreground" />
                </button>
            </PopoverTrigger>
            <PopoverContent className="w-[320px] p-0" align="end" sideOffset={5}>
                <div className="p-4 border-b border-border/50">
                    <h3 className="font-semibold text-base mb-2">选择下载格式</h3>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                        PPT导出不支持部分视觉效果，样式可能有所差异；
                    </p>
                </div>
                <div className="p-2">
                    <ExportItem
                        id="pdf"
                        name="PDF文件"
                        icon={<FileText className="h-5 w-5 text-rose-600" />}
                        iconBgInfo="bg-rose-100"
                        onDownload={() => handleExport("pdf", ".pdf")}
                        isLoading={loadingMap["pdf"]}
                    />
                    <ExportItem
                        id="html"
                        name="HTML网页"
                        icon={<Globe className="h-5 w-5 text-emerald-600" />}
                        iconBgInfo="bg-emerald-100"
                        onDownload={() => handleExport("html", ".html")}
                        isLoading={loadingMap["html"]}
                    />
                    <ExportItem
                        id="images"
                        name="图片打包"
                        icon={<Download className="h-5 w-5 text-blue-600" />}
                        iconBgInfo="bg-blue-100"
                        onDownload={() => handleExport("images", ".zip")}
                        isLoading={loadingMap["images"]}
                        extraInfo="每页导出为PNG图片，打包成ZIP"
                    />
                    <ExportItem
                        id="pptx"
                        name="PPT文件"
                        icon={<FileSliders className="h-5 w-5 text-orange-600" />}
                        iconBgInfo="bg-orange-100"
                        onDownload={() => handleExport("pptx", ".pptx")}
                        isLoading={loadingMap["pptx"]}
                        extraInfo="PPTX下载样式可能有所差异"
                    />
                </div>
            </PopoverContent>
        </Popover>
    );
}

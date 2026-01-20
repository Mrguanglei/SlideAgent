
import { useState } from "react";
import { FileText, FileSliders, Globe, Download, Loader2 } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

interface DownloadPopoverProps {
    projectId: number;
    versionId?: number;
    title: string;
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

export default function DownloadPopover({ projectId, versionId, title }: DownloadPopoverProps) {
    const [loadingMap, setLoadingMap] = useState<Record<string, boolean>>({});

    const handleExport = async (format: string, extension: string) => {
        setLoadingMap(prev => ({ ...prev, [format]: true }));

        try {
            const response = await fetch("/api/ppt/export", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    project_id: projectId,
                    version_id: versionId,
                    format: format
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "导出失败");
            }

            // 获取文件名
            const contentDisposition = response.headers.get("Content-Disposition");
            let filename = `${title}${extension}`;
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

        } catch (err) {
            console.error("Export failed:", err);
            // 这里可以加一个 toast 通知用户失败，暂时 log
            alert("导出失败，请稍后重试");
        } finally {
            setLoadingMap(prev => ({ ...prev, [format]: false }));
        }
    };

    return (
        <Popover>
            <PopoverTrigger asChild>
                <button
                    className="p-2 hover:bg-muted rounded-lg transition-colors outline-none"
                    title="下载"
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
                        extraInfo="PPTX 下载目前有问题，敬请谅解"
                    />
                </div>
            </PopoverContent>
        </Popover>
    );
}

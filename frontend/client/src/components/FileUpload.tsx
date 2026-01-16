import { useCallback, useState } from "react";
import { usePPTAgent } from "@/contexts/PPTAgentContext";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Upload,
  X,
  FileText,
  Image,
  File,
  FileSpreadsheet,
  Presentation,
} from "lucide-react";

const FILE_ICONS: Record<string, typeof File> = {
  "application/pdf": FileText,
  "application/msword": FileText,
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileText,
  "application/vnd.ms-powerpoint": Presentation,
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": Presentation,
  "application/vnd.ms-excel": FileSpreadsheet,
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FileSpreadsheet,
  "text/plain": FileText,
  "text/markdown": FileText,
};

function getFileIcon(type: string) {
  if (type.startsWith("image/")) return Image;
  return FILE_ICONS[type] || File;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface FileUploadProps {
  onFilesSelected?: (files: File[]) => void;
  accept?: string;
  maxFiles?: number;
  maxSize?: number; // in bytes
  className?: string;
}

export function FileUpload({
  onFilesSelected,
  accept = ".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.md,.png,.jpg,.jpeg,.gif,.webp",
  maxFiles = 10,
  maxSize = 50 * 1024 * 1024, // 50MB
  className,
}: FileUploadProps) {
  const { state, addAttachment, removeAttachment, updateAttachment } = usePPTAgent();
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files) return;

      const validFiles: File[] = [];
      const currentCount = state.attachments.length;

      for (let i = 0; i < files.length; i++) {
        const file = files[i];

        // Check max files
        if (currentCount + validFiles.length >= maxFiles) {
          console.warn(`Maximum ${maxFiles} files allowed`);
          break;
        }

        // Check file size
        if (file.size > maxSize) {
          console.warn(`File ${file.name} exceeds maximum size of ${formatFileSize(maxSize)}`);
          continue;
        }

        validFiles.push(file);

        // Add to state
        addAttachment({
          name: file.name,
          size: file.size,
          type: file.type,
          uploadProgress: 0,
        });
      }

      if (validFiles.length > 0 && onFilesSelected) {
        onFilesSelected(validFiles);
      }
    },
    [state.attachments.length, maxFiles, maxSize, addAttachment, onFilesSelected]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      handleFiles(e.target.files);
      e.target.value = ""; // Reset input
    },
    [handleFiles]
  );

  return (
    <div className={cn("space-y-3", className)}>
      {/* Drop Zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={cn(
          "relative border-2 border-dashed rounded-xl p-6 transition-all duration-200",
          "flex flex-col items-center justify-center gap-3 text-center",
          isDragOver
            ? "border-primary bg-primary/5 scale-[1.02]"
            : "border-border hover:border-primary/50 hover:bg-accent/50"
        )}
      >
        <input
          type="file"
          accept={accept}
          multiple
          onChange={handleInputChange}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
        <div
          className={cn(
            "w-12 h-12 rounded-full flex items-center justify-center transition-colors",
            isDragOver ? "bg-primary/20" : "bg-accent"
          )}
        >
          <Upload
            className={cn(
              "h-6 w-6 transition-colors",
              isDragOver ? "text-primary" : "text-muted-foreground"
            )}
          />
        </div>
        <div>
          <p className="text-sm font-medium">
            拖拽文件到此处，或{" "}
            <span className="text-primary">点击上传</span>
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            支持 PDF、Word、PPT、Excel、图片等格式，最大 {formatFileSize(maxSize)}
          </p>
        </div>
      </div>

      {/* File List */}
      {state.attachments.length > 0 && (
        <div className="space-y-2">
          {state.attachments.map((file) => {
            const Icon = getFileIcon(file.type);
            return (
              <Card
                key={file.id}
                className="flex items-center gap-3 p-3 bg-accent/30"
              >
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                  <Icon className="h-5 w-5 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatFileSize(file.size)}
                  </p>
                  {file.uploadProgress !== undefined && file.uploadProgress < 100 && (
                    <Progress
                      value={file.uploadProgress}
                      className="h-1 mt-1.5"
                    />
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
                  onClick={() => removeAttachment(file.id)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default FileUpload;

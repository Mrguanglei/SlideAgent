/**
 * 分享弹窗组件
 * 
 * 功能：
 * - 生成分享链接
 * - 复制链接
 * - 设置有效期
 */

import { useState, useEffect } from "react";
import { X, Link2, Copy, Check, Loader2, Clock, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

interface ShareModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: number;
  versionId?: number;
  title: string;
}

interface ShareInfo {
  share_id: string;
  share_url: string;
  expires_at: string;
  expire_days: number;
}

const EXPIRE_OPTIONS = [
  { days: 1, label: "1 天" },
  { days: 7, label: "7 天" },
  { days: 30, label: "30 天" },
];

export default function ShareModal({
  isOpen,
  onClose,
  projectId,
  versionId,
  title
}: ShareModalProps) {
  const [expireDays, setExpireDays] = useState(7);
  const [isCreating, setIsCreating] = useState(false);
  const [shareInfo, setShareInfo] = useState<ShareInfo | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 重置状态
  useEffect(() => {
    if (isOpen) {
      setShareInfo(null);
      setCopied(false);
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleCreateShare = async () => {
    setIsCreating(true);
    setError(null);

    try {
      const response = await fetch("/api/ppt/share", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          version_id: versionId,
          expire_days: expireDays
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "创建分享链接失败");
      }

      const data = await response.json();
      setShareInfo(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建分享链接失败");
    } finally {
      setIsCreating(false);
    }
  };

  const handleCopyLink = async () => {
    if (!shareInfo) return;

    const fullUrl = `${window.location.origin}${shareInfo.share_url}`;
    
    try {
      await navigator.clipboard.writeText(fullUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      // 降级方案
      const textarea = document.createElement("textarea");
      textarea.value = fullUrl;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleOpenLink = () => {
    if (!shareInfo) return;
    window.open(shareInfo.share_url, "_blank");
  };

  const formatExpireDate = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
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
          <h2 className="text-lg font-semibold">分享 PPT</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-muted rounded-lg transition-colors"
          >
            <X className="h-5 w-5 text-muted-foreground" />
          </button>
        </div>

        {/* 内容 */}
        <div className="p-6">
          {!shareInfo ? (
            // 创建分享链接
            <div className="space-y-6">
              {/* 标题预览 */}
              <div className="p-4 bg-muted/50 rounded-xl">
                <div className="text-sm text-muted-foreground mb-1">分享内容</div>
                <div className="font-medium truncate">{title}</div>
              </div>

              {/* 有效期选择 */}
              <div>
                <div className="text-sm text-muted-foreground mb-3 flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  链接有效期
                </div>
                <div className="flex gap-2">
                  {EXPIRE_OPTIONS.map((option) => (
                    <button
                      key={option.days}
                      onClick={() => setExpireDays(option.days)}
                      className={cn(
                        "flex-1 py-2 px-4 rounded-lg border-2 text-sm font-medium transition-all",
                        expireDays === option.days
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border hover:border-primary/50"
                      )}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 错误提示 */}
              {error && (
                <div className="p-3 bg-destructive/10 text-destructive text-sm rounded-lg">
                  {error}
                </div>
              )}

              {/* 创建按钮 */}
              <button
                onClick={handleCreateShare}
                disabled={isCreating}
                className="w-full py-3 bg-primary text-white rounded-xl hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {isCreating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    生成中...
                  </>
                ) : (
                  <>
                    <Link2 className="h-4 w-4" />
                    生成分享链接
                  </>
                )}
              </button>
            </div>
          ) : (
            // 显示分享链接
            <div className="space-y-6">
              {/* 成功提示 */}
              <div className="text-center py-4">
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Check className="h-8 w-8 text-green-600" />
                </div>
                <h3 className="text-lg font-semibold mb-1">分享链接已生成</h3>
                <p className="text-sm text-muted-foreground">
                  有效期至 {formatExpireDate(shareInfo.expires_at)}
                </p>
              </div>

              {/* 链接显示 */}
              <div className="flex items-center gap-2 p-3 bg-muted rounded-xl">
                <input
                  type="text"
                  readOnly
                  value={`${window.location.origin}${shareInfo.share_url}`}
                  className="flex-1 bg-transparent text-sm outline-none truncate"
                />
                <button
                  onClick={handleCopyLink}
                  className={cn(
                    "p-2 rounded-lg transition-colors",
                    copied
                      ? "bg-green-100 text-green-600"
                      : "hover:bg-background"
                  )}
                  title={copied ? "已复制" : "复制链接"}
                >
                  {copied ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </button>
                <button
                  onClick={handleOpenLink}
                  className="p-2 hover:bg-background rounded-lg transition-colors"
                  title="在新窗口打开"
                >
                  <ExternalLink className="h-4 w-4" />
                </button>
              </div>

              {/* 操作按钮 */}
              <div className="flex gap-3">
                <button
                  onClick={() => setShareInfo(null)}
                  className="flex-1 py-2.5 border border-border rounded-xl hover:bg-muted transition-colors"
                >
                  重新生成
                </button>
                <button
                  onClick={onClose}
                  className="flex-1 py-2.5 bg-primary text-white rounded-xl hover:bg-primary/90 transition-colors"
                >
                  完成
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

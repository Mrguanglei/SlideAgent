/**
 * useDownloadProgress
 * 管理导出/下载进度条状态
 */
import { useState, useRef, useCallback, useEffect } from "react";

export interface DownloadProgressState {
  percent: number;
  status: "running" | "success" | "error";
  label: string;
}

export function useDownloadProgress() {
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgressState | null>(null);
  const downloadHideTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (downloadHideTimerRef.current !== null) {
        window.clearTimeout(downloadHideTimerRef.current);
      }
    };
  }, []);

  const handleDownloadProgress = useCallback((payload: {
    status: "start" | "progress" | "complete" | "error";
    percent?: number;
    label?: string;
  }) => {
    if (downloadHideTimerRef.current !== null) {
      window.clearTimeout(downloadHideTimerRef.current);
      downloadHideTimerRef.current = null;
    }

    if (payload.status === "start") {
      setDownloadProgress({ percent: Math.max(0, Math.min(100, payload.percent ?? 0)), status: "running", label: payload.label || "正在导出" });
      return;
    }
    if (payload.status === "progress") {
      setDownloadProgress(prev => ({
        percent: Math.max(0, Math.min(100, payload.percent ?? prev?.percent ?? 0)),
        status: "running",
        label: payload.label || prev?.label || "正在导出",
      }));
      return;
    }
    if (payload.status === "complete") {
      setDownloadProgress({ percent: 100, status: "success", label: payload.label || "下载完成" });
      downloadHideTimerRef.current = window.setTimeout(() => setDownloadProgress(null), 1600);
      return;
    }
    if (payload.status === "error") {
      setDownloadProgress({ percent: Math.max(0, Math.min(100, payload.percent ?? 0)), status: "error", label: payload.label || "导出失败" });
      downloadHideTimerRef.current = window.setTimeout(() => setDownloadProgress(null), 2400);
    }
  }, []);

  return { downloadProgress, setDownloadProgress, handleDownloadProgress };
}

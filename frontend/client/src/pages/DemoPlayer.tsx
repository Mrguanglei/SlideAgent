import { motion } from "framer-motion";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Download,
  Pause,
  Play,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useParams } from "wouter";

interface PreviewResponse {
  images: string[];
  count?: number;
  downloadUrl?: string;
}

const AUTO_INTERVAL = 4000;

export default function DemoPlayer() {
  const [, setLocation] = useLocation();
  const params = useParams<{ name: string }>();
  const fileName = useMemo(() => {
    const raw = params?.name ?? "";
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  }, [params]);

  const [images, setImages] = useState<string[]>([]);
  const [current, setCurrent] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(true);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch(
          `/api/demo/preview?name=${encodeURIComponent(fileName)}`
        );
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail || "预览生成失败");
        }
        const data: PreviewResponse = await response.json();
        if (!active) return;
        setImages(data.images || []);
        setCurrent(0);
        setDownloadUrl(data.downloadUrl || null);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "预览生成失败");
      } finally {
        if (active) setLoading(false);
      }
    };

    if (fileName) {
      load();
    }

    return () => {
      active = false;
    };
  }, [fileName]);

  useEffect(() => {
    if (!playing || images.length <= 1) return;
    const timer = window.setInterval(() => {
      setCurrent(prev => (prev + 1) % images.length);
    }, AUTO_INTERVAL);
    return () => window.clearInterval(timer);
  }, [playing, images.length]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (images.length === 0) return;
      if (event.key === "ArrowRight") {
        setCurrent(prev => (prev + 1) % images.length);
        setPlaying(false);
      }
      if (event.key === "ArrowLeft") {
        setCurrent(prev => (prev - 1 + images.length) % images.length);
        setPlaying(false);
      }
      if (event.key === " ") {
        event.preventDefault();
        setPlaying(prev => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [images.length]);

  const title = fileName.replace(/\.pptx$/i, "");
  const currentImage = images[current] || "";

  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950 text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.18),transparent_55%),radial-gradient(circle_at_bottom,rgba(244,114,182,0.12),transparent_60%)]" />
      <div className="relative z-10 flex min-h-screen flex-col">
        <header className="container mx-auto flex items-center justify-between py-6">
          <button
            className="group flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
            onClick={() => setLocation("/demos")}
          >
            <ArrowLeft className="h-4 w-4 transition group-hover:-translate-x-0.5" />
            返回列表
          </button>
          <div className="text-center">
            <p className="font-display text-lg font-semibold">{title}</p>
            <p className="text-xs text-white/60">轮播预览</p>
          </div>
          {downloadUrl ? (
            <a
              href={downloadUrl}
              className="flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-slate-900"
            >
              <Download className="h-4 w-4" />
              下载
            </a>
          ) : (
            <div className="w-24" />
          )}
        </header>

        <main className="container mx-auto flex flex-1 flex-col items-center justify-center pb-10">
          {loading && (
            <div className="rounded-3xl border border-white/10 bg-white/5 px-8 py-6 text-sm text-white/70">
              正在生成预览，请稍候...
            </div>
          )}

          {error && (
            <div className="rounded-3xl border border-red-400/40 bg-red-500/10 px-8 py-6 text-center text-sm text-red-100">
              <p>{error}</p>
              <p className="mt-2 text-xs text-red-100/70">
                如果首次生成失败，请确认后端已安装 LibreOffice 与 poppler。
              </p>
            </div>
          )}

          {!loading && !error && images.length > 0 && (
            <div className="w-full">
              <div className="relative mx-auto aspect-[16/9] w-full max-w-5xl overflow-hidden rounded-[32px] border border-white/10 bg-black shadow-[0_30px_80px_rgba(15,23,42,0.6)]">
                <motion.img
                  key={currentImage}
                  src={currentImage}
                  alt={title}
                  className="h-full w-full object-contain"
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                />
                <button
                  className="absolute left-4 top-1/2 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full bg-white/10 text-white transition hover:bg-white/20"
                  onClick={() => {
                    setCurrent(prev => (prev - 1 + images.length) % images.length);
                    setPlaying(false);
                  }}
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>
                <button
                  className="absolute right-4 top-1/2 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full bg-white/10 text-white transition hover:bg-white/20"
                  onClick={() => {
                    setCurrent(prev => (prev + 1) % images.length);
                    setPlaying(false);
                  }}
                >
                  <ChevronRight className="h-5 w-5" />
                </button>
              </div>

              <div className="mt-6 flex flex-wrap items-center justify-center gap-4 text-sm text-white/70">
                <span>
                  {current + 1} / {images.length}
                </span>
                <button
                  className="inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm text-white transition hover:bg-white/10"
                  onClick={() => setPlaying(prev => !prev)}
                >
                  {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                  {playing ? "暂停" : "播放"}
                </button>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

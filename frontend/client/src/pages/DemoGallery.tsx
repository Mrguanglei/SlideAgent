import { motion } from "framer-motion";
import type { Variants } from "framer-motion";
import { ArrowRight, Download, FileText, Play } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useLocation } from "wouter";

interface DemoItem {
  name: string;
  size: number;
  modifiedAt: string;
}

const container: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: {
    opacity: 1,
    y: 0,
    transition: { staggerChildren: 0.08, duration: 0.4, ease: "easeOut" },
  },
};

const item: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } },
};

const formatSize = (bytes: number) => {
  if (!bytes && bytes !== 0) return "-";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(2)} MB`;
};

const formatDate = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString();
};

export default function DemoGallery() {
  const [, setLocation] = useLocation();
  const [items, setItems] = useState<DemoItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const response = await fetch("/api/demo/list");
        const data = await response.json();
        if (active) {
          setItems(data.items || []);
        }
      } catch (error) {
        console.warn("Failed to load demo list", error);
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, []);

  const demos = useMemo(() => {
    return items.map(demo => ({
      ...demo,
      title: demo.name.replace(/\.pptx$/i, ""),
    }));
  }, [items]);

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#f7f6f2] text-slate-900">
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(800px circle at 10% -10%, rgba(59, 130, 246, 0.18), transparent 60%), radial-gradient(640px circle at 90% 0%, rgba(244, 114, 182, 0.18), transparent 62%), linear-gradient(180deg, #fbfaf6 0%, #f6f7ff 45%, #fff5ee 100%)",
        }}
      />
      <div className="relative z-10">
        <header className="container mx-auto flex items-center justify-between py-6">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white shadow-lg ring-1 ring-slate-900/10">
              <img
                src="/favicon.png"
                alt="SlideAgent"
                className="h-7 w-7 object-contain"
              />
            </div>
            <div>
              <p className="font-display text-lg font-semibold tracking-tight">SlideAgent</p>
              <p className="text-xs text-slate-500">演示 Demo 预览</p>
            </div>
          </div>
          <button
            className="group flex items-center gap-2 rounded-full border border-slate-900/10 bg-white/80 px-4 py-2 text-sm font-medium text-slate-900 shadow-sm transition hover:-translate-y-0.5 hover:border-slate-900/20 hover:bg-white"
            onClick={() => setLocation("/")}
          >
            返回首页
            <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
          </button>
        </header>

        <main className="container mx-auto pb-20">
          <motion.div variants={container} initial="hidden" animate="show">
            <motion.div variants={item} className="max-w-2xl">
              <h1 className="font-display text-3xl font-semibold text-slate-900 md:text-4xl">
                Demo PPT 
              </h1>
              <p className="mt-3 text-sm text-slate-600 md:text-base">
                这里列出本地的 PPT demo 文件。支持“转图片 + 轮播播放”在线预览，也可以直接下载原始 PPTX。
              </p>
            </motion.div>

            <motion.div
              variants={item}
              className="mt-10 grid gap-4 md:grid-cols-2"
            >
              {loading && (
                <div className="rounded-[24px] border border-slate-900/10 bg-white/70 p-6 shadow-sm">
                  <p className="text-sm text-slate-500">正在读取 demo 列表...</p>
                </div>
              )}

              {!loading && demos.length === 0 && (
                <div className="rounded-[24px] border border-slate-900/10 bg-white/70 p-6 shadow-sm">
                  <p className="text-sm text-slate-500">
                    未找到 PPT demo。请确认文件在 `PPT_demo/` 目录下。
                  </p>
                </div>
              )}

              {demos.map(demo => (
                <motion.div
                  key={demo.name}
                  variants={item}
                  className="rounded-[24px] border border-slate-900/10 bg-white/80 p-6 shadow-sm"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-display text-lg font-semibold text-slate-900">
                        {demo.title}
                      </p>
                      <p className="mt-2 text-xs text-slate-500">
                        {formatSize(demo.size)} · {formatDate(demo.modifiedAt)}
                      </p>
                    </div>
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-900 text-white">
                      <FileText className="h-5 w-5" />
                    </div>
                  </div>
                  <div className="mt-6 flex flex-wrap gap-3">
                    <button
                      className="inline-flex items-center gap-2 rounded-full border border-slate-900/15 bg-white/80 px-5 py-2 text-sm font-semibold text-slate-900"
                      onClick={() =>
                        setLocation(`/demos/${encodeURIComponent(demo.name)}`)
                      }
                    >
                      <Play className="h-4 w-4" />
                      轮播预览
                    </button>
                    <a
                      href={`/api/demo/file?name=${encodeURIComponent(demo.name)}`}
                      className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white"
                    >
                      <Download className="h-4 w-4" />
                      下载 PPTX
                    </a>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          </motion.div>
        </main>
      </div>
    </div>
  );
}

import { motion } from "framer-motion";
import {
  ArrowRight,
  Layers,
  Palette,
  Rocket,
  Sparkles,
  Wand2,
} from "lucide-react";
import type { CSSProperties, MouseEvent } from "react";
import { useRef, useState } from "react";
import { useLocation } from "wouter";

const stats = [
  { label: "模板风格", value: "120+" },
  { label: "平均出稿", value: "3 分钟" },
  { label: "素材库", value: "4,800+" },
];

const features = [
  {
    title: "多模型协作",
    desc: "结构、视觉与内容并行编排，自动拆解重点。",
    icon: Sparkles,
  },
  {
    title: "一键排版",
    desc: "自动生成标题层级、配色和动效组合。",
    icon: Palette,
  },
  {
    title: "可编辑大纲",
    desc: "实时预览与迭代，节奏与信息密度可控。",
    icon: Layers,
  },
];

const steps = [
  {
    title: "输入目标",
    desc: "一句话需求即可，自动解析受众与语气。",
  },
  {
    title: "生成结构",
    desc: "提炼提纲 + 逻辑链路，先看框架再上色。",
  },
  {
    title: "输出演示",
    desc: "支持分享链接、播放预览与导出格式。",
  },
];

const container = {
  hidden: { opacity: 0, y: 18 },
  show: {
    opacity: 1,
    y: 0,
    transition: { staggerChildren: 0.12, duration: 0.6, ease: "easeOut" as const },
  },
};

const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: "easeOut" as const } },
};

export default function Landing() {
  const [, setLocation] = useLocation();
  const spotlightRef = useRef<HTMLDivElement>(null);
  const [spotlight, setSpotlight] = useState({ x: 140, y: 120 });

  const handleMouseMove = (event: MouseEvent<HTMLDivElement>) => {
    const rect = spotlightRef.current?.getBoundingClientRect();
    if (!rect) return;
    setSpotlight({ x: event.clientX - rect.left, y: event.clientY - rect.top });
  };

  const spotlightStyle = {
    "--spot-x": `${spotlight.x}px`,
    "--spot-y": `${spotlight.y}px`,
  } as CSSProperties;

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#f7f6f2] text-slate-900">
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(900px circle at 12% -10%, rgba(59, 130, 246, 0.18), transparent 60%), radial-gradient(800px circle at 88% 10%, rgba(249, 168, 212, 0.18), transparent 62%), radial-gradient(600px circle at 70% 90%, rgba(234, 179, 8, 0.15), transparent 55%), linear-gradient(180deg, #fbfaf6 0%, #f5f7ff 40%, #fff5ee 100%)",
        }}
      />
      <div className="pointer-events-none absolute inset-0 opacity-60 [background-image:linear-gradient(rgba(15,23,42,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(15,23,42,0.04)_1px,transparent_1px)] [background-size:32px_32px]" />

      <motion.div
        className="absolute -left-24 top-32 h-72 w-72 rounded-full bg-[#2dd4bf]/20 blur-3xl"
        animate={{ y: [0, -18, 0], x: [0, 12, 0] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute right-8 top-20 h-52 w-52 rounded-full bg-[#fb7185]/20 blur-3xl"
        animate={{ y: [0, 22, 0], x: [0, -14, 0] }}
        transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
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
              <p className="text-xs text-slate-500">AI 驱动的演示工坊</p>
            </div>
          </div>
          <nav className="hidden items-center gap-6 text-sm text-slate-600 md:flex">
            <span>产品特性</span>
            <span>工作流</span>
            <span>模板生态</span>
          </nav>
          <button
            className="group flex items-center gap-2 rounded-full border border-slate-900/10 bg-white/80 px-4 py-2 text-sm font-medium text-slate-900 shadow-sm transition hover:-translate-y-0.5 hover:border-slate-900/20 hover:bg-white"
            onClick={() => setLocation("/chat")}
          >
            立即开始
            <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
          </button>
        </header>

        <main className="container mx-auto grid gap-12 pb-20 pt-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <motion.div variants={container} initial="hidden" animate="show">
            <motion.div variants={item} className="inline-flex items-center gap-2 rounded-full border border-slate-900/10 bg-white/70 px-4 py-2 text-xs font-medium text-slate-700 shadow-sm">
              <span className="font-mono-alt text-[11px] text-slate-500">PPT vNext</span>
              <span>让每个演示更有说服力</span>
            </motion.div>
            <motion.h1
              variants={item}
              className="font-display mt-6 text-balance text-4xl font-semibold leading-tight text-slate-900 md:text-5xl"
            >
              从一句话需求，
              <span className="text-[#2563eb]">秒级</span>生成可讲的演示文稿
            </motion.h1>
            <motion.p variants={item} className="mt-5 max-w-xl text-base text-slate-600 md:text-lg">
              SlideAgent 把内容提炼、结构规划、视觉排版一次完成。保留你的控场能力，同时让每次汇报更快更稳。
            </motion.p>
            <motion.div variants={item} className="mt-8 flex flex-wrap items-center gap-4">
              <motion.button
                whileHover={{ y: -2, boxShadow: "0 18px 40px rgba(37, 99, 235, 0.25)" }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-2 rounded-full bg-slate-900 px-6 py-3 text-sm font-semibold text-white"
                onClick={() => setLocation("/chat")}
              >
                立即开始
                <Rocket className="h-4 w-4" />
              </motion.button>
              <motion.button
                whileHover={{ y: -2 }}
                className="flex items-center gap-2 rounded-full border border-slate-900/15 bg-white/80 px-6 py-3 text-sm font-semibold text-slate-900"
                onClick={() => setLocation("/demos")}
              >
                预览效果
                <Wand2 className="h-4 w-4" />
              </motion.button>
            </motion.div>
            <motion.div variants={item} className="mt-10 flex flex-wrap items-center gap-6">
              {stats.map(stat => (
                <div key={stat.label} className="rounded-2xl border border-slate-900/10 bg-white/70 px-5 py-3 shadow-sm">
                  <div className="font-display text-2xl font-semibold text-slate-900">{stat.value}</div>
                  <div className="text-xs text-slate-500">{stat.label}</div>
                </div>
              ))}
            </motion.div>
          </motion.div>

          <motion.div
            className="relative"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: "easeOut" }}
          >
            <motion.div
              className="absolute -right-10 -top-10 h-32 w-32 rounded-full border border-white/70 bg-white/60 shadow-lg backdrop-blur"
              animate={{ rotate: [0, 8, 0] }}
              transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            />
            <motion.div
              className="absolute -left-8 bottom-8 h-24 w-24 rounded-3xl bg-[#facc15]/25 backdrop-blur"
              animate={{ y: [0, -10, 0] }}
              transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
            />
            <div className="relative rounded-[32px] border border-slate-900/10 bg-white/70 p-6 shadow-[0_25px_60px_rgba(15,23,42,0.15)] backdrop-blur">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-display text-lg font-semibold text-slate-900">演示生成面板</p>
                  <p className="text-xs text-slate-500">结构、视觉、图表自动协作</p>
                </div>
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">
                  Live
                </span>
              </div>
              <div className="mt-6 grid gap-4">
                <div className="rounded-2xl border border-slate-900/10 bg-white px-4 py-3">
                  <p className="text-xs text-slate-500">Prompt</p>
                  <p className="mt-2 text-sm font-medium text-slate-900">
                    为年度发布会准备一套产品战略演示
                  </p>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-2xl border border-slate-900/10 bg-gradient-to-br from-slate-900 to-slate-700 p-4 text-white">
                    <p className="text-xs text-white/70">结构分层</p>
                    <p className="mt-3 font-display text-lg">7 章节 · 28 页</p>
                    <p className="mt-2 text-xs text-white/70">战略 · 市场 · 产品 · 增长</p>
                  </div>
                  <div className="rounded-2xl border border-slate-900/10 bg-white p-4">
                    <p className="text-xs text-slate-500">视觉方案</p>
                    <div className="mt-3 flex items-center gap-2">
                      <span className="h-3 w-3 rounded-full bg-[#2563eb]" />
                      <span className="h-3 w-3 rounded-full bg-[#f97316]" />
                      <span className="h-3 w-3 rounded-full bg-[#14b8a6]" />
                    </div>
                    <p className="mt-3 text-xs text-slate-500">轻盈 / 清晰 / 锐利</p>
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-900/10 bg-white px-4 py-4">
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span>实时生成</span>
                    <span className="font-mono-alt">98%</span>
                  </div>
                  <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                    <motion.div
                      className="h-full rounded-full bg-gradient-to-r from-[#2563eb] via-[#0ea5e9] to-[#14b8a6]"
                      initial={{ width: "22%" }}
                      animate={{ width: ["22%", "98%", "22%"] }}
                      transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </main>

        <section className="container mx-auto pb-20">
          <div
            ref={spotlightRef}
            className="group relative rounded-[32px] border border-slate-900/10 bg-white/70 px-6 py-10 shadow-lg backdrop-blur"
            style={spotlightStyle}
            onMouseMove={handleMouseMove}
          >
            <div
              className="pointer-events-none absolute inset-0 rounded-[32px] opacity-0 transition duration-300 group-hover:opacity-100"
              style={{
                background:
                  "radial-gradient(280px circle at var(--spot-x) var(--spot-y), rgba(56, 189, 248, 0.18), transparent 65%)",
              }}
            />
            <div className="relative z-10">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500">核心能力</p>
                  <h2 className="font-display mt-2 text-2xl font-semibold text-slate-900">
                    一套工作流完成内容到视觉
                  </h2>
                </div>
                <div className="hidden items-center gap-2 rounded-full border border-slate-900/10 bg-white/70 px-3 py-1 text-xs text-slate-500 md:flex">
                  <Sparkles className="h-4 w-4 text-[#0ea5e9]" />
                  与你的团队实时协作
                </div>
              </div>
              <div className="mt-8 grid gap-4 md:grid-cols-3">
                {features.map(feature => (
                  <motion.div
                    key={feature.title}
                    whileHover={{ y: -6 }}
                    className="rounded-3xl border border-slate-900/10 bg-white p-5 shadow-sm"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 text-white">
                      <feature.icon className="h-5 w-5" />
                    </div>
                    <h3 className="font-display mt-4 text-lg font-semibold text-slate-900">
                      {feature.title}
                    </h3>
                    <p className="mt-2 text-sm text-slate-600">{feature.desc}</p>
                  </motion.div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="container mx-auto grid gap-10 pb-20 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
          <div className="rounded-[28px] border border-slate-900/10 bg-white/70 p-8 shadow-lg backdrop-blur">
            <p className="text-xs font-medium text-slate-500">工作流</p>
            <h2 className="font-display mt-3 text-2xl font-semibold text-slate-900">
              从需求到演示，三步完成
            </h2>
            <div className="mt-6 space-y-4">
              {steps.map((step, index) => (
                <div key={step.title} className="flex gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white">
                    0{index + 1}
                  </div>
                  <div>
                    <p className="font-display text-base font-semibold text-slate-900">
                      {step.title}
                    </p>
                    <p className="text-sm text-slate-600">{step.desc}</p>
                  </div>
                </div>
              ))}
            </div>
            <button
              className="mt-8 inline-flex items-center gap-2 rounded-full border border-slate-900/15 bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white"
              onClick={() => setLocation("/chat")}
            >
              立即开始
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <motion.div
              whileHover={{ y: -6 }}
              className="rounded-[28px] border border-slate-900/10 bg-gradient-to-br from-white via-white to-slate-50 p-6 shadow-lg"
            >
              <p className="text-xs font-medium text-slate-500">AI 生成</p>
              <p className="font-display mt-3 text-xl font-semibold text-slate-900">
                结构先行，视觉跟随
              </p>
              <p className="mt-2 text-sm text-slate-600">
                每一页都有清晰的叙事目的与视觉锚点。
              </p>
              <div className="mt-6 space-y-2">
                <div className="h-2 w-full rounded-full bg-slate-100">
                  <div className="h-full w-[78%] rounded-full bg-[#2563eb]" />
                </div>
                <div className="h-2 w-full rounded-full bg-slate-100">
                  <div className="h-full w-[52%] rounded-full bg-[#f97316]" />
                </div>
              </div>
            </motion.div>
            <motion.div
              whileHover={{ y: -6 }}
              className="rounded-[28px] border border-slate-900/10 bg-slate-900 p-6 text-white shadow-lg"
            >
              <p className="text-xs font-medium text-white/60">实时共享</p>
              <p className="font-display mt-3 text-xl font-semibold">链接即演示</p>
              <p className="mt-2 text-sm text-white/70">
                一键生成可播放链接，支持评审与协作批注。
              </p>
              <div className="mt-6 rounded-2xl bg-white/10 p-3 text-xs text-white/70">
                share.pptagent.ai/demo/launch
              </div>
            </motion.div>
          </div>
        </section>

        <section className="container mx-auto pb-24">
          <div className="rounded-[32px] border border-slate-900/10 bg-slate-900 px-8 py-12 text-white shadow-[0_25px_60px_rgba(15,23,42,0.3)]">
            <div className="flex flex-wrap items-center justify-between gap-6">
              <div>
                <p className="text-xs font-medium text-white/60">立即体验</p>
                <h2 className="font-display mt-3 text-2xl font-semibold md:text-3xl">
                  把你的想法变成可以讲的演示
                </h2>
                <p className="mt-3 text-sm text-white/70">
                  从一页到整套提案，SlideAgent 让你只关注内容。
                </p>
              </div>
              <button
                className="flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-900"
                onClick={() => setLocation("/chat")}
              >
                立即开始
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

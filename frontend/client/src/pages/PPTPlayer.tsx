import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "wouter";
import { Loader2, ChevronLeft, ChevronRight, X, Maximize2 } from "lucide-react";
import { getPPTProject } from "@/lib/api";
import type { PPTProject, PPTSlide } from "@/types";
import { cn } from "@/lib/utils";

export default function PPTPlayer() {
    const { id } = useParams<{ id: string }>();
    const [project, setProject] = useState<PPTProject | null>(null);
    const [slides, setSlides] = useState<PPTSlide[]>([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [layout, setLayout] = useState({ scale: 1, x: 0, y: 0 });
    const containerRef = useRef<HTMLDivElement>(null);

    const [showControls, setShowControls] = useState(false);
    const controlsTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);

    // 加载数据
    useEffect(() => {
        if (!id) {
            setError("未提供项目ID");
            setLoading(false);
            return;
        }

        const loadProject = async () => {
            try {
                const projectId = parseInt(id);
                const data = await getPPTProject(projectId);

                // 构造兼容的前端数据对象
                // 注意：后端返回的结构只有 versions，没有 slides 和 current_version 字段
                let processedProject = { ...data } as any;

                // 查找最新版本
                let latestVersion = null;
                if (data.versions && data.versions.length > 0) {
                    // 假设 versions 是按时间排序的，取最后一个；或者按 version_number 排序
                    latestVersion = data.versions.sort((a: any, b: any) => b.version_number - a.version_number)[0];
                    processedProject.current_version = latestVersion;
                    processedProject.slides = latestVersion.slides || [];
                }

                setProject(processedProject);

                const slidesData = processedProject.slides || [];

                if (slidesData.length > 0) {
                    const sortedSlides = slidesData.sort((a: any, b: any) => a.page_number - b.page_number);
                    setSlides(sortedSlides);
                } else {
                    console.warn('❌ 未找到幻灯片数据，项目结构:', JSON.stringify(data, null, 2));
                    setError("该项目没有幻灯片数据");
                }
            } catch (err) {
                console.error("加载PPT失败:", err);
                setError("加载PPT失败，请稍后重试");
            } finally {
                setLoading(false);
            }
        };

        loadProject();
    }, [id]);

    // 计算缩放比例和位置
    useEffect(() => {
        const handleResize = () => {
            const windowWidth = window.innerWidth;
            const windowHeight = window.innerHeight;
            const slideWidth = 1280;
            const slideHeight = 720;

            // 保持比例缩放，填满屏幕
            const scale = Math.min(windowWidth / slideWidth, windowHeight / slideHeight);

            // 计算居中偏移量
            const x = (windowWidth - slideWidth * scale) / 2;
            const y = (windowHeight - slideHeight * scale) / 2;

            setLayout({ scale, x, y });
        };

        window.addEventListener("resize", handleResize);
        handleResize();

        return () => window.removeEventListener("resize", handleResize);
    }, []);

    // 键盘控制
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "ArrowRight" || e.key === " " || e.key === "Enter") {
                if (currentIndex < slides.length - 1) {
                    setCurrentIndex(prev => prev + 1);
                }
            } else if (e.key === "ArrowLeft") {
                if (currentIndex > 0) {
                    setCurrentIndex(prev => prev - 1);
                }
            } else if (e.key === "Escape") {
                // 如果全屏则退出全屏，否则不做处理（或者关闭窗口）
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                }
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [currentIndex, slides.length]);

    // 处理控制条显示
    const handleMouseMove = useCallback(() => {
        setShowControls(true);
        if (controlsTimeoutRef.current) {
            clearTimeout(controlsTimeoutRef.current);
        }
        controlsTimeoutRef.current = setTimeout(() => {
            setShowControls(false);
        }, 3000);
    }, []);

    // 注入强制样式的函数
    const processSlideHtml = (slide: string): string => {
        const fontLinks = `
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <link href="https://cdn.cn.font.mi.com/font/css?family=MiSans:300,400,500,600,700:Chinese_Simplify,Latin&display=swap" rel="stylesheet">
      <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    `;
        const forceStyles = `
      ${fontLinks}
      <style>
        html, body {
          width: 1280px !important;
          height: 720px !important;
          max-width: 1280px !important;
          max-height: 720px !important;
          overflow: hidden !important;
          margin: 0 !important;
          padding: 0 !important;
          background-color: transparent !important;
        }
        .slide, [class*="slide"] {
          width: 1280px !important;
          height: 720px !important;
          max-height: 720px !important;
          overflow: hidden !important;
        }
        /* 隐藏滚动条 */
        ::-webkit-scrollbar {
          display: none;
        }
      </style>
    `;

        let processedSlide = slide;
        if (slide.includes("</head>")) {
            processedSlide = slide.replace("</head>", forceStyles + "</head>");
        } else if (slide.includes("<body")) {
            processedSlide = slide.replace("<body", forceStyles + "<body");
        } else {
            processedSlide = forceStyles + slide;
        }
        return processedSlide;
    };

    const handleFullscreen = () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    };

    if (loading) {
        return (
            <div className="h-screen w-screen bg-black flex items-center justify-center text-white">
                <Loader2 className="h-10 w-10 animate-spin mb-4" />
                <p>加载演示文稿...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="h-screen w-screen bg-black flex flex-col items-center justify-center text-white">
                <p className="text-xl mb-4">{error}</p>
                <button
                    onClick={() => window.close()}
                    className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                >
                    关闭
                </button>
            </div>
        );
    }

    const currentSlide = slides[currentIndex];
    // 预加载下一页
    const nextSlide = currentIndex < slides.length - 1 ? slides[currentIndex + 1] : null;

    return (
        <div
            className="h-screen w-screen bg-black overflow-hidden relative cursor-none"
            style={{ cursor: showControls ? 'default' : 'none' }}
            onMouseMove={handleMouseMove}
            onClick={() => {
                // 点击右侧下一页，点击左侧上一页
                // 这里简单处理为点击任意处下一页，或者根据区域判断
            }}
        >
            {/* 幻灯片容器 - 绝对定位 + 手动居中 */}
            <div
                className="absolute top-0 left-0 origin-top-left"
                style={{
                    width: '1280px',
                    height: '720px',
                    transform: `translate(${layout.x}px, ${layout.y}px) scale(${layout.scale})`,
                }}
            >
                <iframe
                    key={`play-${currentIndex}`}
                    srcDoc={processSlideHtml(currentSlide.html_content)}
                    className="w-full h-full border-0 bg-white"
                    title={`Slide ${currentIndex + 1}`}
                    sandbox="allow-same-origin allow-scripts"
                    scrolling="no"
                />
                {/* 点击覆盖层 - 用于翻页交互 */}
                <div className="absolute inset-0 grid grid-cols-2 z-10">
                    <div
                        className="h-full cursor-w-resize"
                        onClick={() => currentIndex > 0 && setCurrentIndex(prev => prev - 1)}
                        title="上一页"
                    />
                    <div
                        className="h-full cursor-e-resize"
                        onClick={() => currentIndex < slides.length - 1 && setCurrentIndex(prev => prev + 1)}
                        title="下一页"
                    />
                </div>
            </div>

            {/* 预加载 iframe (不可见) */}
            {nextSlide && (
                <iframe
                    srcDoc={processSlideHtml(nextSlide.html_content)}
                    className="hidden"
                    sandbox="allow-same-origin allow-scripts"
                />
            )}

            {/* 底部控制条 */}
            <div
                className={cn(
                    "fixed bottom-0 left-0 right-0 h-16 bg-black/50 backdrop-blur-sm flex items-center justify-between px-8 text-white transition-transform duration-300 z-50",
                    showControls ? "translate-y-0" : "translate-y-full"
                )}
            >
                <div className="flex items-center gap-4">
                    <span className="font-medium truncate max-w-[300px]">{project?.title}</span>
                </div>

                <div className="flex items-center gap-4">
                    <button
                        onClick={() => currentIndex > 0 && setCurrentIndex(prev => prev - 1)}
                        disabled={currentIndex === 0}
                        className="p-2 hover:bg-white/10 rounded-full disabled:opacity-50 transition-colors"
                        title="上一页 (Left Arrow)"
                    >
                        <ChevronLeft className="h-6 w-6" />
                    </button>

                    <span className="font-mono text-sm">
                        {currentIndex + 1} / {slides.length}
                    </span>

                    <button
                        onClick={() => currentIndex < slides.length - 1 && setCurrentIndex(prev => prev + 1)}
                        disabled={currentIndex === slides.length - 1}
                        className="p-2 hover:bg-white/10 rounded-full disabled:opacity-50 transition-colors"
                        title="下一页 (Right Arrow / Space)"
                    >
                        <ChevronRight className="h-6 w-6" />
                    </button>
                </div>

                <div className="flex items-center gap-4">
                    <button
                        onClick={handleFullscreen}
                        className="p-2 hover:bg-white/10 rounded-full transition-colors"
                        title="全屏"
                    >
                        <Maximize2 className="h-5 w-5" />
                    </button>
                    <button
                        onClick={() => window.close()}
                        className="p-2 hover:bg-white/10 rounded-full transition-colors"
                        title="关闭"
                    >
                        <X className="h-5 w-5" />
                    </button>
                </div>
            </div>
        </div>
    );
}

import { useRef, useEffect, RefObject } from "react";
import { Loader2 } from "lucide-react";
import type { PPTViewMode, PPTProject } from "@/types";
import EditablePPTPreview, { type EditablePPTPreviewRef } from "./EditablePPTPreview";

interface PPTPreviewPanelProps {
  pptHtmlCode: string;
  pptViewMode: PPTViewMode;
  pptPreviewScrollRef: RefObject<HTMLDivElement>;
  pptCodeScrollRef: RefObject<HTMLDivElement>;
  targetSlideIndex?: number;
  isEditMode?: boolean;
  onSaveSlide?: (slideId: number, htmlContent: string) => Promise<void>;
  pptProject?: PPTProject | null;
  editablePPTRef?: RefObject<EditablePPTPreviewRef>;
}

export default function PPTPreviewPanel({
  pptHtmlCode,
  pptViewMode,
  pptPreviewScrollRef,
  pptCodeScrollRef,
  targetSlideIndex,
  isEditMode = false,
  onSaveSlide,
  pptProject,
  editablePPTRef,
}: PPTPreviewPanelProps) {
  const slideRefsPreview = useRef<(HTMLDivElement | null)[]>([]);
  const slideRefsCode = useRef<(HTMLDivElement | null)[]>([]);

  // 当 targetSlideIndex 改变时，滚动到对应的幻灯片
  useEffect(() => {
    if (targetSlideIndex !== undefined && targetSlideIndex >= 0) {
      const slideRefs = pptViewMode === "preview" ? slideRefsPreview : slideRefsCode;
      const targetSlide = slideRefs.current[targetSlideIndex];
      if (targetSlide) {
        targetSlide.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }, [targetSlideIndex, pptViewMode]);

  // 注入强制样式的函数
  const processSlideHtml = (slide: string): string => {
    const fontLinks = `
      <!-- Material Icons -->
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <!-- MiSans 字体 -->
      <link href="https://cdn.cn.font.mi.com/font/css?family=MiSans:300,400,500,600,700:Chinese_Simplify,Latin&display=swap" rel="stylesheet">
      <!-- Google Fonts 备用 -->
      <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    `;
    const forceStyles = `
      ${fontLinks}
      <style>
        .material-icons {
          font-family: 'Material Icons', sans-serif;
          font-weight: normal;
          font-style: normal;
          font-size: 24px;
          line-height: 1;
          letter-spacing: normal;
          text-transform: none;
          display: inline-block;
          white-space: nowrap;
          word-wrap: normal;
          direction: ltr;
          -webkit-font-smoothing: antialiased;
        }
        html, body {
          width: 1280px !important;
          height: 720px !important;
          max-width: 1280px !important;
          max-height: 720px !important;
          overflow: hidden !important;
          margin: 0 !important;
          padding: 0 !important;
        }
        .slide, [class*="slide"] {
          width: 1280px !important;
          height: 720px !important;
          max-height: 720px !important;
          overflow: hidden !important;
        }
        * {
          box-sizing: border-box !important;
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

  // 获取 slides 数据 - 优先从 current_version.slides，否则从 project.slides
  const slides = pptProject?.current_version?.slides || (pptProject as any)?.slides;
  const hasSlides = slides && slides.length > 0;

  // 调试日志
  console.log('[PPTPreviewPanel] 状态:', {
    isEditMode,
    pptViewMode,
    hasSlides,
    slidesCount: slides?.length,
    hasSaveCallback: !!onSaveSlide,
    slideSource: pptProject?.current_version?.slides ? 'current_version.slides' : (pptProject as any)?.slides ? 'project.slides' : 'none'
  });

  return (
    <div
      className="bg-gray-50/50 h-full overflow-auto"
      ref={pptViewMode === "preview" ? pptPreviewScrollRef : pptCodeScrollRef}
    >
      {pptViewMode === "preview" ? (
        <>
          {/* 编辑模式且有 PPT 项目数据时，使用 EditablePPTPreview */}
          {isEditMode && hasSlides && onSaveSlide ? (
            <>
              {console.log('✅ 渲染 EditablePPTPreview')}
              <EditablePPTPreview
                ref={editablePPTRef}
                slides={slides}
                isEditMode={isEditMode}
                onSaveSlide={onSaveSlide}
              />
            </>
          ) : (
            <>
              {console.log('❌ 渲染普通预览')}
              {/* PPT 预览区域 - 垂直流式排列 */}
              <div className="p-8 space-y-8">
                {pptHtmlCode ? (
                  <>
                    {(() => {
                      const slidesHtml = pptHtmlCode
                        .split(/(?=<!DOCTYPE html>)/i)
                        .filter((html: string) => html.trim());
                      slideRefsPreview.current = [];

                      return slidesHtml.map((slide: string, idx: number) => {
                        const containerWidth = 836;
                        const slideWidth = 1280;
                        const slideHeight = 720;
                        const scale = containerWidth / slideWidth;
                        const scaledHeight = slideHeight * scale;
                        const processedSlide = processSlideHtml(slide);

                        return (
                          <div
                            key={idx}
                            className="flex flex-col gap-3"
                            ref={(el) => {
                              slideRefsPreview.current[idx] = el;
                            }}
                          >
                            {/* 页码标识 */}
                            <div className="flex items-center gap-2 px-1">
                              <span className="text-xs font-medium text-muted-foreground bg-muted px-2 py-0.5 rounded">
                                第 {idx + 1} 页
                              </span>
                              <div className="h-[1px] flex-1 bg-border/50"></div>
                              <span className="text-[10px] text-muted-foreground/50 font-mono">
                                1280 × 720
                              </span>
                            </div>

                            {/* PPT 容器 */}
                            <div
                              className="relative shadow-xl rounded-xl bg-white border border-border/50 overflow-hidden"
                              style={{
                                width: `${containerWidth}px`,
                                height: `${scaledHeight}px`,
                              }}
                            >
                              <iframe
                                key={`preview-${idx}-${pptViewMode}`}
                                srcDoc={processedSlide}
                                className="border-0"
                                title={`Slide ${idx + 1}`}
                                sandbox="allow-same-origin allow-scripts"
                                scrolling="no"
                                style={{
                                  width: `${slideWidth}px`,
                                  height: `${slideHeight}px`,
                                  transform: `scale(${scale})`,
                                  transformOrigin: "top left",
                                  overflow: "hidden",
                                  margin: 0,
                                  padding: 0,
                                  border: "none",
                                }}
                              />
                            </div>
                          </div>
                        );
                      });
                    })()}
                  </>
                ) : (
                  <div className="flex items-center justify-center h-[60vh]">
                    <div className="text-sm text-muted-foreground text-center">
                      <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
                      正在生成 PPT...
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </>
      ) : (
        <>
          {/* 代码区域 - 分页显示代码块 */}
          <div className="p-6 space-y-6">
            {pptHtmlCode ? (
              <>
                {(() => {
                  const slidesHtml = pptHtmlCode
                    .split(/(?=<!DOCTYPE html>)/i)
                    .filter((html: string) => html.trim());
                  const containerWidth = 836;
                  const slideHeight = 470.25;
                  slideRefsCode.current = [];

                  return slidesHtml.map((slide: string, idx: number) => (
                    <div
                      key={idx}
                      className="flex flex-col gap-3"
                      ref={(el) => {
                        slideRefsCode.current[idx] = el;
                      }}
                    >
                      {/* 代码页码标识 */}
                      <div className="flex items-center justify-between px-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-muted-foreground bg-muted px-2 py-0.5 rounded">
                            第 {idx + 1} 页 代码
                          </span>
                          <span className="text-[10px] text-muted-foreground/40 font-mono">
                            HTML / CSS
                          </span>
                        </div>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(slide);
                          }}
                          className="text-[10px] text-primary hover:underline font-medium"
                        >
                          复制代码
                        </button>
                      </div>

                      {/* 代码块容器 */}
                      <div
                        className="relative bg-white border border-border rounded-xl overflow-auto shadow-sm"
                        style={{
                          width: `${containerWidth}px`,
                          height: `${slideHeight}px`,
                        }}
                      >
                        <pre className="text-[11px] text-gray-800 p-5 font-mono leading-relaxed m-0">
                          <code className="block language-html">{slide}</code>
                        </pre>
                      </div>
                    </div>
                  ));
                })()}
              </>
            ) : (
              <div className="flex items-center justify-center h-[60vh]">
                <div className="text-sm text-muted-foreground text-center">
                  <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
                  正在加载代码...
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

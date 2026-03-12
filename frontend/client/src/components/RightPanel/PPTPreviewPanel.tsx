import { useRef, useEffect, useState, RefObject } from "react";
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

const CODE_TOKEN_REGEX =
  /(<!--.*?-->|\/\*.*?\*\/|<!DOCTYPE|<\/?[A-Za-z][\w:-]*|\/?>|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[A-Za-z_:][-A-Za-z0-9_:.]*(?=\s*=)|[A-Za-z-]+(?=\s*:)|\b\d+(?:\.\d+)?\b|[{}[\]();:,=])/g;

type TokenType =
  | "comment"
  | "doctype"
  | "tag"
  | "tagEnd"
  | "string"
  | "attr"
  | "cssProp"
  | "number"
  | "punct"
  | "plain";

const detectTokenType = (token: string): TokenType => {
  if (token.startsWith("<!--") || token.startsWith("/*")) return "comment";
  if (token === "<!DOCTYPE") return "doctype";
  if (token.startsWith("</") || token.startsWith("<")) return "tag";
  if (token === ">" || token === "/>") return "tagEnd";
  if (token.startsWith("\"") || token.startsWith("'")) return "string";
  if (/^[{}[\]();:,=]$/.test(token)) return "punct";
  if (/^\d+(?:\.\d+)?$/.test(token)) return "number";
  if (/^[A-Za-z-]+$/.test(token)) return "cssProp";
  if (/^[A-Za-z_:][-A-Za-z0-9_:.]*$/.test(token)) return "attr";
  return "plain";
};

const escapeHtml = (input: string): string =>
  input
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#39;");

const wrapToken = (token: string, type?: string): string => {
  const escaped = escapeHtml(token);
  if (type === "comment") {
    return `<span style="color:#94a3b8">${escaped}</span>`;
  }
  if (type === "doctype") {
    return `<span style="color:#7c3aed;font-weight:600">${escaped}</span>`;
  }
  if (type === "string") {
    return `<span style="color:#16a34a">${escaped}</span>`;
  }
  if (type === "tag") {
    return `<span style="color:#2563eb">${escaped}</span>`;
  }
  if (type === "tagEnd") {
    return `<span style="color:#64748b">${escaped}</span>`;
  }
  if (type === "attr") {
    return `<span style="color:#c2410c">${escaped}</span>`;
  }
  if (type === "cssProp") {
    return `<span style="color:#0f766e">${escaped}</span>`;
  }
  if (type === "number") {
    return `<span style="color:#e11d48">${escaped}</span>`;
  }
  if (type === "punct") {
    return `<span style="color:#64748b">${escaped}</span>`;
  }
  return `<span style="color:#334155">${escaped}</span>`;
};

const highlightCodeLine = (line: string): string => {
  if (!line) return "&nbsp;";
  let result = "";
  let lastIndex = 0;
  const regex = new RegExp(CODE_TOKEN_REGEX.source, "g");
  let match: RegExpExecArray | null = null;
  while ((match = regex.exec(line)) !== null) {
    const idx = match.index ?? 0;
    const token = match[0] || "";
    const tokenType = detectTokenType(token);
    if (idx > lastIndex) {
      result += escapeHtml(line.slice(lastIndex, idx));
    }
    result += wrapToken(token, tokenType);
    lastIndex = idx + token.length;
  }
  if (lastIndex < line.length) {
    result += escapeHtml(line.slice(lastIndex));
  }
  return result || "&nbsp;";
};

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
  const [renderEpoch, setRenderEpoch] = useState(0);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [editorReady, setEditorReady] = useState(false);

  const FONT_URL_PATTERN = /(https?:\/\/(?:fonts\.googleapis\.com|fonts\.gstatic\.com|cdn\.cn\.font\.mi\.com)[^"'\s)<]+)/gi;
  const toFontCacheUrl = (url: string): string => `/api/font-cache?url=${encodeURIComponent(url)}`;
  const rewriteFontUrlsToCache = (html: string): string =>
    html.replace(FONT_URL_PATTERN, (match) => toFontCacheUrl(match));

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
    const cachedSlide = rewriteFontUrlsToCache(slide);
    const fontLinks = `
      <link href="${toFontCacheUrl("https://fonts.googleapis.com/icon?family=Material+Icons")}" rel="stylesheet">
      <link href="${toFontCacheUrl("https://cdn.cn.font.mi.com/font/css?family=MiSans:300,400,500,600,700:Chinese_Simplify,Latin&display=swap")}" rel="stylesheet">
      <link href="${toFontCacheUrl("https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap")}" rel="stylesheet">
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
        body {
          font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
        }
      </style>
    `;

    let processedSlide = cachedSlide;
    if (cachedSlide.includes("</head>")) {
      processedSlide = cachedSlide.replace("</head>", forceStyles + "</head>");
    } else if (cachedSlide.includes("<body")) {
      processedSlide = cachedSlide.replace("<body", forceStyles + "<body");
    } else {
      processedSlide = forceStyles + cachedSlide;
    }
    return processedSlide;
  };

  // 获取 slides 数据 - 优先从 current_version.slides，否则从 project.slides
  const slides = pptProject?.current_version?.slides || (pptProject as any)?.slides;
  const hasSlides = slides && slides.length > 0;
  const slidesFromProject = hasSlides
    ? [...slides]
        .sort((a: any, b: any) => a.page_number - b.page_number)
        .map((slide: any) => slide.html_content)
    : [];
  const slidesFromHtml = pptHtmlCode
    ? pptHtmlCode
        .split(/(?=<!DOCTYPE html>)/i)
        .filter((html: string) => html.trim())
    : [];
  // 优先使用流式拼接的 HTML，避免完成阶段切换导致空白闪烁
  const slidesHtml = slidesFromHtml.length > 0 ? slidesFromHtml : slidesFromProject;

  // 编辑模式下，若 pptProject 没有 slides 数据，从 pptHtmlCode 构造合成 slides
  // 这样切换编辑模式时不会出现白屏
  const editableSlides = hasSlides
    ? slides
    : slidesFromHtml.length > 0
    ? slidesFromHtml.map((html: string, idx: number) => ({
        id: -(idx + 1), // 负数 id 表示未持久化的合成 slide
        version_id: -1,
        page_number: idx + 1,
        html_content: html,
        created_at: "",
        updated_at: "",
      }))
    : [];
  const isEmptySlides = slidesHtml.length === 0;
  const hasEditableSlides = editableSlides.length > 0;

  const prevSlidesCountRef = useRef(0);

  useEffect(() => {
    const becameEmpty = slidesHtml.length === 0 && prevSlidesCountRef.current > 0;
    if (becameEmpty) {
      setRenderEpoch(prev => prev + 1);
    }
    prevSlidesCountRef.current = slidesHtml.length;
  }, [slidesHtml.length]);

  useEffect(() => {
    if (!isEditMode) {
      setEditorReady(false);
      return;
    }
    setEditorReady(false);
  }, [isEditMode, hasEditableSlides]);

  const copyToClipboard = async (text: string, index: number) => {
    const fallbackCopy = () => {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      textarea.style.pointerEvents = "none";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    };

    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        fallbackCopy();
      }
      setCopiedIndex(index);
      window.setTimeout(() => setCopiedIndex(null), 1200);
    } catch {
      try {
        fallbackCopy();
        setCopiedIndex(index);
        window.setTimeout(() => setCopiedIndex(null), 1200);
      } catch {
        // Ignore copy failures silently
      }
    }
  };

  const renderPreviewSlides = () => (
    <div className="p-8 space-y-8">
      {!isEmptySlides ? (
        <>
          {(() => {
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
                  <div className="flex items-center gap-2 px-1">
                    <span className="text-xs font-medium text-muted-foreground bg-muted px-2 py-0.5 rounded">
                      第 {idx + 1} 页
                    </span>
                    <div className="h-[1px] flex-1 bg-border/50"></div>
                    <span className="text-[10px] text-muted-foreground/50 font-mono">
                      1280 × 720
                    </span>
                  </div>

                  <div
                    className="relative shadow-xl rounded-xl bg-white border border-border/50 overflow-hidden"
                    style={{
                      width: `${containerWidth}px`,
                      height: `${scaledHeight}px`,
                    }}
                  >
                    <iframe
                      key={`preview-${idx}-${pptViewMode}-${renderEpoch}`}
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
      ) : null}
    </div>
  );

  const shouldUseEditable = !!(isEditMode && hasEditableSlides && onSaveSlide);

  return (
    <div
      className="relative bg-gray-50/50 h-full overflow-auto"
      ref={pptViewMode === "preview" ? pptPreviewScrollRef : pptCodeScrollRef}
    >
      {pptViewMode === "preview" ? (
        <>
          {shouldUseEditable ? (
            <>
              {!editorReady && renderPreviewSlides()}
              {!editorReady && (
                <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 px-3 py-1.5 rounded-full bg-background/95 border border-border text-xs text-muted-foreground shadow-sm">
                  正在进入编辑模式...
                </div>
              )}
              <EditablePPTPreview
                ref={editablePPTRef}
                slides={editableSlides}
                isEditMode={isEditMode}
                onSaveSlide={onSaveSlide!}
                onReady={() => setEditorReady(true)}
                className={editorReady ? "" : "fixed left-[-99999px] top-0 w-px h-px overflow-hidden pointer-events-none"}
              />
            </>
          ) : (
            renderPreviewSlides()
          )}
        </>
      ) : (
        <>
          {/* 代码区域 - 分页显示代码块 */}
          <div className="p-6 space-y-6">
            {!isEmptySlides ? (
              <>
                {(() => {
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
                            copyToClipboard(slide, idx);
                          }}
                          className="text-[10px] text-primary hover:underline font-medium"
                        >
                          {copiedIndex === idx ? "已复制" : "复制代码"}
                        </button>
                      </div>

                      {/* 代码块容器 */}
                      <div
                        className="relative bg-[#f8fafc] border border-slate-200 rounded-xl overflow-auto shadow-sm"
                        style={{
                          width: `${containerWidth}px`,
                          height: `${slideHeight}px`,
                        }}
                      >
                        <div className="text-[12px] font-mono leading-6 text-slate-700 px-0 py-2">
                          <div className="min-w-max">
                            {slide.split("\n").map((line, lineIndex) => (
                              <div key={lineIndex} className="grid grid-cols-[52px_1fr] hover:bg-slate-50/80">
                                <span className="select-none pr-3 text-right text-slate-400 border-r border-slate-200 bg-slate-50/70">
                                  {lineIndex + 1}
                                </span>
                                <span
                                  className="pl-4 pr-3 whitespace-pre"
                                  dangerouslySetInnerHTML={{ __html: highlightCodeLine(line) }}
                                />
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  ));
                })()}
              </>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}

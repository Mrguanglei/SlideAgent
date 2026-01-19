/**
 * 可编辑的 PPT 预览组件
 * 
 * 功能：
 * - 点击"编辑"后所有页面文字直接可编辑
 * - 通过父组件调用保存
 */

import { useState, useRef, useEffect, useCallback, forwardRef, useImperativeHandle } from "react";
import { cn } from "@/lib/utils";
import type { PPTSlide } from "@/types";

interface EditablePPTPreviewProps {
  slides: PPTSlide[];
  isEditMode: boolean;
  onSaveSlide: (slideId: number, htmlContent: string) => Promise<void>;
}

export interface EditablePPTPreviewRef {
  saveAllSlides: () => Promise<void>;
}

const EditablePPTPreview = forwardRef<EditablePPTPreviewRef, EditablePPTPreviewProps>(({
  slides,
  isEditMode,
  onSaveSlide
}, ref) => {
  const [localSlides, setLocalSlides] = useState<PPTSlide[]>(slides);
  const iframeRefs = useRef<(HTMLIFrameElement | null)[]>([]);

  // 同步外部 slides 变化
  useEffect(() => {
    setLocalSlides(slides);
  }, [slides]);

  // 注入强制样式的函数
  const processSlideHtml = (slide: string, editable: boolean = false): string => {
    const fontLinks = `
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <link href="https://cdn.cn.font.mi.com/font/css?family=MiSans:300,400,500,600,700:Chinese_Simplify,Latin&display=swap" rel="stylesheet">
      <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    `;

    const editableStyles = editable ? `
      [contenteditable="true"] {
        outline: 2px dashed #3b82f6 !important;
        outline-offset: 2px;
        cursor: text;
        min-height: 20px;
      }
      [contenteditable="true"]:hover {
        outline-color: #2563eb !important;
        background: rgba(59, 130, 246, 0.05) !important;
      }
      [contenteditable="true"]:focus {
        outline: 2px solid #3b82f6 !important;
        background: rgba(59, 130, 246, 0.1) !important;
      }
    ` : '';

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
        ${editableStyles}
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

  // 使文本元素可编辑
  const makeEditable = useCallback((iframe: HTMLIFrameElement) => {
    try {
      const doc = iframe.contentDocument;
      if (!doc) return;

      const textElements = doc.querySelectorAll('h1, h2, h3, h4, h5, h6, p, span, div, li, td, th, a, button, label');

      let madeEditableCount = 0;
      textElements.forEach((el) => {
        const element = el as HTMLElement;
        const hasText = element.textContent && element.textContent.trim().length > 0;

        if (hasText) {
          element.setAttribute('contenteditable', 'true');
          element.style.cursor = 'text';
          madeEditableCount++;
        }
      });

      console.log(`✅ 已设置 ${madeEditableCount} 个元素为可编辑`);
    } catch (e) {
      console.error('❌ makeEditable 失败:', e);
    }
  }, []);

  // 获取编辑后的 HTML
  const getEditedHtml = useCallback((iframe: HTMLIFrameElement): string => {
    try {
      const doc = iframe.contentDocument;
      if (!doc) return '';

      const editableElements = doc.querySelectorAll('[contenteditable]');
      editableElements.forEach(el => {
        el.removeAttribute('contenteditable');
      });

      return '<!DOCTYPE html>\n' + doc.documentElement.outerHTML;
    } catch (e) {
      console.error('Failed to get edited HTML:', e);
      return '';
    }
  }, []);

  // 当进入编辑模式时，自动让所有 iframe 可编辑
  useEffect(() => {
    if (isEditMode) {
      setTimeout(() => {
        iframeRefs.current.forEach((iframe) => {
          if (iframe) {
            makeEditable(iframe);
          }
        });
      }, 500);
    }
  }, [isEditMode, makeEditable]);

  // 保存所有编辑 - 暴露给父组件
  const saveAllSlides = useCallback(async () => {
    console.log('开始保存所有幻灯片...');

    for (let idx = 0; idx < localSlides.length; idx++) {
      const iframe = iframeRefs.current[idx];
      if (!iframe) continue;

      const editedHtml = getEditedHtml(iframe);
      const slide = localSlides[idx];

      await onSaveSlide(slide.id, editedHtml);

      setLocalSlides(prev => {
        const newSlides = [...prev];
        newSlides[idx] = {
          ...newSlides[idx],
          html_content: editedHtml
        };
        return newSlides;
      });
    }

    console.log('✅ 所有幻灯片保存成功');
  }, [localSlides, onSaveSlide, getEditedHtml]);

  // 暴露方法给父组件
  useImperativeHandle(ref, () => ({
    saveAllSlides
  }));

  const containerWidth = 836;
  const slideWidth = 1280;
  const slideHeight = 720;
  const scale = containerWidth / slideWidth;
  const scaledHeight = slideHeight * scale;

  return (
    <div className="p-8 space-y-8">
      {localSlides.map((slide, idx) => {
        const processedSlide = processSlideHtml(slide.html_content, isEditMode);

        return (
          <div key={slide.id} className="flex flex-col gap-3">
            {/* 页码标识 */}
            <div className="flex items-center gap-2 px-1">
              <span className="text-xs font-medium text-muted-foreground bg-muted px-2 py-0.5 rounded">
                第 {idx + 1} 页
              </span>
              <div className="h-[1px] flex-1 bg-border/50"></div>
              <span className="text-[10px] text-muted-foreground/50 font-mono">
                1280 × 720
              </span>
              {isEditMode && (
                <span className="text-xs text-primary font-medium">
                  ✏️ 点击文字即可编辑
                </span>
              )}
            </div>

            {/* PPT 容器 */}
            <div
              className={cn(
                "relative shadow-xl rounded-xl bg-white border overflow-hidden transition-all",
                isEditMode
                  ? "border-primary ring-2 ring-primary/20"
                  : "border-border/50"
              )}
              style={{
                width: `${containerWidth}px`,
                height: `${scaledHeight}px`,
              }}
            >
              <iframe
                ref={el => { iframeRefs.current[idx] = el; }}
                key={`editable-${slide.id}-${isEditMode}`}
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
                onLoad={() => {
                  if (isEditMode) {
                    setTimeout(() => {
                      const iframe = iframeRefs.current[idx];
                      if (iframe) {
                        makeEditable(iframe);
                      }
                    }, 100);
                  }
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
});

EditablePPTPreview.displayName = 'EditablePPTPreview';

export default EditablePPTPreview;

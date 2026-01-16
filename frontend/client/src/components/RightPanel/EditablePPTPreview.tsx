/**
 * 可编辑的 PPT 预览组件
 * 
 * 功能：
 * - 点击文字进入编辑模式
 * - 实时预览编辑效果
 * - 保存编辑内容
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { Loader2, Save, X, Edit3 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PPTSlide } from "@/types";

interface EditablePPTPreviewProps {
  slides: PPTSlide[];
  isEditMode: boolean;
  onSaveSlide: (slideId: number, htmlContent: string) => Promise<void>;
}

interface EditingState {
  slideIndex: number;
  originalHtml: string;
  editedHtml: string;
}

export default function EditablePPTPreview({
  slides,
  isEditMode,
  onSaveSlide
}: EditablePPTPreviewProps) {
  const [editingState, setEditingState] = useState<EditingState | null>(null);
  const [isSaving, setIsSaving] = useState(false);
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
      <link href="https://cdn.bootcdn.net/ajax/libs/material-design-icons/4.0.0/iconfont/material-icons.css" rel="stylesheet">
      <link href="https://cdn.cn.font.mi.com/font/css?family=MiSans:300,400,500,600,700:Chinese_Simplify,Latin&display=swap" rel="stylesheet">
      <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    `;
    
    const editableStyles = editable ? `
      [contenteditable="true"] {
        outline: 2px dashed #3b82f6 !important;
        outline-offset: 2px;
        cursor: text;
      }
      [contenteditable="true"]:hover {
        outline-color: #2563eb !important;
      }
      [contenteditable="true"]:focus {
        outline: 2px solid #3b82f6 !important;
        background: rgba(59, 130, 246, 0.05) !important;
      }
    ` : '';
    
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

      // 查找所有文本元素
      const textElements = doc.querySelectorAll('h1, h2, h3, h4, h5, h6, p, span, div, li, td, th');
      
      textElements.forEach((el) => {
        const element = el as HTMLElement;
        // 只对包含直接文本内容的元素设置可编辑
        const hasDirectText = Array.from(element.childNodes).some(
          node => node.nodeType === Node.TEXT_NODE && node.textContent?.trim()
        );
        
        if (hasDirectText || (element.children.length === 0 && element.textContent?.trim())) {
          element.setAttribute('contenteditable', 'true');
        }
      });
    } catch (e) {
      console.error('Failed to make elements editable:', e);
    }
  }, []);

  // 获取编辑后的 HTML
  const getEditedHtml = useCallback((iframe: HTMLIFrameElement): string => {
    try {
      const doc = iframe.contentDocument;
      if (!doc) return '';

      // 移除 contenteditable 属性
      const editableElements = doc.querySelectorAll('[contenteditable]');
      editableElements.forEach(el => {
        el.removeAttribute('contenteditable');
      });

      // 获取完整 HTML
      return '<!DOCTYPE html>\n' + doc.documentElement.outerHTML;
    } catch (e) {
      console.error('Failed to get edited HTML:', e);
      return '';
    }
  }, []);

  // 进入编辑模式
  const handleStartEdit = (index: number) => {
    const slide = localSlides[index];
    setEditingState({
      slideIndex: index,
      originalHtml: slide.html_content,
      editedHtml: slide.html_content
    });

    // 延迟使元素可编辑
    setTimeout(() => {
      const iframe = iframeRefs.current[index];
      if (iframe) {
        makeEditable(iframe);
      }
    }, 500);
  };

  // 取消编辑
  const handleCancelEdit = () => {
    if (editingState) {
      // 恢复原始内容
      setLocalSlides(prev => {
        const newSlides = [...prev];
        newSlides[editingState.slideIndex] = {
          ...newSlides[editingState.slideIndex],
          html_content: editingState.originalHtml
        };
        return newSlides;
      });
    }
    setEditingState(null);
  };

  // 保存编辑
  const handleSaveEdit = async () => {
    if (!editingState) return;

    const iframe = iframeRefs.current[editingState.slideIndex];
    if (!iframe) return;

    setIsSaving(true);

    try {
      const editedHtml = getEditedHtml(iframe);
      const slide = localSlides[editingState.slideIndex];
      
      await onSaveSlide(slide.id, editedHtml);

      // 更新本地状态
      setLocalSlides(prev => {
        const newSlides = [...prev];
        newSlides[editingState.slideIndex] = {
          ...newSlides[editingState.slideIndex],
          html_content: editedHtml
        };
        return newSlides;
      });

      setEditingState(null);
    } catch (e) {
      console.error('Failed to save slide:', e);
    } finally {
      setIsSaving(false);
    }
  };

  const containerWidth = 836;
  const slideWidth = 1280;
  const slideHeight = 720;
  const scale = containerWidth / slideWidth;
  const scaledHeight = slideHeight * scale;

  return (
    <div className="p-8 space-y-8">
      {localSlides.map((slide, idx) => {
        const isEditing = editingState?.slideIndex === idx;
        const processedSlide = processSlideHtml(slide.html_content, isEditing);

        return (
          <div key={slide.id} className="flex flex-col gap-3">
            {/* 页码标识和操作按钮 */}
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-muted-foreground bg-muted px-2 py-0.5 rounded">
                  第 {idx + 1} 页
                </span>
                <div className="h-[1px] flex-1 bg-border/50"></div>
                <span className="text-[10px] text-muted-foreground/50 font-mono">
                  1280 × 720
                </span>
              </div>
              
              {/* 编辑操作按钮 */}
              {isEditMode && (
                <div className="flex items-center gap-2">
                  {isEditing ? (
                    <>
                      <button
                        onClick={handleCancelEdit}
                        disabled={isSaving}
                        className="px-3 py-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                      >
                        取消
                      </button>
                      <button
                        onClick={handleSaveEdit}
                        disabled={isSaving}
                        className="px-3 py-1 text-xs bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1"
                      >
                        {isSaving ? (
                          <>
                            <Loader2 className="h-3 w-3 animate-spin" />
                            保存中
                          </>
                        ) : (
                          <>
                            <Save className="h-3 w-3" />
                            保存
                          </>
                        )}
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => handleStartEdit(idx)}
                      className="px-3 py-1 text-xs text-primary hover:bg-primary/10 rounded-lg transition-colors flex items-center gap-1"
                    >
                      <Edit3 className="h-3 w-3" />
                      编辑此页
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* PPT 容器 */}
            <div
              className={cn(
                "relative shadow-xl rounded-xl bg-white border overflow-hidden transition-all",
                isEditing 
                  ? "border-primary ring-2 ring-primary/20" 
                  : "border-border/50"
              )}
              style={{
                width: `${containerWidth}px`,
                height: `${scaledHeight}px`,
              }}
            >
              {isEditing && (
                <div className="absolute top-2 left-2 z-10 px-2 py-1 bg-primary text-white text-xs rounded-md">
                  编辑模式 - 点击文字进行编辑
                </div>
              )}
              <iframe
                ref={el => { iframeRefs.current[idx] = el; }}
                key={`preview-${idx}-${isEditing}`}
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
                  if (isEditing) {
                    const iframe = iframeRefs.current[idx];
                    if (iframe) {
                      makeEditable(iframe);
                    }
                  }
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

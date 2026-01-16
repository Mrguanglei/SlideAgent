import { usePPTAgent } from "@/contexts/PPTAgentContext";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import {
  Presentation,
  Download,
  ExternalLink,
  Loader2,
  CheckCircle2,
  XCircle,
  FileSliders,
  Eye,
  ChevronLeft,
  ChevronRight,
  Maximize2,
} from "lucide-react";
import { useState } from "react";

interface PPTPreviewProps {
  className?: string;
}

export function PPTPreview({ className }: PPTPreviewProps) {
  const { state } = usePPTAgent();
  const { pptState } = state;
  const [currentSlide, setCurrentSlide] = useState(0);

  // Mock slides for demo
  const mockSlides = [
    { id: 1, title: "封面", thumbnail: null },
    { id: 2, title: "目录", thumbnail: null },
    { id: 3, title: "第一章", thumbnail: null },
    { id: 4, title: "第二章", thumbnail: null },
    { id: 5, title: "总结", thumbnail: null },
  ];

  const slides = pptState.status === "completed" ? mockSlides : [];

  return (
    <div className={cn("flex flex-col h-full", className)}>
      {/* Header */}
      <div className="px-4 pt-4 pb-3 border-b border-border/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Presentation className="h-5 w-5 text-primary" />
            <h2 className="font-semibold">PPT 预览</h2>
          </div>
          <StatusBadge status={pptState.status} />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {pptState.status === "idle" && <IdleState />}
        {pptState.status === "generating" && <GeneratingState />}
        {pptState.status === "completed" && (
          <CompletedState
            slides={slides}
            currentSlide={currentSlide}
            onSlideChange={setCurrentSlide}
            downloadUrl={pptState.outputPath}
          />
        )}
        {pptState.status === "error" && (
          <ErrorState error={pptState.error} />
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline"; icon: typeof Loader2 }> = {
    idle: { label: "等待生成", variant: "secondary", icon: FileSliders },
    generating: { label: "生成中", variant: "default", icon: Loader2 },
    completed: { label: "已完成", variant: "outline", icon: CheckCircle2 },
    error: { label: "生成失败", variant: "destructive", icon: XCircle },
  };

  const { label, variant, icon: Icon } = config[status] || config.idle;

  return (
    <Badge variant={variant} className="gap-1">
      <Icon className={cn("h-3 w-3", status === "generating" && "animate-spin")} />
      {label}
    </Badge>
  );
}

function IdleState() {
  return (
    <div className="flex flex-col items-center justify-center h-full p-8 text-center">
      <div className="w-20 h-20 rounded-2xl bg-accent flex items-center justify-center mb-4">
        <Presentation className="h-10 w-10 text-muted-foreground" />
      </div>
      <h3 className="font-medium text-lg mb-2">准备生成 PPT</h3>
      <p className="text-sm text-muted-foreground max-w-[280px]">
        在左侧输入您的需求或上传参考文档，开始生成专业的演示文稿
      </p>
    </div>
  );
}

function GeneratingState() {
  const steps = [
    { label: "分析需求", progress: 100, completed: true },
    { label: "研究内容", progress: 100, completed: true },
    { label: "设计布局", progress: 60, completed: false },
    { label: "生成幻灯片", progress: 0, completed: false },
  ];

  const currentStep = steps.findIndex((s) => !s.completed);
  const overallProgress = steps.reduce((acc, s) => acc + s.progress, 0) / steps.length;

  return (
    <div className="flex flex-col items-center justify-center h-full p-8">
      <div className="w-full max-w-[320px] space-y-6">
        {/* Main Progress */}
        <div className="text-center">
          <div className="relative w-24 h-24 mx-auto mb-4">
            <svg className="w-full h-full transform -rotate-90">
              <circle
                cx="48"
                cy="48"
                r="44"
                stroke="currentColor"
                strokeWidth="8"
                fill="none"
                className="text-accent"
              />
              <circle
                cx="48"
                cy="48"
                r="44"
                stroke="currentColor"
                strokeWidth="8"
                fill="none"
                strokeDasharray={`${overallProgress * 2.76} 276`}
                strokeLinecap="round"
                className="text-primary transition-all duration-500"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-2xl font-semibold">{Math.round(overallProgress)}%</span>
            </div>
          </div>
          <h3 className="font-medium">正在生成 PPT</h3>
          <p className="text-sm text-muted-foreground mt-1">
            {steps[currentStep]?.label || "处理中..."}
          </p>
        </div>

        {/* Steps */}
        <div className="space-y-3">
          {steps.map((step, index) => (
            <div key={step.label} className="flex items-center gap-3">
              <div
                className={cn(
                  "w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium shrink-0",
                  step.completed
                    ? "bg-primary text-primary-foreground"
                    : index === currentStep
                    ? "bg-primary/20 text-primary"
                    : "bg-accent text-muted-foreground"
                )}
              >
                {step.completed ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : index === currentStep ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  index + 1
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span
                    className={cn(
                      "text-sm",
                      step.completed || index === currentStep
                        ? "text-foreground"
                        : "text-muted-foreground"
                    )}
                  >
                    {step.label}
                  </span>
                  {index === currentStep && (
                    <span className="text-xs text-primary">{step.progress}%</span>
                  )}
                </div>
                {index === currentStep && (
                  <Progress value={step.progress} className="h-1 mt-1.5" />
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

interface CompletedStateProps {
  slides: Array<{ id: number; title: string; thumbnail: string | null }>;
  currentSlide: number;
  onSlideChange: (index: number) => void;
  downloadUrl?: string;
}

function CompletedState({
  slides,
  currentSlide,
  onSlideChange,
  downloadUrl,
}: CompletedStateProps) {
  return (
    <div className="flex flex-col h-full">
      {/* Main Preview */}
      <div className="flex-1 p-4 flex flex-col">
        <div className="flex-1 bg-accent rounded-xl overflow-hidden relative group">
          {/* Slide Preview */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-full max-w-[480px] aspect-[16/9] bg-white rounded-lg shadow-lg flex items-center justify-center">
              <div className="text-center p-8">
                <Presentation className="h-12 w-12 text-muted-foreground/50 mx-auto mb-3" />
                <p className="text-lg font-medium text-muted-foreground">
                  {slides[currentSlide]?.title || `幻灯片 ${currentSlide + 1}`}
                </p>
              </div>
            </div>
          </div>

          {/* Navigation Overlay */}
          <div className="absolute inset-0 flex items-center justify-between px-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button
              variant="secondary"
              size="icon"
              className="h-10 w-10 rounded-full shadow-lg"
              onClick={() => onSlideChange(Math.max(0, currentSlide - 1))}
              disabled={currentSlide === 0}
            >
              <ChevronLeft className="h-5 w-5" />
            </Button>
            <Button
              variant="secondary"
              size="icon"
              className="h-10 w-10 rounded-full shadow-lg"
              onClick={() => onSlideChange(Math.min(slides.length - 1, currentSlide + 1))}
              disabled={currentSlide === slides.length - 1}
            >
              <ChevronRight className="h-5 w-5" />
            </Button>
          </div>

          {/* Fullscreen Button */}
          <Button
            variant="secondary"
            size="icon"
            className="absolute top-2 right-2 h-8 w-8 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <Maximize2 className="h-4 w-4" />
          </Button>
        </div>

        {/* Slide Counter */}
        <div className="flex items-center justify-center gap-2 mt-3">
          <span className="text-sm text-muted-foreground">
            {currentSlide + 1} / {slides.length}
          </span>
        </div>
      </div>

      {/* Thumbnail Strip */}
      <div className="border-t border-border/50 p-3">
        <ScrollArea className="w-full">
          <div className="flex gap-2">
            {slides.map((slide, index) => (
              <button
                key={slide.id}
                onClick={() => onSlideChange(index)}
                className={cn(
                  "w-20 h-12 rounded-lg bg-accent shrink-0 flex items-center justify-center text-xs transition-all",
                  index === currentSlide
                    ? "ring-2 ring-primary ring-offset-2"
                    : "hover:ring-2 hover:ring-border"
                )}
              >
                {slide.title}
              </button>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* Actions */}
      <div className="border-t border-border/50 p-4 flex gap-2">
        <Button className="flex-1" disabled={!downloadUrl}>
          <Download className="h-4 w-4 mr-2" />
          下载 PPTX
        </Button>
        <Button variant="outline" className="flex-1">
          <ExternalLink className="h-4 w-4 mr-2" />
          在线预览
        </Button>
      </div>
    </div>
  );
}

function ErrorState({ error }: { error?: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full p-8 text-center">
      <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mb-4">
        <XCircle className="h-8 w-8 text-destructive" />
      </div>
      <h3 className="font-medium text-lg mb-2">生成失败</h3>
      <p className="text-sm text-muted-foreground max-w-[280px]">
        {error || "生成过程中遇到错误，请重试"}
      </p>
      <Button variant="outline" className="mt-4">
        重新生成
      </Button>
    </div>
  );
}

export default PPTPreview;

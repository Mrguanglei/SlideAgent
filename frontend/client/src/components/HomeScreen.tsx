/**
 * HomeScreen - 首页欢迎界面（输入框 + 模板网格）
 */
import { RefObject } from "react";
import { Send, Paperclip, Database, Globe, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Popover, PopoverContent, PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select, SelectContent, SelectItem, SelectTrigger,
} from "@/components/ui/select";
import type { Template, TemplateCategory } from "@/types";
import type { UploadResponse } from "@/lib/api";

const TEMPLATES: Template[] = [
  { id: 1, title: "AI医疗创新", category: "科技", color: "from-white to-gray-50", subtitle: "AI-DRIVEN HEALTHCARE INNOVATION", preview: "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=400&h=225&fit=crop" },
  { id: 2, title: "中国医疗创新", category: "商务", color: "from-blue-50 to-blue-100", subtitle: "中国医疗创新：未来的挑战", preview: "https://images.unsplash.com/photo-1551076805-e1869033e561?w=400&h=225&fit=crop" },
  { id: 3, title: "战略规划", category: "商务", color: "from-purple-600 to-purple-700", subtitle: "STRATEGIC EXCELLENCE", preview: "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=400&h=225&fit=crop" },
  { id: 4, title: "商业转型", category: "商务", color: "from-slate-700 to-slate-800", subtitle: "Business Transformation Strategy", preview: "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=400&h=225&fit=crop" },
  { id: 5, title: "律师事务所", category: "商务", color: "from-amber-700 to-amber-800", subtitle: "LAWYER", preview: "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=400&h=225&fit=crop" },
  { id: 6, title: "企业卓越", category: "商务", color: "from-orange-500 to-orange-600", subtitle: "CORPORATE EXCELLENCE", preview: "https://images.unsplash.com/photo-1497366216548-37526070297c?w=400&h=225&fit=crop" },
  { id: 7, title: "研究报告", category: "科技", color: "from-gray-100 to-gray-200", subtitle: "ADVANCED RESEARCH SYMPOSIUM", preview: "https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=400&h=225&fit=crop" },
  { id: 8, title: "酒店介绍", category: "创意", color: "from-stone-600 to-stone-700", subtitle: "The Grand Meridian", preview: "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=400&h=225&fit=crop" },
];

const TEMPLATE_CATEGORIES: TemplateCategory[] = ["全部", "科技", "商务", "创意"];

const SEARCH_MODE_OPTIONS = [
  { value: "auto", label: "自动", description: "自动判断联网获取信息" },
  { value: "on", label: "开启联网", description: "始终联网获取信息" },
  { value: "off", label: "关闭", description: "不再联网获取信息" },
] as const;

interface HomeScreenProps {
  greeting: string;
  inputValue: string;
  setInputValue: (v: string) => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  activeAttachments: UploadResponse[];
  setActiveAttachments: React.Dispatch<React.SetStateAction<UploadResponse[]>>;
  isLoading: boolean;
  searchMode: "auto" | "on" | "off";
  setSearchMode: (v: "auto" | "on" | "off") => void;
  isSearchDisabled: boolean;
  homePopoverOpen: boolean;
  setHomePopoverOpen: (v: boolean) => void;
  selectedCategory: TemplateCategory;
  setSelectedCategory: (v: TemplateCategory) => void;
  onSend: () => void;
  onOpenKbSelector: () => void;
  onOpenFileInput: () => void;
  onCompositionStart: React.CompositionEventHandler<HTMLTextAreaElement>;
  onCompositionEnd: React.CompositionEventHandler<HTMLTextAreaElement>;
  onKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement>;
}

const getSearchModeLabel = (value: "auto" | "on" | "off") =>
  SEARCH_MODE_OPTIONS.find(item => item.value === value)?.label || "自动";

export default function HomeScreen({
  greeting,
  inputValue,
  setInputValue,
  inputRef,
  activeAttachments,
  setActiveAttachments,
  isLoading,
  searchMode,
  setSearchMode,
  isSearchDisabled,
  homePopoverOpen,
  setHomePopoverOpen,
  selectedCategory,
  setSelectedCategory,
  onSend,
  onOpenKbSelector,
  onOpenFileInput,
  onCompositionStart,
  onCompositionEnd,
  onKeyDown,
}: HomeScreenProps) {
  const filteredTemplates = TEMPLATES.filter(
    t => selectedCategory === "全部" || t.category === selectedCategory
  );

  return (
    <ScrollArea className="h-full">
      <div className="min-h-full flex flex-col">
        {/* 上半部分：欢迎语 + 输入框 */}
        <div className="flex-shrink-0 pt-16 pb-12 px-4">
          <div className="max-w-3xl mx-auto mt-26">
            <h1 className="text-3xl font-bold mb-8 text-center flex items-center justify-center gap-2">
              <span className="greeting-emoji">👋</span>
              <span className="greeting-title">{greeting}</span>
            </h1>

            <div className="border border-border rounded-2xl bg-background shadow-sm overflow-hidden">
              {activeAttachments.length > 0 && (
                <div className="flex flex-wrap gap-2 px-5 pt-3">
                  {activeAttachments.map(file => (
                    <div key={file.id} className="flex items-center gap-1 bg-muted px-2 py-1 rounded-md text-sm border border-border">
                      <span className="truncate max-w-[150px]">{file.filename}</span>
                      <button
                        onClick={() => setActiveAttachments(prev => prev.filter(f => f.id !== file.id))}
                        className="hover:text-destructive transition-colors"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                onCompositionStart={onCompositionStart}
                onCompositionEnd={onCompositionEnd}
                onKeyDown={onKeyDown}
                placeholder="告诉我PPT的主题或内容"
                className="w-full px-5 pt-5 pb-3 bg-transparent resize-none focus:outline-none min-h-[80px] max-h-[200px] text-base"
                rows={2}
              />

              <div className="flex items-center justify-between px-4 py-3 border-t border-border/50">
                <div className="flex items-center gap-3">
                  <Popover open={homePopoverOpen} onOpenChange={setHomePopoverOpen}>
                    <PopoverTrigger asChild>
                      <button className="p-2 hover:bg-muted rounded-lg transition-colors">
                        <Paperclip className="h-5 w-5 text-muted-foreground" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-48 p-0" align="start">
                      <div className="flex flex-col">
                        <button onClick={onOpenKbSelector} className="flex items-center gap-2 px-4 py-2 hover:bg-muted text-sm text-left transition-colors">
                          <Database className="h-4 w-4" /><span>云知识库选择</span>
                        </button>
                        <button onClick={onOpenFileInput} className="flex items-center gap-2 px-4 py-2 hover:bg-muted text-sm text-left transition-colors">
                          <Paperclip className="h-4 w-4" /><span>本地文件选择</span>
                        </button>
                      </div>
                    </PopoverContent>
                  </Popover>

                  <Select value={searchMode} disabled={isSearchDisabled} onValueChange={(v) => { if (v === "auto" || v === "on" || v === "off") setSearchMode(v); }}>
                    <SelectTrigger size="sm" className={cn("h-8 rounded-full px-3", isSearchDisabled && "opacity-50 cursor-not-allowed")}>
                      <div className="flex items-center gap-2 text-sm">
                        <Globe className="h-3.5 w-3.5 text-muted-foreground" />
                        <span>联网搜索</span>
                        <span className="text-muted-foreground">· {getSearchModeLabel(searchMode)}</span>
                      </div>
                    </SelectTrigger>
                    <SelectContent align="start" className="min-w-[240px]">
                      {SEARCH_MODE_OPTIONS.map(option => (
                        <SelectItem key={option.value} value={option.value}>
                          <div className="flex flex-col gap-0.5 text-left">
                            <span className="text-sm">{option.label}</span>
                            <span className="text-xs text-muted-foreground">{option.description}</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <button
                  onClick={onSend}
                  disabled={!inputValue.trim() || isLoading}
                  className="p-2.5 bg-primary text-white rounded-full hover:bg-primary/90 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <Send className="h-5 w-5" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* 下半部分：分类标签 + 模板网格 */}
        <div className="flex-1 px-4 pb-8">
          <div className="flex justify-center gap-6 mb-8">
            {TEMPLATE_CATEGORIES.map(cat => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={cn(
                  "px-2 py-1 text-base transition-colors border-b-2",
                  selectedCategory === cat
                    ? "text-foreground border-foreground font-medium"
                    : "text-muted-foreground border-transparent hover:text-foreground"
                )}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="max-w-6xl mx-auto">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
              {filteredTemplates.map(template => (
                <button
                  key={template.id}
                  onClick={() => { setInputValue(`帮我制作一个${template.title}的PPT`); inputRef.current?.focus(); }}
                  className="group relative aspect-[16/9] rounded-xl overflow-hidden shadow-lg hover:shadow-2xl transition-all hover:scale-[1.02] bg-white"
                >
                  {template.preview ? (
                    <img src={template.preview} alt={template.title} className="absolute inset-0 w-full h-full object-cover" />
                  ) : (
                    <div className={cn("absolute inset-0 bg-gradient-to-br", template.color)} />
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent" />
                  <div className="absolute inset-0 p-4 flex flex-col justify-end text-white">
                    <div className="text-xs opacity-90 mb-1 uppercase tracking-wide">{template.subtitle}</div>
                    <h3 className="font-bold text-lg leading-tight">{template.title}</h3>
                  </div>
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors" />
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </ScrollArea>
  );
}

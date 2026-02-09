import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Streamdown } from "streamdown";

interface ThinkingBlockProps {
    content: string;
    status?: 'thinking' | 'completed';
    defaultExpanded?: boolean;
}

/**
 * 可折叠的思维链组件 - 胶囊样式
 * 用于显示 AI 的深度思考内容
 */
export default function ThinkingBlock({ content, status = 'completed', defaultExpanded = false }: ThinkingBlockProps) {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);

    // 根据状态自动控制展开/折叠
    // 当状态变为 thinking 时自动展开，变为 completed 时自动折叠
    useEffect(() => {
        if (status === 'thinking') {
            setIsExpanded(true);
        } else if (status === 'completed') {
            setIsExpanded(defaultExpanded);
        }
    }, [status, defaultExpanded]);

    if (!content || content.trim().length === 0) {
        return null;
    }

    return (
        <div>
            {/* 胶囊按钮 */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="tool-button"
            >
                <svg
                    className="tool-button-icon h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                    />
                </svg>
                <span className="tool-button-text">
                    {status === 'thinking' ? '思考中...' : '思考完毕'}
                </span>
                {isExpanded ? (
                    <ChevronDown className="tool-button-arrow h-4 w-4" />
                ) : (
                    <ChevronRight className="tool-button-arrow h-4 w-4" />
                )}
            </button>

            {/* 展开的内容 */}
            {isExpanded && (
                <div className="mt-2 px-4 py-3 rounded-lg bg-muted/30 border border-border/40">
                    <div className="prose prose-sm max-w-none dark:prose-invert prose-headings:text-foreground prose-strong:text-foreground">
                        <Streamdown>{content}</Streamdown>
                    </div>
                </div>
            )}
        </div>
    );
}

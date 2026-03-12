/**
 * useStreamHandler
 * 处理 SSE 流式事件，更新消息、PPT、搜索、任务规划等状态
 */
import { useRef, useCallback } from "react";
import { useLocation } from "wouter";
import type { Message, ToolCall, TaskPlan, SearchRound, ImageSearchRound, RightPanelType, PPTProject } from "@/types";

export interface StreamHandlerDeps {
  // refs
  isStreamingRef: React.MutableRefObject<boolean>;
  currentConversationUuidRef: React.MutableRefObject<string | null>;
  lastCompletedSearchRoundRef: React.MutableRefObject<number>;
  pendingImagePanelRoundRef: React.MutableRefObject<number | null>;
  // state setters
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setIsLoading: React.Dispatch<React.SetStateAction<boolean>>;
  setIsConfirming: React.Dispatch<React.SetStateAction<boolean>>;
  setCurrentConversationId: React.Dispatch<React.SetStateAction<number | null>>;
  setCurrentConversationUuid: React.Dispatch<React.SetStateAction<string | null>>;
  setTaskPlan: React.Dispatch<React.SetStateAction<TaskPlan | null>>;
  setTaskPlanStreaming: React.Dispatch<React.SetStateAction<boolean>>;
  setSearchRounds: React.Dispatch<React.SetStateAction<SearchRound[]>>;
  setCurrentSearchRound: React.Dispatch<React.SetStateAction<number>>;
  setDeepThinking: React.Dispatch<React.SetStateAction<string>>;
  setDeepThinkingStreaming: React.Dispatch<React.SetStateAction<boolean>>;
  setImageSearchRounds: React.Dispatch<React.SetStateAction<ImageSearchRound[]>>;
  setCurrentImageSearchRound: React.Dispatch<React.SetStateAction<number>>;
  setPptOutline: React.Dispatch<React.SetStateAction<string>>;
  setPptOutlineStreaming: React.Dispatch<React.SetStateAction<boolean>>;
  setPptHtmlCode: React.Dispatch<React.SetStateAction<string>>;
  setPptProject: React.Dispatch<React.SetStateAction<PPTProject | null>>;
  setPptProjects: React.Dispatch<React.SetStateAction<PPTProject[]>>;
  setCurrentTopic: React.Dispatch<React.SetStateAction<string>>;
  setPendingToolCallId: React.Dispatch<React.SetStateAction<string>>;
  // callbacks
  openRightPanelDeferred: (type: RightPanelType, delay?: number) => void;
  loadConversations: () => Promise<void>;
  loadPPTProjects: () => Promise<void>;
  refreshPPTProject: (id: number, opts?: { preserveHtml?: boolean }) => Promise<void>;
  startAutoConfirmCountdown: (toolCallId: string) => void;
  // state values (read-only)
  isConfirming: boolean;
  deepThinking: string;
  currentSearchRound: number;
  pptProjectRef: React.MutableRefObject<PPTProject | null>;
}

export function useStreamHandler(deps: StreamHandlerDeps) {
  const [, setLocation] = useLocation();

  const shouldRenderStreamForCurrentConversation = useCallback(
    (streamConversationUuid: string | null) => {
      const currentUuid = deps.currentConversationUuidRef.current;
      if (!streamConversationUuid) return currentUuid === null;
      return currentUuid === streamConversationUuid;
    },
    [deps.currentConversationUuidRef]
  );

  const handleToolCall = useCallback((data: any) => {
    const toolCall: ToolCall = {
      id: String(data.id || `tool-${Date.now()}`),
      type: data.tool_type,
      name: data.tool_name,
      status: data.status || "running",
      data: data.data || {},
    };

    deps.setMessages(prev => {
      const shouldIsolate = toolCall.type === "ppt_generate" || toolCall.type === "ppt_edit" || toolCall.type === "ppt_remove";
      if (shouldIsolate) {
        return [...prev, { id: `assistant-${Date.now()}`, role: "assistant", content: "", timestamp: Date.now(), toolCalls: [toolCall] }];
      }
      const lastMsg = prev[prev.length - 1];
      if (lastMsg?.role === "assistant") {
        return [...prev.slice(0, -1), { ...lastMsg, toolCalls: [...(lastMsg.toolCalls || []), toolCall] }];
      }
      return [...prev, { id: `assistant-${Date.now()}`, role: "assistant", content: "", timestamp: Date.now(), toolCalls: [toolCall] }];
    });

    if (data.tool_type === "supplement_info" && data.status === "pending") {
      deps.setPendingToolCallId(toolCall.id);
      deps.startAutoConfirmCountdown(toolCall.id);
      const generatedTopic = data.data?.topic;
      if (generatedTopic && typeof generatedTopic === "string") {
        deps.setCurrentTopic(generatedTopic);
      }
    }

    if (data.tool_type === "task_plan" || data.tool_type === "plan_task") {
      const planData = data.data as any;
      deps.setTaskPlan({
        thinkingNarrative: planData.thinkingNarrative || planData.thinking_narrative || "",
        coreRequirement: planData.coreRequirement || planData.core_requirement || planData.goal || "",
        problemAnalysis: planData.problemAnalysis || planData.problem_analysis,
        informationDimensions: planData.informationDimensions || planData.information_dimensions,
        searchStrategy: planData.searchStrategy || planData.search_strategy,
        timeScope: planData.timeScope || planData.time_scope,
        details: planData.details || planData.requirements || [],
        steps: planData.steps || planData.tasks || [],
        streamContent: planData.streamContent || planData.content || "",
        streaming: planData.streaming || false,
      } as any);
      deps.openRightPanelDeferred("task_plan");
    }

    if (data.tool_type === "web_search" || data.tool_type === "search") {
      const searchData = data.data as any;
      const round = searchData.round || 1;
      const results = searchData.results || [];
      deps.setSearchRounds(prev => {
        const existingRound = prev.find(r => r.round === round);
        if (existingRound) {
          return prev.map(r => r.round === round ? { ...r, results: [...r.results, ...results], isCompleted: true } : r);
        }
        return [...prev, { round, query: searchData.query || "", results, isCompleted: true }];
      });
      deps.setCurrentSearchRound(round);
      deps.openRightPanelDeferred("web_search");
    }

    if (data.tool_type === "image_search") {
      const imageData = data.data as any;
      const round = typeof imageData.round === "number" ? imageData.round : Number(imageData.round) || 1;
      const images = imageData.images || [];
      deps.setImageSearchRounds(prev => {
        const existingRound = prev.find(r => r.round === round);
        if (existingRound) {
          return prev.map(r => r.round === round ? { ...r, images: [...r.images, ...images], isCompleted: true } : r);
        }
        return [...prev, { round, query: imageData.query || "", images, isCompleted: true }];
      });
      deps.setCurrentImageSearchRound(round);
      if (deps.lastCompletedSearchRoundRef.current >= round) {
        deps.openRightPanelDeferred("image_search", 300);
      } else {
        deps.pendingImagePanelRoundRef.current = round;
      }
    }

    if (data.tool_type === "ppt_outline") {
      deps.setPptOutline((data.data as any)?.content || "");
      deps.openRightPanelDeferred("ppt_outline");
    }

    if (data.tool_type === "create_slide" || data.tool_type === "ppt_generate") {
      deps.openRightPanelDeferred("ppt_preview");
    }

    if (data.tool_type === "ppt_edit") {
      deps.openRightPanelDeferred("ppt_preview");
    }
  }, [deps]);

  const handleStreamEvent = useCallback((data: any, streamConversationUuid: string | null) => {
    if (!shouldRenderStreamForCurrentConversation(streamConversationUuid)) {
      if (data.type === "conversation_created" || data.type === "done") {
        deps.loadConversations();
      }
      return;
    }

    if (data.type !== "done") {
      deps.isStreamingRef.current = true;
    }
    if (deps.isConfirming) {
      deps.setIsConfirming(false);
    }

    console.log("[Frontend] SSE Event:", data.type, data);

    switch (data.type) {
      case "conversation_created":
        deps.setCurrentConversationId(data.conversation_id);
        deps.setCurrentConversationUuid(data.conversation_uuid);
        deps.currentConversationUuidRef.current = data.conversation_uuid;
        if (data.conversation_uuid) {
          setLocation(`/chat/${data.conversation_uuid}`);
        }
        deps.loadConversations();
        break;

      case "message":
        deps.setMessages(prev => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.role === "assistant" && !lastMsg.toolCalls?.length) {
            return [...prev.slice(0, -1), { ...lastMsg, content: lastMsg.content + data.content, streaming: data.streaming !== false }];
          }
          return [...prev, { id: `assistant-${Date.now()}`, role: "assistant", content: data.content, timestamp: Date.now(), streaming: data.streaming === true }];
        });
        break;

      case "tool_call":
        handleToolCall(data);
        break;

      case "task_plan_stream":
        deps.setTaskPlanStreaming(true);
        deps.openRightPanelDeferred("task_plan");
        deps.setTaskPlan(prev => ({ ...(prev || {}), streamContent: (prev?.streamContent || "") + data.content } as any));
        break;

      case "task_plan_complete":
        deps.setTaskPlanStreaming(false);
        if (data.data) {
          deps.setTaskPlan(data.data);
          deps.openRightPanelDeferred("task_plan");
        }
        break;

      case "search_start": {
        const roundNumber = typeof data.round === "number" ? data.round : Number(data.round) || 1;
        deps.setSearchRounds(prev => [...prev, { round: roundNumber, query: data.query, results: [], isCompleted: false }]);
        deps.setImageSearchRounds(prev => [...prev, { round: roundNumber, query: data.query, images: [], isCompleted: false }]);
        deps.setCurrentSearchRound(roundNumber);
        deps.setCurrentImageSearchRound(roundNumber);
        deps.openRightPanelDeferred("web_search");
        break;
      }

      case "search_result":
        deps.setSearchRounds(prev => prev.map(r => r.round === data.round ? { ...r, results: [...r.results, data.result] } : r));
        break;

      case "search_complete":
        deps.setSearchRounds(prev => prev.map(r => r.round === data.round ? { ...r, isCompleted: true } : r));
        if (typeof data.round === "number") {
          deps.lastCompletedSearchRoundRef.current = Math.max(deps.lastCompletedSearchRoundRef.current, data.round);
        }
        if (deps.pendingImagePanelRoundRef.current === data.round) {
          deps.pendingImagePanelRoundRef.current = null;
          deps.openRightPanelDeferred("image_search", 300);
        }
        break;

      case "deep_thinking_start":
        deps.setDeepThinking("");
        deps.setDeepThinkingStreaming(true);
        deps.openRightPanelDeferred("web_search");
        break;

      case "deep_thinking_stream":
        deps.setDeepThinkingStreaming(true);
        deps.setDeepThinking(prev => prev + (data.content || ""));
        deps.setSearchRounds(prev => {
          if (prev.length === 0) return prev;
          const lastRound = prev.reduce((max, item) => (item.round > max ? item.round : max), prev[0].round);
          return prev.map(item =>
            item.round === lastRound
              ? { ...item, thinking: (item.thinking || "") + (data.content || "") }
              : item
          );
        });
        break;

      case "deep_thinking_complete":
        deps.setDeepThinkingStreaming(false);
        {
          const completeThinking = data.content || deps.deepThinking;
          deps.setSearchRounds(prev => {
            if (prev.length === 0) return prev;
            const lastRound = prev.reduce((max, item) => (item.round > max ? item.round : max), prev[0].round);
            return prev.map(item => item.round === lastRound ? { ...item, thinking: completeThinking } : item);
          });
        }
        break;

      case "ppt_outline_stream":
        deps.setPptOutlineStreaming(true);
        deps.openRightPanelDeferred("ppt_outline");
        deps.setPptOutline(prev => prev + data.content);
        break;

      case "ppt_outline_complete":
        deps.setPptOutlineStreaming(false);
        break;

      case "ppt_slide":
        deps.setPptHtmlCode(prev => prev + data.html);
        deps.openRightPanelDeferred("ppt_preview");
        break;

      case "ppt_slide_update":
        deps.setPptProject(prev => {
          if (!prev) return prev;
          const slides = (prev as any).slides;
          if (!slides) return prev;
          const updatedSlides = slides.map((slide: any) =>
            slide.page_number === data.page_number
              ? { ...slide, html_content: data.html, page_title: data.page_title || slide.page_title, updated_at: new Date().toISOString() }
              : slide
          );
          const htmlCode = updatedSlides.sort((a: any, b: any) => a.page_number - b.page_number).map((s: any) => s.html_content).join("\n");
          deps.setPptHtmlCode(htmlCode);
          return { ...prev, slides: updatedSlides } as any;
        });
        deps.openRightPanelDeferred("ppt_preview");
        break;

      case "ppt_slide_remove":
        deps.setPptProject(prev => {
          if (!prev) return prev;
          const slides = (prev as any).slides;
          if (!slides) return prev;
          const remainingSlides = slides.filter((slide: any) => !(data.page_numbers || []).includes(slide.page_number));
          const htmlCode = remainingSlides.sort((a: any, b: any) => a.page_number - b.page_number).map((s: any) => s.html_content).join("\n");
          deps.setPptHtmlCode(htmlCode);
          return { ...prev, slides: remainingSlides } as any;
        });
        break;

      case "ppt_edit_complete":
        deps.setIsLoading(false);
        deps.isStreamingRef.current = false;
        {
          const projectId = deps.pptProjectRef.current?.id;
          if (projectId) {
            deps.refreshPPTProject(projectId);
          }
        }
        break;

      case "ppt_complete":
        if (data.project) {
          deps.setPptProject(data.project);
          if (data.project.title) deps.setCurrentTopic(data.project.title);
          deps.setPptProjects(prev => {
            const exists = prev.some(p => p.id === data.project.id);
            if (exists) return prev.map(p => p.id === data.project.id ? data.project : p);
            return [...prev, data.project];
          });
          deps.loadPPTProjects();
        }
        break;

      case "done":
        deps.setIsLoading(false);
        deps.isStreamingRef.current = false;
        deps.loadConversations();
        {
          const projectId = deps.pptProjectRef.current?.id;
          if (projectId) {
            deps.refreshPPTProject(projectId, { preserveHtml: true });
          }
        }
        deps.setMessages(prev => {
          if (prev.length === 0) return prev;
          const lastMsg = prev[prev.length - 1];
          if (lastMsg.role === "assistant" && lastMsg.streaming) {
            return [...prev.slice(0, -1), { ...lastMsg, streaming: false }];
          }
          return prev;
        });
        break;
    }
  }, [shouldRenderStreamForCurrentConversation, handleToolCall, deps, setLocation]);

  return { handleStreamEvent, shouldRenderStreamForCurrentConversation };
}

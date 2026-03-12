/**
 * useConversationManager
 * 管理对话列表、当前对话、加载/切换/删除/重命名/置顶
 */
import { useState, useRef, useCallback } from "react";
import { toast } from "sonner";
import {
  getConversations,
  getConversationDetail,
  updateConversation,
  deleteConversation,
  getPPTProjects,
  getPPTProject,
} from "@/lib/api";
import type { Conversation, PPTProject, PPTVersion, RightPanelType, Message, TaskPlan, SearchRound, ImageSearchRound } from "@/types";

export interface LoadConversationResult {
  conversationId: number | null;
  hasPptSlides: boolean;
  nextPanelType: RightPanelType;
  restoredMessages: Message[];
  taskPlan: TaskPlan | null;
  searchRounds: SearchRound[];
  imageSearchRounds: ImageSearchRound[];
  pptOutline: string;
  pptProject: PPTProject | null;
  pptHtmlCode: string;
  pptProjects: PPTProject[];
  sessionId: string | null;
  searchMode: "auto" | "on" | "off" | null;
  taskStatus: string;
  topic: string;
}

function resolvePanelTypeFromConversation(
  messages: any[] | undefined,
  hasPptSlides: boolean
): RightPanelType {
  if (hasPptSlides) return "ppt_preview";
  if (!messages || messages.length === 0) return null;

  let hasTaskPlan = false;
  let hasWebSearch = false;
  let hasImageSearch = false;
  let hasPptOutline = false;

  for (const msg of messages) {
    if (!msg?.tool_calls) continue;
    for (const tc of msg.tool_calls) {
      const toolType = tc?.tool_type;
      if (toolType === "task_plan") hasTaskPlan = true;
      if (toolType === "web_search" || toolType === "search" || toolType === "deep_thinking") hasWebSearch = true;
      if (toolType === "image_search") hasImageSearch = true;
      if (toolType === "ppt_outline") hasPptOutline = true;
      if (toolType === "create_slide" || toolType === "ppt_generate") return "ppt_preview";
    }
  }

  if (hasPptOutline) return "ppt_outline";
  if (hasImageSearch) return "image_search";
  if (hasWebSearch) return "web_search";
  if (hasTaskPlan) return "task_plan";
  return null;
}

export function useConversationManager() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [pptProjects, setPptProjects] = useState<PPTProject[]>([]);

  const sortConversations = useCallback((list: Conversation[]) =>
    [...list].sort((a, b) => {
      const aPinned = (a as any).pinned ? 1 : 0;
      const bPinned = (b as any).pinned ? 1 : 0;
      if (aPinned !== bPinned) return bPinned - aPinned;
      const aRunning = a.task_status === "running" ? 1 : 0;
      const bRunning = b.task_status === "running" ? 1 : 0;
      if (aRunning !== bRunning) return bRunning - aRunning;
      const aUpdated = a.updated_at ? new Date(a.updated_at).getTime() : 0;
      const bUpdated = b.updated_at ? new Date(b.updated_at).getTime() : 0;
      if (aUpdated !== bUpdated) return bUpdated - aUpdated;
      return (b.id || 0) - (a.id || 0);
    }), []);

  const loadConversations = useCallback(async () => {
    try {
      const data = await getConversations();
      setConversations(prev => {
        const sorted = [...data].sort((a, b) => {
          const aPinned = (a as any).pinned ? 1 : 0;
          const bPinned = (b as any).pinned ? 1 : 0;
          if (aPinned !== bPinned) return bPinned - aPinned;
          const aRunning = a.task_status === "running" ? 1 : 0;
          const bRunning = b.task_status === "running" ? 1 : 0;
          if (aRunning !== bRunning) return bRunning - aRunning;
          const aUpdated = a.updated_at ? new Date(a.updated_at).getTime() : 0;
          const bUpdated = b.updated_at ? new Date(b.updated_at).getTime() : 0;
          if (aUpdated !== bUpdated) return bUpdated - aUpdated;
          return (b.id || 0) - (a.id || 0);
        });
        return sorted;
      });
    } catch (error) {
      console.error("Failed to load conversations:", error);
    }
  }, []);

  const loadPPTProjects = useCallback(async () => {
    try {
      const data = await getPPTProjects();
      setPptProjects(data);
    } catch (error) {
      console.error("Failed to load PPT projects:", error);
    }
  }, []);

  const loadConversationDetail = useCallback(async (uuid: string): Promise<LoadConversationResult> => {
    const data = await getConversationDetail(uuid);

    let hasPptSlides = false;
    let pptProject: PPTProject | null = null;
    let pptHtmlCode = "";
    let topic = "";

    if (data.ppt_project) {
      const project = data.ppt_project;
      pptProject = project;
      if (project.slides && project.slides.length > 0) {
        hasPptSlides = true;
        pptHtmlCode = project.slides
          .sort((a: any, b: any) => a.page_number - b.page_number)
          .map((slide: any) => slide.html_content)
          .join("\n");
      }
      topic = project.title;
    } else {
      topic = data.conversation.title;
    }

    // 恢复消息
    const restoredMessages: Message[] = (data.messages || []).map((msg: any) => ({
      id: msg.id.toString(),
      role: msg.role,
      content: msg.content,
      timestamp: new Date(msg.created_at).getTime(),
      attachments: (msg.attachments || []).map((att: any) => ({
        id: att.id,
        filename: att.filename,
        file_path: att.file_path,
        file_size: att.file_size,
        content_type: att.content_type,
      })),
      toolCalls: msg.tool_calls?.map((tc: any) => ({
        id: tc.id.toString(),
        type: tc.tool_type,
        name: tc.tool_name,
        status: tc.status,
        data: { ...(tc.arguments || {}), ...(tc.result || {}) },
      })),
      streaming: false,
    }));

    // 提取任务规划（兼容两种数据来源：task_plan 关联表 / tool_call result）
    let taskPlan: TaskPlan | null = null;
    for (const msg of data.messages || []) {
      if (msg.tool_calls) {
        for (const tc of msg.tool_calls) {
          if (tc.tool_type !== "task_plan") continue;

          if (tc.task_plan) {
            const fromResult = tc.result || {};
            const hasStructured =
              !!(fromResult.coreRequirement || fromResult.core_requirement) ||
              !!(fromResult.problemAnalysis || fromResult.problem_analysis) ||
              !!(fromResult.informationDimensions || fromResult.information_dimensions) ||
              !!(fromResult.searchStrategy || fromResult.search_strategy);
            taskPlan = {
              thinkingNarrative:
                fromResult.thinkingNarrative ||
                fromResult.thinking_narrative ||
                "",
              coreRequirement: fromResult.coreRequirement || fromResult.core_requirement || "",
              problemAnalysis: fromResult.problemAnalysis || fromResult.problem_analysis,
              informationDimensions: fromResult.informationDimensions || fromResult.information_dimensions,
              searchStrategy: fromResult.searchStrategy || fromResult.search_strategy,
              streamContent: hasStructured ? (fromResult.streamContent || "") : (tc.task_plan.plan_content || fromResult.streamContent || ""),
              steps: tc.task_plan.steps || fromResult.steps || [],
            };
            continue;
          }

          const raw = tc.result || tc.arguments || {};
          const fallbackSteps = Array.isArray(raw.steps) ? raw.steps : [];
          const fallbackContent = typeof raw.plan_content === "string"
            ? raw.plan_content
            : (typeof raw.streamContent === "string" ? raw.streamContent : "");
          if (fallbackSteps.length > 0 || fallbackContent) {
            taskPlan = {
              thinkingNarrative: typeof raw.thinkingNarrative === "string"
                ? raw.thinkingNarrative
                : (typeof raw.thinking_narrative === "string" ? raw.thinking_narrative : ""),
              coreRequirement: raw.coreRequirement || raw.core_requirement || "",
              problemAnalysis: raw.problemAnalysis || raw.problem_analysis,
              informationDimensions: raw.informationDimensions || raw.information_dimensions,
              searchStrategy: raw.searchStrategy || raw.search_strategy,
              streamContent: fallbackContent,
              steps: fallbackSteps,
            };
          }
        }
      }
    }

    // 提取搜索轮次
    const extractedRounds: SearchRound[] = [];
    for (const msg of data.messages || []) {
      if (msg.tool_calls) {
        for (const tc of msg.tool_calls) {
          if ((tc.tool_type === "web_search" || tc.tool_type === "search") && tc.search_rounds) {
            for (const sr of tc.search_rounds) {
              extractedRounds.push({
                round: sr.round_number,
                query: sr.query,
                results: sr.results?.map((r: any) => ({
                  title: r.title, url: r.url, snippet: r.snippet, date: r.date,
                })) || [],
                isCompleted: true,
                thinking: sr.thinking || "",
              });
            }
          }
        }
      }
    }

    // 提取图片搜索轮次
    const imageRoundsMap = new Map<number, ImageSearchRound>();
    for (const msg of data.messages || []) {
      if (msg.tool_calls) {
        for (const tc of msg.tool_calls) {
          if (tc.tool_type === "image_search") {
            const rawRound = tc.arguments?.round ?? tc.result?.round ?? 1;
            const round = typeof rawRound === "number" ? rawRound : Number(rawRound) || 1;
            const query = tc.arguments?.query || tc.result?.query || "";
            const images = tc.result?.images || tc.arguments?.images || [];
            const existing = imageRoundsMap.get(round);
            if (existing) {
              existing.images = [...existing.images, ...images];
            } else {
              imageRoundsMap.set(round, { round, query, images, isCompleted: true });
            }
          }
        }
      }
    }
    const imageSearchRounds = Array.from(imageRoundsMap.values()).sort((a, b) => a.round - b.round);

    // 提取 PPT 大纲
    let pptOutline = "";
    for (const msg of data.messages || []) {
      if (msg.tool_calls) {
        for (const tc of msg.tool_calls) {
          if (tc.tool_type === "ppt_outline" && tc.result) {
            pptOutline = tc.result.content || "";
          }
        }
      }
    }

    const nextPanelType = resolvePanelTypeFromConversation(data.messages, hasPptSlides);

    return {
      conversationId: typeof data?.conversation?.id === "number" ? data.conversation.id : null,
      hasPptSlides,
      nextPanelType,
      restoredMessages,
      taskPlan,
      searchRounds: extractedRounds,
      imageSearchRounds,
      pptOutline,
      pptProject,
      pptHtmlCode,
      pptProjects: (data as any).ppt_projects || [],
      sessionId: data.session_id || null,
      searchMode: (data.search_mode === "auto" || data.search_mode === "on" || data.search_mode === "off")
        ? data.search_mode : null,
      taskStatus: data.task_status || "",
      topic,
    };
  }, []);

  const refreshPPTProject = useCallback(async (
    projectId: number,
    options?: { preserveHtml?: boolean },
    currentHtml?: string
  ): Promise<{ project: PPTProject; htmlCode: string; subVersionMap: Record<number, PPTVersion> } | null> => {
    try {
      const project = await getPPTProject(projectId);
      const allVersions = project.versions || [];
      // Top-level versions only (no parent_version_id)
      const topVersions = allVersions
        .filter((v: any) => !v.parent_version_id)
        .slice()
        .sort((a: any, b: any) => a.version_number - b.version_number);
      const latestVersion = topVersions[topVersions.length - 1];
      const slides = latestVersion?.slides || [];
      const enriched = { ...project, current_version: latestVersion, slides, versions: topVersions } as PPTProject;

      // Build map: parentVersionId -> sub-version (for editSnapshots restoration)
      const subVersionMap: Record<number, PPTVersion> = {};
      for (const v of allVersions) {
        if ((v as any).parent_version_id) {
          subVersionMap[(v as any).parent_version_id] = v;
        }
      }

      let htmlCode = "";
      if (slides.length > 0) {
        const freshHtml = slides
          .sort((a: any, b: any) => a.page_number - b.page_number)
          .map((slide: any) => slide.html_content)
          .join("\n");

        if (options?.preserveHtml && currentHtml) {
          const prevCount = currentHtml
            .split(/(?=<!DOCTYPE html>)/i)
            .filter((h: string) => h.trim()).length;
          htmlCode = prevCount === slides.length ? currentHtml : freshHtml;
        } else {
          htmlCode = freshHtml;
        }
      }

      return { project: enriched, htmlCode, subVersionMap };
    } catch (error) {
      console.error("Failed to refresh PPT project:", error);
      return null;
    }
  }, []);

  const deleteConv = useCallback(async (id: number) => {
    try {
      await deleteConversation(id);
      setConversations(prev => prev.filter(c => c.id !== id));
      toast.success("对话已删除");
      return true;
    } catch (error) {
      console.error("Failed to delete conversation:", error);
      toast.error("删除失败");
      return false;
    }
  }, []);

  const renameConv = useCallback(async (id: number, newTitle: string) => {
    try {
      await updateConversation(id, newTitle);
      setConversations(prev => prev.map(c => c.id === id ? { ...c, title: newTitle } : c));
      toast.success("重命名成功");
    } catch (error) {
      console.error("Failed to rename conversation:", error);
      toast.error("重命名失败");
    }
  }, []);

  const pinConv = useCallback(async (id: number, pinned: boolean) => {
    try {
      setConversations(prev => {
        const updated = prev.map(c => c.id === id ? { ...c, pinned } as Conversation : c);
        return updated.sort((a, b) => {
          const aPinned = (a as any).pinned ? 1 : 0;
          const bPinned = (b as any).pinned ? 1 : 0;
          if (aPinned !== bPinned) return bPinned - aPinned;
          const aRunning = a.task_status === "running" ? 1 : 0;
          const bRunning = b.task_status === "running" ? 1 : 0;
          if (aRunning !== bRunning) return bRunning - aRunning;
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
        });
      });
      toast.success(pinned ? "已置顶" : "已取消置顶");
    } catch (error) {
      console.error("Failed to pin conversation:", error);
      toast.error("操作失败");
    }
  }, []);

  const markConversationRunning = useCallback((id: number) => {
    setConversations(prev =>
      [...prev]
        .map(c => c.id === id ? { ...c, task_status: "running" as const } : c)
        .sort((a, b) => {
          const aPinned = (a as any).pinned ? 1 : 0;
          const bPinned = (b as any).pinned ? 1 : 0;
          if (aPinned !== bPinned) return bPinned - aPinned;
          const aRunning = a.task_status === "running" ? 1 : 0;
          const bRunning = b.task_status === "running" ? 1 : 0;
          if (aRunning !== bRunning) return bRunning - aRunning;
          const aUpdated = a.updated_at ? new Date(a.updated_at).getTime() : 0;
          const bUpdated = b.updated_at ? new Date(b.updated_at).getTime() : 0;
          if (aUpdated !== bUpdated) return bUpdated - aUpdated;
          return (b.id || 0) - (a.id || 0);
        })
    );
  }, []);

  return {
    conversations,
    setConversations,
    pptProjects,
    setPptProjects,
    loadConversations,
    loadPPTProjects,
    loadConversationDetail,
    refreshPPTProject,
    deleteConv,
    renameConv,
    pinConv,
    markConversationRunning,
  };
}

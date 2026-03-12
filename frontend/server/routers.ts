import { COOKIE_NAME } from "@shared/const";
import { getSessionCookieOptions } from "./_core/cookies";
import { systemRouter } from "./_core/systemRouter";
import { publicProcedure, protectedProcedure, router } from "./_core/trpc";
import { z } from "zod";
import { understandIntent, continueConversation, executeTool, getCurrentSessionId, setCurrentSessionId } from "./pptagent";

export const appRouter = router({
  system: systemRouter,
  auth: router({
    me: publicProcedure.query(opts => opts.ctx.user),
    logout: publicProcedure.mutation(({ ctx }) => {
      const cookieOptions = getSessionCookieOptions(ctx.req);
      ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
      return {
        success: true,
      } as const;
    }),
  }),

  // PPTAgent 路由
  ppt: router({
    // 发送消息并获取 AI 响应
    chat: publicProcedure
      .input(z.object({
        message: z.string(),
        conversationHistory: z.array(z.object({
          role: z.enum(["system", "user", "assistant", "tool"]),
          content: z.string(),
          name: z.string().optional(),
          tool_call_id: z.string().optional(),
        })).optional(),
        sessionId: z.string().optional(),
      }))
      .mutation(async ({ input }) => {
        try {
          if (!input.conversationHistory || input.conversationHistory.length === 0) {
            // 新对话，理解用户意图
            const result = await understandIntent(input.message);
            return {
              success: true,
              content: result.content,
              toolCall: result.toolCall,
              sessionId: result.sessionId,
            };
          } else {
            // 继续对话
            const result = await continueConversation(input.conversationHistory, undefined, input.sessionId);
            return {
              success: true,
              content: result.content,
              toolCall: result.toolCall,
              sessionId: getCurrentSessionId(),
            };
          }
        } catch (error) {
          console.error("PPT chat error:", error);
          return {
            success: false,
            error: error instanceof Error ? error.message : "Unknown error",
          };
        }
      }),

    // 确认补充信息
    confirmInfo: publicProcedure
      .input(z.object({
        toolCallId: z.string(),
        selectedData: z.record(z.string(), z.unknown()),
        topic: z.string(),
        sessionId: z.string().optional(),
      }))
      .mutation(async ({ input }) => {
        // 设置 session_id
        if (input.sessionId) {
          setCurrentSessionId(input.sessionId);
        }

        // 用户确认补充信息后，继续生成PPT
        const conversationHistory = [
          { role: "user" as const, content: `请帮我制作一份关于"${input.topic}"的PPT` },
          { role: "assistant" as const, content: `好的，我已收到您的补充信息：${JSON.stringify(input.selectedData)}。现在我将为您生成任务规划。` },
        ];

        try {
          const result = await continueConversation(conversationHistory, {
            name: "supplement_info",
            result: JSON.stringify({ confirmed: true, data: input.selectedData }),
          }, input.sessionId);
          return {
            success: true,
            content: result.content,
            toolCall: result.toolCall,
            sessionId: getCurrentSessionId(),
          };
        } catch (error) {
          console.error("Confirm info error:", error);
          return {
            success: false,
            content: "处理确认信息时出错",
            toolCall: undefined,
            sessionId: getCurrentSessionId(),
          };
        }
      }),

    // 执行工具调用
    executeTool: publicProcedure
      .input(z.object({
        toolName: z.string(),
        args: z.record(z.string(), z.unknown()),
      }))
      .mutation(async ({ input }) => {
        try {
          const result = await executeTool(input.toolName, input.args);
          return result;
        } catch (error) {
          console.error("Tool execution error:", error);
          return {
            success: false,
            result: { error: error instanceof Error ? error.message : "Unknown error" },
          };
        }
      }),

    // 继续生成（在工具执行后）
    continue: publicProcedure
      .input(z.object({
        conversationHistory: z.array(z.object({
          role: z.enum(["system", "user", "assistant", "tool"]),
          content: z.string(),
          name: z.string().optional(),
          tool_call_id: z.string().optional(),
        })),
        toolResult: z.object({
          name: z.string(),
          result: z.string(),
        }).optional(),
      }))
      .mutation(async ({ input }) => {
        try {
          const result = await continueConversation(
            input.conversationHistory,
            input.toolResult || undefined
          );
          return {
            success: true,
            content: result.content,
            toolCall: result.toolCall,
          };
        } catch (error) {
          console.error("Continue conversation error:", error);
          return {
            success: false,
            error: error instanceof Error ? error.message : "Unknown error",
          };
        }
      }),

    // 获取生成的 PPT 数据
    getSlides: publicProcedure
      .input(z.object({
        sessionId: z.string(),
      }))
      .query(async ({ input }) => {
        // 这里可以从数据库或缓存获取生成的幻灯片
        // 目前返回模拟数据
        return {
          slides: [],
          totalPages: 0,
        };
      }),
  }),
});

export type AppRouter = typeof appRouter;

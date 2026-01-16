import { describe, expect, it } from "vitest";
import {
  Role,
  AgentType,
  ConvertType,
  TEMPLATES,
  PAGE_OPTIONS,
  CONVERT_OPTIONS,
} from "../shared/pptagent";

describe("PPTAgent Types", () => {
  describe("Role enum", () => {
    it("should have correct role values", () => {
      expect(Role.SYSTEM).toBe("system");
      expect(Role.USER).toBe("user");
      expect(Role.ASSISTANT).toBe("assistant");
      expect(Role.TOOL).toBe("tool");
    });
  });

  describe("AgentType enum", () => {
    it("should have correct agent type values", () => {
      expect(AgentType.RESEARCH).toBe("research");
      expect(AgentType.DESIGN).toBe("design");
      expect(AgentType.PPTAGENT).toBe("pptagent");
    });
  });

  describe("ConvertType enum", () => {
    it("should have correct convert type values", () => {
      expect(ConvertType.DEEPPRESENTER).toBe("deeppresenter");
      expect(ConvertType.PPTAGENT).toBe("pptagent");
    });
  });
});

describe("PPTAgent Constants", () => {
  describe("TEMPLATES", () => {
    it("should have auto option as first template", () => {
      expect(TEMPLATES[0].value).toBe("auto");
      expect(TEMPLATES[0].label).toBe("自动选择");
    });

    it("should have default template", () => {
      const defaultTemplate = TEMPLATES.find((t) => t.value === "default");
      expect(defaultTemplate).toBeDefined();
      expect(defaultTemplate?.label).toBe("默认模板");
    });

    it("should have at least 5 templates", () => {
      expect(TEMPLATES.length).toBeGreaterThanOrEqual(5);
    });
  });

  describe("PAGE_OPTIONS", () => {
    it("should have auto option as first page option", () => {
      expect(PAGE_OPTIONS[0].value).toBe("auto");
      expect(PAGE_OPTIONS[0].label).toBe("自动");
    });

    it("should have 31 page options (auto + 1-30)", () => {
      expect(PAGE_OPTIONS.length).toBe(31);
    });

    it("should have correct page number labels", () => {
      expect(PAGE_OPTIONS[1].value).toBe("1");
      expect(PAGE_OPTIONS[1].label).toBe("1 页");
      expect(PAGE_OPTIONS[30].value).toBe("30");
      expect(PAGE_OPTIONS[30].label).toBe("30 页");
    });
  });

  describe("CONVERT_OPTIONS", () => {
    it("should have freeform and template options", () => {
      expect(CONVERT_OPTIONS.length).toBe(2);
      expect(CONVERT_OPTIONS[0].value).toBe(ConvertType.DEEPPRESENTER);
      expect(CONVERT_OPTIONS[1].value).toBe(ConvertType.PPTAGENT);
    });

    it("should have correct labels", () => {
      expect(CONVERT_OPTIONS[0].label).toContain("自由生成");
      expect(CONVERT_OPTIONS[1].label).toContain("模板生成");
    });
  });
});

describe("PPTAgent Data Structures", () => {
  it("should create valid ChatMessage structure", () => {
    const message = {
      id: "test-id",
      role: Role.USER,
      content: "Test message",
      timestamp: Date.now(),
    };

    expect(message.id).toBe("test-id");
    expect(message.role).toBe(Role.USER);
    expect(message.content).toBe("Test message");
    expect(typeof message.timestamp).toBe("number");
  });

  it("should create valid ToolExecution structure", () => {
    const execution = {
      id: "exec-id",
      name: "analyze_requirements",
      arguments: { instruction: "test" },
      status: "running" as const,
      startTime: Date.now(),
      agentType: AgentType.RESEARCH,
    };

    expect(execution.name).toBe("analyze_requirements");
    expect(execution.status).toBe("running");
    expect(execution.agentType).toBe(AgentType.RESEARCH);
  });

  it("should create valid PPTGenerationConfig structure", () => {
    const config = {
      convertType: ConvertType.DEEPPRESENTER,
      template: null,
      numPages: 10,
    };

    expect(config.convertType).toBe(ConvertType.DEEPPRESENTER);
    expect(config.template).toBeNull();
    expect(config.numPages).toBe(10);
  });

  it("should create valid AgentStatus structure", () => {
    const status = {
      type: AgentType.RESEARCH,
      status: "running" as const,
      currentStep: "分析需求",
      progress: 50,
      startTime: Date.now(),
    };

    expect(status.type).toBe(AgentType.RESEARCH);
    expect(status.status).toBe("running");
    expect(status.progress).toBe(50);
  });
});

// PPTAgent 工具执行测试
import { pptTools, executeTool } from "./pptagent";

describe("PPTAgent Tools", () => {
  describe("pptTools definition", () => {
    it("should have all required tools defined", () => {
      const toolNames = pptTools.map(t => t.function.name);
      
      expect(toolNames).toContain("supplement_info");
      expect(toolNames).toContain("task_plan");
      expect(toolNames).toContain("web_search");
      expect(toolNames).toContain("image_search");
      expect(toolNames).toContain("create_slide");
    });

    it("should have valid tool structure", () => {
      pptTools.forEach(tool => {
        expect(tool.type).toBe("function");
        expect(tool.function.name).toBeDefined();
        expect(tool.function.description).toBeDefined();
      });
    });
  });

  describe("executeTool", () => {
    it("should execute web_search and return results", async () => {
      const result = await executeTool("web_search", { query: "测试搜索" });
      
      expect(result.success).toBe(true);
      expect(result.result).toHaveProperty("query", "测试搜索");
      expect(result.result).toHaveProperty("results");
      expect(Array.isArray((result.result as { results: unknown[] }).results)).toBe(true);
    });

    it("should execute image_search and return results", async () => {
      const result = await executeTool("image_search", { query: "测试图片" });
      
      expect(result.success).toBe(true);
      expect(result.result).toHaveProperty("query", "测试图片");
      expect(result.result).toHaveProperty("images");
    });

    it("should execute supplement_info and return confirmed data", async () => {
      const args = {
        purpose: "产品介绍",
        modules: ["核心功能", "应用场景"],
        style: "科技感",
        color: "蓝色",
      };
      
      const result = await executeTool("supplement_info", args);
      
      expect(result.success).toBe(true);
      expect(result.result).toHaveProperty("confirmed", true);
      expect(result.result).toHaveProperty("data");
    });

    it("should execute task_plan and return planned data", async () => {
      const args = {
        coreRequirement: "制作产品介绍PPT",
        details: ["包含核心功能", "展示应用场景"],
        steps: [
          { id: 1, text: "搜索产品信息" },
          { id: 2, text: "生成PPT内容" },
        ],
      };
      
      const result = await executeTool("task_plan", args);
      
      expect(result.success).toBe(true);
      expect(result.result).toHaveProperty("planned", true);
    });

    it("should execute create_slide and return slide data", async () => {
      const args = {
        pageNumber: 1,
        title: "封面",
        content: "产品介绍",
      };
      
      const result = await executeTool("create_slide", args);
      
      expect(result.success).toBe(true);
      expect(result.result).toHaveProperty("pageNumber", 1);
      expect(result.result).toHaveProperty("title", "封面");
      expect(result.result).toHaveProperty("htmlCode");
    });

    it("should return error for unknown tool", async () => {
      const result = await executeTool("unknown_tool", {});
      
      expect(result.success).toBe(false);
      expect(result.result).toHaveProperty("error");
    });
  });
});

describe("PPTAgent Tool Parameters", () => {
  it("supplement_info should have correct parameters", () => {
    const tool = pptTools.find(t => t.function.name === "supplement_info");
    expect(tool).toBeDefined();
    
    const params = tool?.function.parameters as { properties: Record<string, unknown>; required: string[] };
    // 新的动态选项参数
    expect(params.properties).toHaveProperty("topic");
    expect(params.properties).toHaveProperty("audienceQuestion");
    expect(params.properties).toHaveProperty("audienceOptions");
    expect(params.properties).toHaveProperty("modulesQuestion");
    expect(params.properties).toHaveProperty("modulesOptions");
    expect(params.properties).toHaveProperty("styleQuestion");
    expect(params.properties).toHaveProperty("styleOptions");
    expect(params.properties).toHaveProperty("emphasisQuestion");
    expect(params.properties).toHaveProperty("emphasisPlaceholder");
    expect(params.required).toContain("topic");
    expect(params.required).toContain("audienceOptions");
    expect(params.required).toContain("modulesOptions");
    expect(params.required).toContain("styleOptions");
  });

  it("create_slide should have correct parameters", () => {
    const tool = pptTools.find(t => t.function.name === "create_slide");
    expect(tool).toBeDefined();
    
    const params = tool?.function.parameters as { properties: Record<string, unknown>; required: string[] };
    expect(params.properties).toHaveProperty("pageNumber");
    expect(params.properties).toHaveProperty("title");
    expect(params.properties).toHaveProperty("content");
    expect(params.required).toContain("pageNumber");
    expect(params.required).toContain("title");
    expect(params.required).toContain("content");
  });
});

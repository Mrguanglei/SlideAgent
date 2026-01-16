import React, { createContext, useContext, useReducer, useCallback, ReactNode } from "react";
import {
  ChatMessage,
  AgentStatus,
  ToolExecution,
  PPTGenerationState,
  FileAttachment,
  ConversationState,
  Role,
  AgentType,
  ConvertType,
} from "@shared/pptagent";
import { nanoid } from "nanoid";

// Action types
type Action =
  | { type: "ADD_MESSAGE"; payload: Omit<ChatMessage, "id" | "timestamp"> }
  | { type: "UPDATE_MESSAGE"; payload: { id: string; updates: Partial<ChatMessage> } }
  | { type: "SET_AGENT_STATUS"; payload: AgentStatus }
  | { type: "ADD_TOOL_EXECUTION"; payload: Omit<ToolExecution, "id"> }
  | { type: "UPDATE_TOOL_EXECUTION"; payload: { id: string; updates: Partial<ToolExecution> } }
  | { type: "SET_PPT_STATE"; payload: Partial<PPTGenerationState> }
  | { type: "ADD_ATTACHMENT"; payload: Omit<FileAttachment, "id"> }
  | { type: "REMOVE_ATTACHMENT"; payload: string }
  | { type: "UPDATE_ATTACHMENT"; payload: { id: string; updates: Partial<FileAttachment> } }
  | { type: "CLEAR_ATTACHMENTS" }
  | { type: "SET_PROCESSING"; payload: boolean }
  | { type: "RESET_CONVERSATION" };

// Initial state
const initialState: ConversationState = {
  messages: [],
  attachments: [],
  agentStatuses: [
    { type: AgentType.RESEARCH, status: "idle" },
    { type: AgentType.DESIGN, status: "idle" },
    { type: AgentType.PPTAGENT, status: "idle" },
  ],
  toolExecutions: [],
  pptState: {
    status: "idle",
    config: {
      convertType: ConvertType.DEEPPRESENTER,
      template: null,
      numPages: null,
    },
  },
  isProcessing: false,
};

// Reducer
function reducer(state: ConversationState, action: Action): ConversationState {
  switch (action.type) {
    case "ADD_MESSAGE":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            ...action.payload,
            id: nanoid(),
            timestamp: Date.now(),
          },
        ],
      };

    case "UPDATE_MESSAGE":
      return {
        ...state,
        messages: state.messages.map((msg) =>
          msg.id === action.payload.id ? { ...msg, ...action.payload.updates } : msg
        ),
      };

    case "SET_AGENT_STATUS":
      return {
        ...state,
        agentStatuses: state.agentStatuses.map((status) =>
          status.type === action.payload.type ? action.payload : status
        ),
      };

    case "ADD_TOOL_EXECUTION":
      return {
        ...state,
        toolExecutions: [
          ...state.toolExecutions,
          {
            ...action.payload,
            id: nanoid(),
          },
        ],
      };

    case "UPDATE_TOOL_EXECUTION":
      return {
        ...state,
        toolExecutions: state.toolExecutions.map((exec) =>
          exec.id === action.payload.id ? { ...exec, ...action.payload.updates } : exec
        ),
      };

    case "SET_PPT_STATE":
      return {
        ...state,
        pptState: { ...state.pptState, ...action.payload },
      };

    case "ADD_ATTACHMENT":
      return {
        ...state,
        attachments: [
          ...state.attachments,
          {
            ...action.payload,
            id: nanoid(),
          },
        ],
      };

    case "REMOVE_ATTACHMENT":
      return {
        ...state,
        attachments: state.attachments.filter((att) => att.id !== action.payload),
      };

    case "UPDATE_ATTACHMENT":
      return {
        ...state,
        attachments: state.attachments.map((att) =>
          att.id === action.payload.id ? { ...att, ...action.payload.updates } : att
        ),
      };

    case "CLEAR_ATTACHMENTS":
      return {
        ...state,
        attachments: [],
      };

    case "SET_PROCESSING":
      return {
        ...state,
        isProcessing: action.payload,
      };

    case "RESET_CONVERSATION":
      return initialState;

    default:
      return state;
  }
}

// Context
interface PPTAgentContextType {
  state: ConversationState;
  addMessage: (message: Omit<ChatMessage, "id" | "timestamp">) => void;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  setAgentStatus: (status: AgentStatus) => void;
  addToolExecution: (execution: Omit<ToolExecution, "id">) => void;
  updateToolExecution: (id: string, updates: Partial<ToolExecution>) => void;
  setPPTState: (state: Partial<PPTGenerationState>) => void;
  addAttachment: (attachment: Omit<FileAttachment, "id">) => void;
  removeAttachment: (id: string) => void;
  updateAttachment: (id: string, updates: Partial<FileAttachment>) => void;
  clearAttachments: () => void;
  setProcessing: (processing: boolean) => void;
  resetConversation: () => void;
}

const PPTAgentContext = createContext<PPTAgentContextType | null>(null);

// Provider
export function PPTAgentProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const addMessage = useCallback((message: Omit<ChatMessage, "id" | "timestamp">) => {
    dispatch({ type: "ADD_MESSAGE", payload: message });
  }, []);

  const updateMessage = useCallback((id: string, updates: Partial<ChatMessage>) => {
    dispatch({ type: "UPDATE_MESSAGE", payload: { id, updates } });
  }, []);

  const setAgentStatus = useCallback((status: AgentStatus) => {
    dispatch({ type: "SET_AGENT_STATUS", payload: status });
  }, []);

  const addToolExecution = useCallback((execution: Omit<ToolExecution, "id">) => {
    dispatch({ type: "ADD_TOOL_EXECUTION", payload: execution });
  }, []);

  const updateToolExecution = useCallback((id: string, updates: Partial<ToolExecution>) => {
    dispatch({ type: "UPDATE_TOOL_EXECUTION", payload: { id, updates } });
  }, []);

  const setPPTState = useCallback((pptState: Partial<PPTGenerationState>) => {
    dispatch({ type: "SET_PPT_STATE", payload: pptState });
  }, []);

  const addAttachment = useCallback((attachment: Omit<FileAttachment, "id">) => {
    dispatch({ type: "ADD_ATTACHMENT", payload: attachment });
  }, []);

  const removeAttachment = useCallback((id: string) => {
    dispatch({ type: "REMOVE_ATTACHMENT", payload: id });
  }, []);

  const updateAttachment = useCallback((id: string, updates: Partial<FileAttachment>) => {
    dispatch({ type: "UPDATE_ATTACHMENT", payload: { id, updates } });
  }, []);

  const clearAttachments = useCallback(() => {
    dispatch({ type: "CLEAR_ATTACHMENTS" });
  }, []);

  const setProcessing = useCallback((processing: boolean) => {
    dispatch({ type: "SET_PROCESSING", payload: processing });
  }, []);

  const resetConversation = useCallback(() => {
    dispatch({ type: "RESET_CONVERSATION" });
  }, []);

  return (
    <PPTAgentContext.Provider
      value={{
        state,
        addMessage,
        updateMessage,
        setAgentStatus,
        addToolExecution,
        updateToolExecution,
        setPPTState,
        addAttachment,
        removeAttachment,
        updateAttachment,
        clearAttachments,
        setProcessing,
        resetConversation,
      }}
    >
      {children}
    </PPTAgentContext.Provider>
  );
}

// Hook
export function usePPTAgent() {
  const context = useContext(PPTAgentContext);
  if (!context) {
    throw new Error("usePPTAgent must be used within a PPTAgentProvider");
  }
  return context;
}

import { create } from "zustand";
import type { ChatMessage, DecisionPoint } from "@/types/chat";

interface ChatStore {
  messages: ChatMessage[];
  isStreaming: boolean;
  pendingDecision: DecisionPoint | null;
  addMessage: (message: ChatMessage) => void;
  setStreaming: (streaming: boolean) => void;
  setPendingDecision: (decision: DecisionPoint | null) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  isStreaming: false,
  pendingDecision: null,
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  setStreaming: (isStreaming) => set({ isStreaming }),
  setPendingDecision: (pendingDecision) => set({ pendingDecision }),
  clearMessages: () => set({ messages: [], pendingDecision: null }),
}));

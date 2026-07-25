import { create } from "zustand";
import type { AgentInfo } from "@/types/agent";
import type { PipelinePhase, PipelineStatus } from "@/types/project";

interface PipelineStore {
  agents: AgentInfo[];
  currentPhase: PipelinePhase;
  status: PipelineStatus;
  elapsedMs: number;
  setAgents: (agents: AgentInfo[]) => void;
  updateAgent: (agentId: string, update: Partial<AgentInfo>) => void;
  setPhase: (phase: PipelinePhase) => void;
  setStatus: (status: PipelineStatus) => void;
  setElapsed: (ms: number) => void;
}

export const usePipelineStore = create<PipelineStore>((set) => ({
  agents: [],
  currentPhase: "idle",
  status: "idle",
  elapsedMs: 0,
  setAgents: (agents) => set({ agents }),
  updateAgent: (agentId, update) =>
    set((state) => ({
      agents: state.agents.map((a) =>
        a.id === agentId ? { ...a, ...update } : a
      ),
    })),
  setPhase: (currentPhase) => set({ currentPhase }),
  setStatus: (status) => set({ status }),
  setElapsed: (elapsedMs) => set({ elapsedMs }),
}));

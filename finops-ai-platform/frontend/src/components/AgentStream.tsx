"use client";

import { api } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */

const AGENTS = [
    { id: "root_cause_analyzer", label: "Root Cause Analyzer", icon: "🔍" },
    { id: "tag_intelligence", label: "Tag Intelligence", icon: "🏷️" },
    { id: "cost_forecaster", label: "Cost Forecaster", icon: "📈" },
    { id: "action_planner", label: "Action Planner", icon: "⚡" },
];

interface Props {
    events: any[];
    isRunning: boolean;
    dataLoaded: boolean;
    onStart: () => void;
    onEvent: (event: any) => void;
    onComplete: () => void;
    onError: (err: string) => void;
}

export default function AgentStream({
    events,
    isRunning,
    dataLoaded,
    onStart,
    onEvent,
    onComplete,
    onError,
}: Props) {
    const getAgentStatus = (agentId: string) => {
        const agentEvents = events.filter(
            (e) => e.agent === agentId || e.type === "agent_event" && e.agent === agentId
        );
        const lastEvent = agentEvents[agentEvents.length - 1];
        if (!lastEvent) return "pending";
        return lastEvent.status || "pending";
    };

    const handleRun = () => {
        onStart();
        api.runAnalysis(onEvent, onComplete, (err) => {
            onError(err);
        });
    };

    return (
        <div className="glass-panel p-4 mb-4">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <span className="text-lg">🔗</span>
                    <h2 className="text-sm font-semibold text-slate-300">Agent Pipeline</h2>
                </div>
                <button
                    onClick={handleRun}
                    disabled={!dataLoaded || isRunning}
                    className="px-4 py-1.5 rounded-lg bg-gradient-to-r from-emerald-600 to-cyan-600 text-white text-sm font-medium hover:from-emerald-500 hover:to-cyan-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-lg shadow-emerald-500/20"
                >
                    {isRunning ? "⏳ Running..." : "▶ Run Analysis"}
                </button>
            </div>

            <div className="flex items-center gap-2 overflow-x-auto pb-2">
                {AGENTS.map((agent, idx) => {
                    const status = getAgentStatus(agent.id);
                    return (
                        <div key={agent.id} className="flex items-center">
                            <div
                                className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium transition-all ${status === "done"
                                        ? "bg-emerald-900/30 text-emerald-400 border border-emerald-700/50"
                                        : status === "running"
                                            ? "bg-indigo-900/30 text-indigo-300 border border-indigo-600/50 agent-running"
                                            : status === "error"
                                                ? "bg-red-900/30 text-red-400 border border-red-700/50"
                                                : "bg-slate-800/50 text-slate-500 border border-slate-700/30"
                                    }`}
                            >
                                <span>{agent.icon}</span>
                                <span>{agent.label}</span>
                                {status === "done" && <span>✅</span>}
                                {status === "running" && <span>🔄</span>}
                                {status === "error" && <span>❌</span>}
                            </div>
                            {idx < AGENTS.length - 1 && (
                                <span className="text-slate-600 mx-1 text-xs">→</span>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

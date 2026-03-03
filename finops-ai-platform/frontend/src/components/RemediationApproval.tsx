"use client";

import { useState } from "react";
import { api } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */

interface Props {
    data: any | null;
}

export default function RemediationApproval({ data }: Props) {
    const [actionStates, setActionStates] = useState<Record<string, string>>({});
    const [expandedPolicy, setExpandedPolicy] = useState<string | null>(null);

    if (!data) {
        return (
            <div className="glass-panel p-5">
                <div className="flex items-center gap-2 mb-3">
                    <span className="text-lg">⚡</span>
                    <h2 className="text-sm font-semibold text-slate-300">Remediation Actions</h2>
                </div>
                <div className="text-slate-500 text-sm">Run analysis to see recommendations...</div>
            </div>
        );
    }

    if (data.error) {
        return (
            <div className="glass-panel p-5">
                <div className="flex items-center gap-2 mb-3">
                    <span className="text-lg">⚡</span>
                    <h2 className="text-sm font-semibold text-slate-300">Remediation Actions</h2>
                </div>
                <div className="text-red-400 text-sm">Error: {data.error}</div>
            </div>
        );
    }

    const handleAction = async (actionId: string, approved: boolean) => {
        setActionStates((prev) => ({ ...prev, [actionId]: "processing" }));
        try {
            await api.remediate(actionId, approved);
            setActionStates((prev) => ({
                ...prev,
                [actionId]: approved ? "approved" : "rejected",
            }));
        } catch {
            setActionStates((prev) => ({ ...prev, [actionId]: "error" }));
        }
    };

    const riskColors: Record<string, string> = {
        low: "bg-emerald-900/30 text-emerald-400 border-emerald-700/50",
        medium: "bg-amber-900/30 text-amber-400 border-amber-700/50",
        high: "bg-red-900/30 text-red-400 border-red-700/50",
    };

    return (
        <div className="glass-panel p-5">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <span className="text-lg">⚡</span>
                    <h2 className="text-sm font-semibold text-slate-300">Remediation Actions</h2>
                </div>
                {data.total_potential_savings > 0 && (
                    <span className="text-sm font-bold gradient-text">
                        Save ${data.total_potential_savings.toLocaleString()}/mo
                    </span>
                )}
            </div>

            <div className="space-y-3">
                {(data.recommended_actions || []).map((action: any) => {
                    const state = actionStates[action.action_id] || "pending";
                    return (
                        <div
                            key={action.action_id}
                            className="bg-slate-800/40 rounded-xl p-4 border border-slate-700/30 hover:border-slate-600/50 transition-colors"
                        >
                            <div className="flex items-start justify-between mb-2">
                                <div>
                                    <h3 className="text-sm font-medium text-slate-200">{action.title}</h3>
                                    <p className="text-xs text-slate-400 mt-0.5">{action.description}</p>
                                </div>
                                <div className="flex items-center gap-2 shrink-0 ml-4">
                                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${riskColors[action.risk_level] || riskColors.medium}`}>
                                        {action.risk_level?.toUpperCase()} RISK
                                    </span>
                                    <span className="text-xs font-semibold text-emerald-400">
                                        -${action.estimated_monthly_savings?.toLocaleString()}/mo
                                    </span>
                                </div>
                            </div>

                            {/* Affected Resources */}
                            {action.affected_resources?.length > 0 && (
                                <div className="flex flex-wrap gap-1 mb-3">
                                    {action.affected_resources.map((r: string, i: number) => (
                                        <span key={i} className="px-1.5 py-0.5 rounded bg-slate-700/50 text-[10px] text-slate-400 font-mono">
                                            {r}
                                        </span>
                                    ))}
                                </div>
                            )}

                            {/* Policy YAML toggle */}
                            {action.custodian_policy && (
                                <div className="mb-3">
                                    <button
                                        onClick={() => setExpandedPolicy(expandedPolicy === action.action_id ? null : action.action_id)}
                                        className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                                    >
                                        {expandedPolicy === action.action_id ? "▼ Hide" : "▶ View"} Cloud Custodian Policy
                                    </button>
                                    {expandedPolicy === action.action_id && (
                                        <pre className="mt-2 p-3 rounded-lg bg-slate-900/80 border border-slate-700/30 text-[11px] text-slate-300 font-mono overflow-x-auto whitespace-pre-wrap">
                                            {action.custodian_policy}
                                        </pre>
                                    )}
                                </div>
                            )}

                            {/* Action Buttons */}
                            <div className="flex items-center gap-2">
                                {state === "pending" && (
                                    <>
                                        <button
                                            onClick={() => handleAction(action.action_id, true)}
                                            className="px-4 py-1.5 rounded-lg bg-gradient-to-r from-emerald-600 to-emerald-700 text-white text-xs font-medium hover:from-emerald-500 hover:to-emerald-600 transition-all shadow-lg shadow-emerald-500/10"
                                        >
                                            ✅ Approve (Dry-Run)
                                        </button>
                                        <button
                                            onClick={() => handleAction(action.action_id, false)}
                                            className="px-4 py-1.5 rounded-lg bg-slate-700 text-slate-300 text-xs font-medium hover:bg-slate-600 transition-all"
                                        >
                                            ❌ Reject
                                        </button>
                                    </>
                                )}
                                {state === "processing" && (
                                    <span className="text-xs text-indigo-400 agent-running">Processing...</span>
                                )}
                                {state === "approved" && (
                                    <span className="text-xs text-emerald-400 font-medium">✅ Approved — dry-run executed</span>
                                )}
                                {state === "rejected" && (
                                    <span className="text-xs text-slate-500">❌ Rejected</span>
                                )}
                                {state === "error" && (
                                    <span className="text-xs text-red-400">⚠️ Error processing action</span>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            {data.plain_english && (
                <div className="mt-4 pt-3 border-t border-slate-700/50">
                    <p className="text-xs text-slate-400">{data.plain_english}</p>
                </div>
            )}
        </div>
    );
}

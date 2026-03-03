"use client";

/* eslint-disable @typescript-eslint/no-explicit-any */

interface Props {
    data: any | null;
}

export default function RCAPanel({ data }: Props) {
    if (!data) {
        return (
            <div className="glass-panel p-5">
                <div className="flex items-center gap-2 mb-3">
                    <span className="text-lg">🔍</span>
                    <h2 className="text-sm font-semibold text-slate-300">Root Cause Analysis</h2>
                </div>
                <div className="text-slate-500 text-sm">Run analysis to see results...</div>
            </div>
        );
    }

    if (data.error) {
        return (
            <div className="glass-panel p-5">
                <div className="flex items-center gap-2 mb-3">
                    <span className="text-lg">🔍</span>
                    <h2 className="text-sm font-semibold text-slate-300">Root Cause Analysis</h2>
                </div>
                <div className="text-red-400 text-sm">Error: {data.error}</div>
            </div>
        );
    }

    const urgencyColors: Record<string, string> = {
        critical: "bg-red-500",
        high: "bg-rose-500",
        medium: "bg-amber-500",
        low: "bg-emerald-500",
    };

    return (
        <div className="glass-panel p-5">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <span className="text-lg">🔍</span>
                    <h2 className="text-sm font-semibold text-slate-300">Root Cause Analysis</h2>
                </div>
                {data.urgency && (
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium text-white ${urgencyColors[data.urgency] || "bg-slate-600"}`}>
                        {data.urgency.toUpperCase()}
                    </span>
                )}
            </div>

            {/* Spike Summary */}
            {data.spike_summary && (
                <div className="bg-rose-900/20 border border-rose-800/30 rounded-xl p-3 mb-4">
                    <p className="text-sm text-rose-300 font-medium">{data.spike_summary}</p>
                    {data.spike_period && (
                        <p className="text-xs text-rose-400/60 mt-1">
                            {data.spike_period.start} → {data.spike_period.end}
                        </p>
                    )}
                </div>
            )}

            {/* Impacted Services */}
            {data.impacted_services?.map((svc: any, idx: number) => (
                <div key={idx} className="bg-slate-800/40 rounded-xl p-3 mb-3">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-slate-200">{svc.service}</span>
                        <span className="text-xs gradient-text-danger font-semibold">
                            +{svc.pct_change?.toFixed(0)}%
                        </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs text-slate-400 mb-2">
                        <div>Before: <span className="text-slate-300">${svc.cost_before?.toLocaleString()}</span></div>
                        <div>After: <span className="text-rose-400">${svc.cost_after?.toLocaleString()}</span></div>
                    </div>
                    {svc.root_cause && <p className="text-xs text-slate-400">{svc.root_cause}</p>}
                    {svc.deployed_by && (
                        <p className="text-xs text-indigo-400 mt-1">👤 {svc.deployed_by} · {svc.deployment_ref}</p>
                    )}
                </div>
            ))}

            {/* Contributing Factors */}
            {data.contributing_factors?.length > 0 && (
                <div className="mt-3">
                    <p className="text-xs font-medium text-slate-400 mb-2">Contributing Factors</p>
                    <ul className="space-y-1">
                        {data.contributing_factors.map((f: string, i: number) => (
                            <li key={i} className="text-xs text-slate-500 flex items-start gap-1.5">
                                <span className="text-amber-500 mt-0.5">•</span> {f}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Plain English Summary */}
            {data.plain_english && (
                <div className="mt-4 pt-3 border-t border-slate-700/50">
                    <p className="text-xs text-slate-300 leading-relaxed">{data.plain_english}</p>
                </div>
            )}
        </div>
    );
}

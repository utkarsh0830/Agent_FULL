"use client";

/* eslint-disable @typescript-eslint/no-explicit-any */

interface Props {
    data: any | null;
}

export default function TagRecommendations({ data }: Props) {
    if (!data) {
        return (
            <div className="glass-panel p-5">
                <div className="flex items-center gap-2 mb-3">
                    <span className="text-lg">🏷️</span>
                    <h2 className="text-sm font-semibold text-slate-300">Tag Recommendations</h2>
                </div>
                <div className="text-slate-500 text-sm">Run analysis to see results...</div>
            </div>
        );
    }

    if (data.error) {
        return (
            <div className="glass-panel p-5">
                <div className="flex items-center gap-2 mb-3">
                    <span className="text-lg">🏷️</span>
                    <h2 className="text-sm font-semibold text-slate-300">Tag Recommendations</h2>
                </div>
                <div className="text-red-400 text-sm">Error: {data.error}</div>
            </div>
        );
    }

    return (
        <div className="glass-panel p-5">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <span className="text-lg">🏷️</span>
                    <h2 className="text-sm font-semibold text-slate-300">Tag Recommendations</h2>
                </div>
                <div className="flex items-center gap-3 text-xs">
                    <span className="text-slate-500">
                        Untagged: <span className="text-amber-400 font-medium">{data.total_untagged || 0}</span>
                    </span>
                    {data.coverage_before != null && (
                        <span className="text-slate-500">
                            Coverage: <span className="text-slate-400">{data.coverage_before}%</span>
                            <span className="text-slate-600 mx-1">→</span>
                            <span className="text-emerald-400 font-medium">{data.coverage_after}%</span>
                        </span>
                    )}
                </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
                <table className="w-full text-xs">
                    <thead>
                        <tr className="border-b border-slate-700/50">
                            <th className="text-left py-2 px-2 text-slate-500 font-medium">Resource</th>
                            <th className="text-left py-2 px-2 text-slate-500 font-medium">Service</th>
                            <th className="text-left py-2 px-2 text-slate-500 font-medium">Suggested Tags</th>
                            <th className="text-right py-2 px-2 text-slate-500 font-medium">Confidence</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(data.suggestions || []).map((s: any, idx: number) => (
                            <tr key={idx} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                                <td className="py-2.5 px-2">
                                    <div className="text-slate-300 font-medium">{s.resource_name || s.resource_id}</div>
                                    <div className="text-slate-600 text-[10px] font-mono">{s.resource_id}</div>
                                </td>
                                <td className="py-2.5 px-2 text-slate-400">{s.service}</td>
                                <td className="py-2.5 px-2">
                                    <div className="flex flex-wrap gap-1">
                                        {Object.entries(s.suggested_tags || {}).map(([k, v]) => (
                                            <span
                                                key={k}
                                                className="inline-flex items-center px-1.5 py-0.5 rounded bg-indigo-900/30 border border-indigo-700/30 text-indigo-300"
                                            >
                                                <span className="text-indigo-500">{k}:</span>
                                                <span className="ml-0.5">{String(v)}</span>
                                            </span>
                                        ))}
                                    </div>
                                </td>
                                <td className="py-2.5 px-2 text-right">
                                    <span className={`font-medium ${(s.confidence || 0) > 0.8 ? "text-emerald-400" : (s.confidence || 0) > 0.5 ? "text-amber-400" : "text-rose-400"}`}>
                                        {((s.confidence || 0) * 100).toFixed(0)}%
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {data.plain_english && (
                <div className="mt-4 pt-3 border-t border-slate-700/50">
                    <p className="text-xs text-slate-400">{data.plain_english}</p>
                </div>
            )}
        </div>
    );
}

"use client";

import {
    Line, XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer, Area, AreaChart,
} from "recharts";

/* eslint-disable @typescript-eslint/no-explicit-any */

interface Props {
    data: any | null;
}

export default function ForecastChart({ data }: Props) {
    if (!data) {
        return (
            <div className="glass-panel p-5">
                <div className="flex items-center gap-2 mb-3">
                    <span className="text-lg">📈</span>
                    <h2 className="text-sm font-semibold text-slate-300">Cost Forecast</h2>
                </div>
                <div className="text-slate-500 text-sm">Run analysis to see projections...</div>
            </div>
        );
    }

    if (data.error) {
        return (
            <div className="glass-panel p-5">
                <div className="flex items-center gap-2 mb-3">
                    <span className="text-lg">📈</span>
                    <h2 className="text-sm font-semibold text-slate-300">Cost Forecast</h2>
                </div>
                <div className="text-red-400 text-sm">Error: {data.error}</div>
            </div>
        );
    }

    // Build chart data from daily_forecast
    const chartData = (data.daily_forecast || []).map((d: any) => ({
        date: d.date?.slice(5) || "",  // MM-DD
        cost: d.projected_cost,
        lower: d.lower,
        upper: d.upper,
    }));

    const trendColor = data.trend === "increasing" ? "#f43f5e" : data.trend === "decreasing" ? "#10b981" : "#6366f1";

    return (
        <div className="glass-panel p-5">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <span className="text-lg">📈</span>
                    <h2 className="text-sm font-semibold text-slate-300">Cost Forecast</h2>
                </div>
                <div className="flex items-center gap-3 text-xs">
                    {data.trend && (
                        <span className="px-2 py-0.5 rounded-full" style={{ background: trendColor + "20", color: trendColor }}>
                            {data.trend === "increasing" ? "📈" : data.trend === "decreasing" ? "📉" : "➡️"} {data.trend}
                            {data.trend_pct_per_month ? ` (${data.trend_pct_per_month > 0 ? "+" : ""}${data.trend_pct_per_month}%/mo)` : ""}
                        </span>
                    )}
                </div>
            </div>

            {/* Key Metrics */}
            <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="bg-slate-800/40 rounded-xl p-3 text-center">
                    <div className="text-xs text-slate-500 mb-1">Current Rate</div>
                    <div className="text-lg font-bold text-slate-200">
                        ${(data.current_monthly_run_rate || 0).toLocaleString()}
                    </div>
                    <div className="text-[10px] text-slate-500">/month</div>
                </div>
                <div className="bg-slate-800/40 rounded-xl p-3 text-center">
                    <div className="text-xs text-slate-500 mb-1">Projected 30d</div>
                    <div className="text-lg font-bold gradient-text-danger">
                        ${(data.projected_30d_cost || 0).toLocaleString()}
                    </div>
                    <div className="text-[10px] text-slate-500">next 30 days</div>
                </div>
                <div className="bg-slate-800/40 rounded-xl p-3 text-center">
                    <div className="text-xs text-slate-500 mb-1">Confidence</div>
                    <div className="text-lg font-bold text-indigo-400">
                        {((data.confidence_level || 0.95) * 100).toFixed(0)}%
                    </div>
                    <div className="text-[10px] text-slate-500">
                        ${(data.confidence_interval?.lower || 0).toLocaleString()} - ${(data.confidence_interval?.upper || 0).toLocaleString()}
                    </div>
                </div>
            </div>

            {/* Chart */}
            {chartData.length > 0 ? (
                <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartData}>
                            <defs>
                                <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748b" }} />
                            <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickFormatter={(v) => `$${v}`} />
                            <Tooltip
                                contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "8px", fontSize: "12px" }}
                                labelStyle={{ color: "#94a3b8" }}
                            />
                            <Area type="monotone" dataKey="upper" stroke="transparent" fill="#6366f120" />
                            <Area type="monotone" dataKey="lower" stroke="transparent" fill="#0a0f1e" />
                            <Line type="monotone" dataKey="cost" stroke="#6366f1" strokeWidth={2} dot={false} />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            ) : (
                <div className="h-48 flex items-center justify-center text-slate-600 text-sm">
                    No forecast data available for chart
                </div>
            )}

            {/* Anomaly Warnings */}
            {data.anomaly_warnings?.length > 0 && (
                <div className="mt-3">
                    <p className="text-xs font-medium text-amber-400 mb-2">⚠️ Anomaly Warnings</p>
                    {data.anomaly_warnings.map((w: any, i: number) => (
                        <div key={i} className="text-xs text-slate-400 flex items-center gap-2 mb-1">
                            <span className="text-amber-500">{w.date}</span> — {w.reason}
                            <span className={`px-1 py-0.5 rounded text-[10px] ${w.risk === "high" ? "bg-red-900/30 text-red-400" : "bg-amber-900/30 text-amber-400"}`}>
                                {w.risk}
                            </span>
                        </div>
                    ))}
                </div>
            )}

            {data.plain_english && (
                <div className="mt-3 pt-3 border-t border-slate-700/50">
                    <p className="text-xs text-slate-400">{data.plain_english}</p>
                </div>
            )}
        </div>
    );
}

"use client";

import { useState } from "react";
import { api } from "@/lib/api";

interface Props {
    onLoaded: () => void;
}

export default function BillingUpload({ onLoaded }: Props) {
    const [bucket, setBucket] = useState("");
    const [key, setKey] = useState("");
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<{ status: string; records_loaded?: number } | null>(null);

    const handleUpload = async () => {
        setLoading(true);
        try {
            const res = await api.uploadBilling(bucket, key);
            setResult(res);
            if (res.status === "success") onLoaded();
        } catch (err) {
            setResult({ status: `Error: ${err}` });
        }
        setLoading(false);
    };

    return (
        <div className="glass-panel p-4 mb-4">
            <div className="flex items-center gap-2 mb-3">
                <span className="text-lg">📥</span>
                <h2 className="text-sm font-semibold text-slate-300">Billing Data Ingestion</h2>
            </div>
            <div className="flex flex-wrap items-end gap-3">
                <div className="flex-1 min-w-[200px]">
                    <label className="block text-xs text-slate-500 mb-1">S3 Bucket</label>
                    <input
                        type="text"
                        value={bucket}
                        onChange={(e) => setBucket(e.target.value)}
                        placeholder="finops-focus-data (leave blank for mock)"
                        className="w-full px-3 py-2 rounded-lg bg-slate-800/60 border border-slate-700 text-sm text-slate-200 placeholder-slate-500 focus:border-indigo-500 focus:outline-none transition-colors"
                    />
                </div>
                <div className="flex-1 min-w-[200px]">
                    <label className="block text-xs text-slate-500 mb-1">S3 Key</label>
                    <input
                        type="text"
                        value={key}
                        onChange={(e) => setKey(e.target.value)}
                        placeholder="focus-export/2026-02/data.json"
                        className="w-full px-3 py-2 rounded-lg bg-slate-800/60 border border-slate-700 text-sm text-slate-200 placeholder-slate-500 focus:border-indigo-500 focus:outline-none transition-colors"
                    />
                </div>
                <button
                    onClick={handleUpload}
                    disabled={loading}
                    className="px-5 py-2 rounded-lg bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-sm font-medium hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all shadow-lg shadow-indigo-500/20"
                >
                    {loading ? "Loading..." : "⚡ Load Data"}
                </button>
            </div>
            {result && (
                <div className={`mt-3 text-xs px-3 py-2 rounded-lg ${result.status === "success" ? "bg-emerald-900/30 text-emerald-400" : "bg-red-900/30 text-red-400"}`}>
                    {result.status === "success"
                        ? `✅ Loaded ${result.records_loaded} FOCUS records`
                        : `❌ ${result.status}`}
                </div>
            )}
        </div>
    );
}

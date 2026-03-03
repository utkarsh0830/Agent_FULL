"use client";

import { useState } from "react";
import BillingUpload from "@/components/BillingUpload";
import AgentStream from "@/components/AgentStream";
import RCAPanel from "@/components/RCAPanel";
import TagRecommendations from "@/components/TagRecommendations";
import ForecastChart from "@/components/ForecastChart";
import RemediationApproval from "@/components/RemediationApproval";

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function Home() {
  const [dataLoaded, setDataLoaded] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [agentEvents, setAgentEvents] = useState<any[]>([]);
  const [rcaOutput, setRcaOutput] = useState<any>(null);
  const [tagOutput, setTagOutput] = useState<any>(null);
  const [forecastOutput, setForecastOutput] = useState<any>(null);
  const [actionOutput, setActionOutput] = useState<any>(null);

  const handleAnalysisEvent = (event: any) => {
    setAgentEvents((prev) => [...prev, event]);
    if (event.type === "rca_output") setRcaOutput(event.data);
    if (event.type === "tag_output") setTagOutput(event.data);
    if (event.type === "forecast_output") setForecastOutput(event.data);
    if (event.type === "action_output") setActionOutput(event.data);
  };

  return (
    <div className="min-h-screen p-4 md:p-6 max-w-[1600px] mx-auto">
      {/* Header */}
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <span className="text-3xl">🧠</span>
            <span className="gradient-text">FinOps AI Command Center</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            AI-powered orchestration over OpenCost · Infracost · Cloud Custodian
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className={`h-2.5 w-2.5 rounded-full ${dataLoaded ? "bg-emerald-400" : "bg-slate-600"}`} />
          <span className="text-xs text-slate-400">
            {dataLoaded ? "Data Loaded" : "No Data"}
          </span>
        </div>
      </header>

      {/* Billing Upload */}
      <BillingUpload onLoaded={() => setDataLoaded(true)} />

      {/* Agent Pipeline */}
      <AgentStream
        events={agentEvents}
        isRunning={isRunning}
        dataLoaded={dataLoaded}
        onStart={() => {
          setIsRunning(true);
          setAgentEvents([]);
          setRcaOutput(null);
          setTagOutput(null);
          setForecastOutput(null);
          setActionOutput(null);
        }}
        onEvent={handleAnalysisEvent}
        onComplete={() => setIsRunning(false)}
        onError={() => setIsRunning(false)}
      />

      {/* Results Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        {/* RCA Panel */}
        <RCAPanel data={rcaOutput} />

        {/* Forecast Chart */}
        <ForecastChart data={forecastOutput} />

        {/* Tag Recommendations — full width */}
        <div className="lg:col-span-2">
          <TagRecommendations data={tagOutput} />
        </div>

        {/* Remediation Actions — full width */}
        <div className="lg:col-span-2">
          <RemediationApproval data={actionOutput} />
        </div>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Pipeline = {
  pipeline_id: string;
  name: string;
  version: number;
  status: string;
  average_eval_score: number | null;
};

const sampleSparkline = [42, 48, 45, 58, 61, 67, 72];

export default function PipelinesPage() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [analytics, setAnalytics] = useState<Pipeline | null>(null);
  const [name, setName] = useState("");
  const [jsonConfig, setJsonConfig] = useState('{\n  "retrieval": {\n    "top_k": 10\n  }\n}');
  const [jsonError, setJsonError] = useState("");

  async function loadPipelines() {
    try {
      const response = await api.get("/pipelines");
      setPipelines(response.data);
    } catch (error) {
      console.error("Failed to load pipelines:", error);
    }
  }

  useEffect(() => {
    loadPipelines();
  }, []);

  function validateJson(value: string) {
    setJsonConfig(value);
    try {
      JSON.parse(value);
      setJsonError("");
    } catch {
      setJsonError("Invalid JSON configuration.");
    }
  }

  async function createPipeline() {
    if (!name.trim() || jsonError) return;

    try {
      await api.post("/pipelines", {
        name,
        config: JSON.parse(jsonConfig),
      });

      setName("");
      setShowCreate(false);
      await loadPipelines();
    } catch (error) {
      console.error("Failed to create pipeline:", error);
    }
  }

  function scoreClass(score: number | null) {
    if (score === null) return "text-slate-400";
    if (score >= 0.8) return "text-green-400";
    if (score >= 0.6) return "text-yellow-400";
    return "text-red-400";
  }

  return (
    <main className="min-h-screen bg-slate-950 p-8 text-white">
      <div className="mx-auto max-w-6xl">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Pipeline Manager</h1>
            <p className="mt-2 text-slate-400">
              Monitor, create, and analyze your RAG pipelines.
            </p>
          </div>

          <button
            onClick={() => setShowCreate(true)}
            className="rounded-lg bg-blue-600 px-5 py-3 font-semibold hover:bg-blue-500"
          >
            + Create Pipeline
          </button>
        </div>

        <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {pipelines.map((pipeline) => {
            const score = pipeline.average_eval_score;

            return (
              <div
                key={pipeline.pipeline_id}
                className="rounded-xl border border-slate-800 bg-slate-900 p-5"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-lg font-semibold">{pipeline.name}</h2>
                    <p className="text-sm text-slate-500">
                      Version {pipeline.version}
                    </p>
                  </div>

                  <span className="rounded-full bg-green-500/10 px-2 py-1 text-xs text-green-400">
                    {pipeline.status}
                  </span>
                </div>

                <div className="mt-6">
                  <p className="text-xs uppercase tracking-wide text-slate-500">
                    Average evaluation
                  </p>
                  <p className={`mt-1 text-3xl font-bold ${scoreClass(score)}`}>
                    {score === null ? "—" : score.toFixed(2)}
                  </p>
                </div>

                <div className="mt-5">
                  <p className="text-xs uppercase tracking-wide text-slate-500">
                    Queries · 7 days
                  </p>
                  <p className="mt-1 text-xl font-semibold">
                    {Math.floor(Math.random() * 80) + 20}
                  </p>
                </div>

                <div className="mt-5">
                  <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">
                    Daily score
                  </p>
                  <div className="flex h-12 items-end gap-1">
                    {sampleSparkline.map((value, index) => (
                      <div
                        key={index}
                        className="flex-1 rounded-t bg-blue-500/60"
                        style={{ height: `${value}%` }}
                      />
                    ))}
                  </div>
                </div>

                <button
                  onClick={() => setAnalytics(pipeline)}
                  className="mt-5 w-full rounded-lg border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800"
                >
                  View Analytics
                </button>
              </div>
            );
          })}

          {pipelines.length === 0 && (
            <div className="rounded-xl border border-dashed border-slate-700 p-8 text-slate-400">
              No pipelines found.
            </div>
          )}
        </div>

        {showCreate && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6">
            <div className="w-full max-w-2xl rounded-xl border border-slate-700 bg-slate-900 p-6">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Create Pipeline</h2>
                <button
                  onClick={() => setShowCreate(false)}
                  className="text-slate-400 hover:text-white"
                >
                  ✕
                </button>
              </div>

              <label className="mt-5 block text-sm text-slate-400">
                Pipeline name
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My RAG Pipeline"
                className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 p-3 outline-none focus:border-blue-500"
              />

              <label className="mt-5 block text-sm text-slate-400">
                JSON configuration
              </label>
              <textarea
                value={jsonConfig}
                onChange={(e) => validateJson(e.target.value)}
                rows={10}
                className={`mt-2 w-full rounded-lg border bg-slate-950 p-4 font-mono text-sm outline-none ${
                  jsonError ? "border-red-500" : "border-slate-700"
                }`}
              />

              {jsonError && (
                <p className="mt-2 text-sm text-red-400">{jsonError}</p>
              )}

              <div className="mt-5 flex justify-end gap-3">
                <button
                  onClick={() => setShowCreate(false)}
                  className="rounded-lg border border-slate-700 px-4 py-2"
                >
                  Cancel
                </button>
                <button
                  onClick={createPipeline}
                  disabled={!name.trim() || !!jsonError}
                  className="rounded-lg bg-blue-600 px-5 py-2 font-semibold disabled:opacity-50"
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        )}

        {analytics && (
          <div className="fixed inset-y-0 right-0 z-40 w-full max-w-lg border-l border-slate-700 bg-slate-900 p-6 shadow-2xl">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold">{analytics.name}</h2>
                <p className="text-sm text-slate-500">Analytics</p>
              </div>
              <button
                onClick={() => setAnalytics(null)}
                className="rounded-lg border border-slate-700 px-3 py-2"
              >
                Close
              </button>
            </div>

            <div className="mt-8 space-y-6">
              <div>
                <h3 className="font-medium">Latency</h3>
                <div className="mt-3 flex h-40 items-end gap-3">
                  {[45, 70, 55, 85, 60, 75].map((value, index) => (
                    <div key={index} className="flex-1">
                      <div
                        className="rounded-t bg-blue-500/70"
                        style={{ height: `${value}%` }}
                      />
                      <p className="mt-2 text-center text-xs text-slate-500">
                        P{index + 1}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-lg border border-slate-800 p-4">
                <h3 className="font-medium">Cost trend</h3>
                <div className="mt-4 h-2 rounded-full bg-slate-800">
                  <div className="h-2 w-2/3 rounded-full bg-blue-500" />
                </div>
                <p className="mt-2 text-sm text-slate-400">
                  Estimated usage cost trend
                </p>
              </div>

              <div className="rounded-lg border border-slate-800 p-4">
                <h3 className="font-medium">Evaluation radar</h3>
                <div className="mx-auto mt-5 grid h-40 w-40 place-items-center rounded-full border-4 border-blue-500/40">
                  <div className="text-center">
                    <div className="text-2xl font-bold">
                      {analytics.average_eval_score === null
                        ? "—"
                        : analytics.average_eval_score.toFixed(2)}
                    </div>
                    <div className="text-xs text-slate-500">Overall</div>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4">
                <h3 className="font-medium text-red-300">Failed runs</h3>
                <p className="mt-2 text-2xl font-bold">0</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

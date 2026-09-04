"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSSEStream } from "@/hooks";

type Pipeline = {
  pipeline_id: string;
  name: string;
  version: number;
  status: string;
  average_eval_score: number | null;
};

type Score = {
  faithfulness: number;
  relevance: number;
  completeness: number;
  citation_accuracy: number;
};

function Gauge({ label, value }: { label: string; value: number | null }) {
  const score = value ?? 0;

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
      <div className="mb-2 flex justify-between text-sm">
        <span className="text-slate-400">{label}</span>
        <span className="font-semibold text-white">
          {value === null ? "Pending" : `${Math.round(score * 100)}%`}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full rounded-full bg-blue-500 transition-all duration-700"
          style={{ width: `${Math.min(100, Math.max(0, score * 100))}%` }}
        />
      </div>
    </div>
  );
}

function ResponseCard({
  title,
  tokens,
  sources,
  citations,
  done,
  error,
  onCitation,
  runId,
  rating,
  setRating,
  scores,
}: {
  title: string;
  tokens: string;
  sources: Record<string, unknown>[];
  citations: Record<string, unknown>[];
  done: boolean;
  error: string | null;
  onCitation: (citation: Record<string, unknown>) => void;
  runId: string | null;
  rating: number | null;
  setRating: (rating: number) => void;
  scores: Score;
}) {
  async function rate(value: number) {
    if (!runId) return;
    await api.patch(`/runs/${runId}/rating`, { rating: value });
    setRating(value);
  }

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
      <h2 className="text-lg font-semibold">{title}</h2>

      {sources.length > 0 && (
        <div className="mt-4 rounded-lg border border-slate-700 bg-slate-950 p-4">
          <h3 className="font-medium">Retrieved Sources</h3>
          <div className="mt-3 space-y-2">
            {sources.map((source, index) => (
              <div
                key={index}
                className="rounded-md border border-slate-800 p-3 text-sm text-slate-300"
              >
                <div className="font-medium">
                  {String(
                    source.title ??
                      source.document_name ??
                      `Source ${index + 1}`
                  )}
                </div>
                {source.relevance_score !== undefined && (
                  <div className="mt-1 text-xs text-slate-500">
                    Relevance: {String(source.relevance_score)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-5 min-h-32 rounded-lg border border-slate-800 bg-slate-950 p-4">
        <p className="whitespace-pre-wrap text-slate-300">
          {tokens || "Waiting for response..."}
        </p>
      </div>

      {citations.length > 0 && (
        <div className="mt-5">
          <h3 className="text-sm font-medium text-slate-300">Citations</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {citations.map((citation, index) => (
              <button
                key={index}
                onClick={() => onCitation(citation)}
                className="rounded-full border border-blue-500/40 bg-blue-500/10 px-3 py-1 text-sm text-blue-300 hover:bg-blue-500/20"
              >
                {String(citation.reference ?? `Source ${index + 1}`)}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && <p className="mt-4 text-sm text-red-400">{error}</p>}

      {done && (
        <div className="mt-5">
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-400">Rate response:</span>
            <button
              onClick={() => rate(5)}
              className={`rounded-lg border px-3 py-2 ${
                rating === 5
                  ? "border-green-500 bg-green-500/20"
                  : "border-slate-700 hover:bg-slate-800"
              }`}
            >
              👍
            </button>
            <button
              onClick={() => rate(1)}
              className={`rounded-lg border px-3 py-2 ${
                rating === 1
                  ? "border-red-500 bg-red-500/20"
                  : "border-slate-700 hover:bg-slate-800"
              }`}
            >
              👎
            </button>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <Gauge label="Faithfulness" value={scores.faithfulness} />
            <Gauge label="Relevance" value={scores.relevance} />
            <Gauge label="Completeness" value={scores.completeness} />
            <Gauge
              label="Citation Accuracy"
              value={scores.citation_accuracy}
            />
          </div>
        </div>
      )}
    </section>
  );
}

export default function Playground() {
  const [query, setQuery] = useState("");
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [pipelineId, setPipelineId] = useState("");
  const [comparePipelineId, setComparePipelineId] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [compareRunId, setCompareRunId] = useState<string | null>(null);
  const [compare, setCompare] = useState(false);
  const [selectedCitation, setSelectedCitation] =
    useState<Record<string, unknown> | null>(null);
  const [rating, setRating] = useState<number | null>(null);
  const [compareRating, setCompareRating] = useState<number | null>(null);

  const primary = useSSEStream(runId);
  const secondary = useSSEStream(compareRunId);

  useEffect(() => {
    async function loadPipelines() {
      try {
        const response = await api.get("/pipelines");
        const active = response.data.filter(
          (pipeline: Pipeline) => pipeline.status === "active"
        );

        setPipelines(active);

        if (active.length > 0) {
          setPipelineId(active[0].pipeline_id);
        }

        if (active.length > 1) {
          setComparePipelineId(active[1].pipeline_id);
        }
      } catch (error) {
        console.error("Failed to load pipelines:", error);
      }
    }

    loadPipelines();
  }, []);

  async function runQuery() {
    if (!query.trim() || !pipelineId) return;

    setRunId(null);
    setCompareRunId(null);
    setRating(null);
    setCompareRating(null);

    const response = await api.post("/query", {
      query,
      pipeline_id: pipelineId,
      stream: true,
    });

    setRunId(response.data.run_id);

    if (compare && comparePipelineId) {
      const compareResponse = await api.post("/query", {
        query,
        pipeline_id: comparePipelineId,
        stream: true,
      });

      setCompareRunId(compareResponse.data.run_id);
    }
  }

  const defaultScores: Score = {
    faithfulness: null as unknown as number,
    relevance: null as unknown as number,
    completeness: null as unknown as number,
    citation_accuracy: null as unknown as number,
  };

  return (
    <main className="min-h-screen bg-slate-950 p-8 text-white">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-3xl font-bold">Query Playground</h1>
        <p className="mt-2 text-slate-400">
          Test your RAG pipelines and stream responses.
        </p>

        <div className="mt-8 space-y-4">
          <select
            value={pipelineId}
            onChange={(e) => setPipelineId(e.target.value)}
            className="w-full rounded-lg border border-slate-700 bg-slate-900 p-3"
          >
            {pipelines.length === 0 ? (
              <option value="">No active pipelines</option>
            ) : (
              pipelines.map((pipeline) => (
                <option key={pipeline.pipeline_id} value={pipeline.pipeline_id}>
                  {pipeline.name} —{" "}
                  {pipeline.average_eval_score !== null
                    ? `Score: ${pipeline.average_eval_score.toFixed(2)}`
                    : "No evaluation score"}
                </option>
              ))
            )}
          </select>

          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            maxLength={2000}
            rows={6}
            placeholder="Ask a question..."
            className="w-full rounded-lg border border-slate-700 bg-slate-900 p-4 outline-none focus:border-blue-500"
          />

          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={compare}
              onChange={(e) => setCompare(e.target.checked)}
            />
            <span>Compare mode</span>
            <span className="ml-auto text-sm text-slate-500">
              {query.length}/2000
            </span>
          </div>

          {compare && (
            <select
              value={comparePipelineId}
              onChange={(e) => setComparePipelineId(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 p-3"
            >
              <option value="">Select comparison pipeline</option>
              {pipelines
                .filter((pipeline) => pipeline.pipeline_id !== pipelineId)
                .map((pipeline) => (
                  <option key={pipeline.pipeline_id} value={pipeline.pipeline_id}>
                    {pipeline.name} —{" "}
                    {pipeline.average_eval_score !== null
                      ? `Score: ${pipeline.average_eval_score.toFixed(2)}`
                      : "No evaluation score"}
                  </option>
                ))}
            </select>
          )}

          <button
            onClick={runQuery}
            disabled={!query.trim() || !pipelineId}
            className="rounded-lg bg-blue-600 px-6 py-3 font-semibold hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Run Query
          </button>

          {(runId || compareRunId) && (
            <div
              className={`grid gap-6 ${
                compare ? "lg:grid-cols-2" : "grid-cols-1"
              }`}
            >
              <ResponseCard
                title="Primary Pipeline"
                tokens={primary.tokens}
                sources={primary.sources}
                citations={primary.citations}
                done={primary.done}
                error={primary.error}
                onCitation={setSelectedCitation}
                runId={runId}
                rating={rating}
                setRating={setRating}
                scores={defaultScores}
              />

              {compare && compareRunId && (
                <ResponseCard
                  title="Comparison Pipeline"
                  tokens={secondary.tokens}
                  sources={secondary.sources}
                  citations={secondary.citations}
                  done={secondary.done}
                  error={secondary.error}
                  onCitation={setSelectedCitation}
                  runId={compareRunId}
                  rating={compareRating}
                  setRating={setCompareRating}
                  scores={defaultScores}
                />
              )}
            </div>
          )}
        </div>

        {selectedCitation && (
          <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md border-l border-slate-700 bg-slate-900 p-6 shadow-2xl">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Citation Details</h2>
              <button
                onClick={() => setSelectedCitation(null)}
                className="rounded-md border border-slate-700 px-3 py-1 text-slate-300 hover:bg-slate-800"
              >
                Close
              </button>
            </div>

            <div className="mt-6 space-y-4 text-sm">
              <div>
                <span className="text-slate-500">Reference</span>
                <p className="text-white">
                  {String(selectedCitation.reference ?? "Citation")}
                </p>
              </div>
              <div>
                <span className="text-slate-500">Document</span>
                <p className="text-white">
                  {String(selectedCitation.document_name ?? "Unknown")}
                </p>
              </div>
              <div>
                <span className="text-slate-500">Page</span>
                <p className="text-white">
                  {String(selectedCitation.page_number ?? "N/A")}
                </p>
              </div>
              <div>
                <span className="text-slate-500">Chunk</span>
                <p className="text-white">
                  {String(selectedCitation.chunk_id ?? "N/A")}
                </p>
              </div>
              <div>
                <span className="text-slate-500">Content</span>
                <p className="mt-1 whitespace-pre-wrap text-slate-300">
                  {String(
                    selectedCitation.content_preview ??
                      selectedCitation.content ??
                      "No content available."
                  )}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

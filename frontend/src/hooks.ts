"use client";

import { useEffect, useState } from "react";

type Source = {
  [key: string]: unknown;
};

type Citation = {
  [key: string]: unknown;
};

export function useSSEStream(runId: string | null) {
  const [tokens, setTokens] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;

    const controller = new AbortController();

    setTokens("");
    setSources([]);
    setCitations([]);
    setDone(false);
    setError(null);

    const stream = async () => {
      try {
        const response = await fetch(`/backend/query/${runId}/stream`, {
          signal: controller.signal,
          headers: {
            Accept: "text/event-stream",
          },
        });

        if (!response.ok || !response.body) {
          throw new Error(`SSE request failed (${response.status})`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done: readerDone } = await reader.read();

          if (readerDone) break;

          buffer += decoder.decode(value, { stream: true });

          const events = buffer.split("\n\n");
          buffer = events.pop() ?? "";

          for (const rawEvent of events) {
            const dataLine = rawEvent
              .split("\n")
              .find((line) => line.startsWith("data:"));

            if (!dataLine) continue;

            const data = JSON.parse(dataLine.slice(5).trim());

            if (data.type === "retrieval_complete") {
              setSources(data.sources ?? []);
            }

            if (data.type === "token") {
              setTokens((current) => current + (data.delta ?? ""));
            }

            if (data.type === "done") {
              setCitations(data.citations ?? []);
              setDone(true);
              return;
            }

            if (data.type === "error") {
              setError(data.message ?? "Generation failed.");
              return;
            }
          }
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(
            err instanceof Error ? err.message : "SSE connection failed."
          );
        }
      }
    };

    void stream();

    return () => controller.abort();
  }, [runId]);

  return {
    tokens,
    sources,
    citations,
    done,
    error,
  };
}

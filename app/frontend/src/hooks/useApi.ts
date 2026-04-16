import { useState, useEffect, useCallback, useContext } from "react";
import { RegionContext } from "../context/RegionContext";

interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useApi<T>(url: string, params?: Record<string, string>): UseApiResult<T> {
  const { market } = useContext(RegionContext);
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const merged = { market, ...(params ?? {}) };
      const queryString = "?" + new URLSearchParams(
        Object.entries(merged).filter(([, v]) => v)
      ).toString();
      const resp = await fetch(`${url}${queryString}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json = await resp.json();
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [url, market, JSON.stringify(params)]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

export async function postChat(
  message: string,
  market: string = "AU"
): Promise<{ response: string; intent: string | null }> {
  const resp = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, market }),
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

import { useEffect, useState } from "react";

// Vite injects the configured `base` (vite.config.js) here at runtime,
// e.g. "/absproxy/5173/" in dev behind this proxy, "/" in a production build.
const BASE = import.meta.env.BASE_URL;

// Exported (not just used internally) so any other file that needs to link
// to something under public/ — not just JSON fetched by this hook — resolves
// it the same way. FieldContent.jsx uses this for the "Open original" links
// to public/raw/<file_name>, so those links keep working through the same
// dev-server proxy path as everything else instead of drifting out of sync.
export function resolvePath(path) {
  return BASE.replace(/\/$/, "") + "/" + String(path).replace(/^\//, "");
}

/**
 * Fetches a JSON file from /public/data/<name> at runtime (not bundled),
 * so swapping in a real file (copied from evaluation/*.json on the server)
 * just means replacing the file in public/data/ — no rebuild needed in dev,
 * a plain `npm run build` picks it up for the built version.
 *
 * Returns { data, loading, error } — `error` is set (not thrown) when a
 * model's file doesn't exist yet (e.g. Model B/C not benchmarked yet by
 * teammates), so pages can render "not available yet" instead of crashing.
 */
export function useJsonData(path) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });

    const url = resolvePath(path);

    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null });
      })
      .catch((error) => {
        if (!cancelled) setState({ data: null, loading: false, error });
      });

    return () => {
      cancelled = true;
    };
  }, [path]);

  return state;
}
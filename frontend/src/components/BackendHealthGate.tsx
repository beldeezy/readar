import { useEffect, useState } from "react";
import { getApiBaseUrlDebug } from "../api/client";

type Status = "checking" | "ok" | "down";

export default function BackendHealthGate() {
  const [status, setStatus] = useState<Status>("checking");
  const [detail, setDetail] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const { API_BASE_URL } = getApiBaseUrlDebug();
        // API_BASE_URL includes /api; health is at root, so strip trailing /api
        const base = API_BASE_URL.replace(/\/api\/?$/, "");
        const url = `${base}/health`;

        const res = await fetch(url, { method: "GET" });
        if (!res.ok) throw new Error(`Health check failed (status ${res.status})`);

        if (!cancelled) setStatus("ok");
      } catch (e: any) {
        if (!cancelled) {
          setStatus("down");
          setDetail(e?.message || "Backend health check failed");
        }
      }
    }

    check();
    return () => {
      cancelled = true;
    };
  }, []);

  if (status === "ok" || status === "checking") return null;

  // status === "down"
  return (
    <div
      style={{
        position: "fixed",
        left: 16,
        bottom: 16,
        zIndex: 9999,
        padding: "10px 12px",
        borderRadius: 12,
        border: "1px solid rgba(255,255,255,0.15)",
        background: "rgba(10,10,10,0.85)",
        color: "rgba(255,255,255,0.9)",
        maxWidth: 420,
        boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
        fontSize: 13,
        lineHeight: 1.35,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 4 }}>Backend unreachable</div>
      <div style={{ opacity: 0.85 }}>{detail}</div>
      <div style={{ opacity: 0.65, marginTop: 6 }}>
        Check FastAPI is running on port 8000 and VITE_API_BASE_URL is correct.
      </div>
    </div>
  );
}


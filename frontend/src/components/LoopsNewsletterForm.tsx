import { useMemo, useState } from "react";
import "./LoopsNewsletterForm.css";

type Phase = "idle" | "loading" | "success" | "error" | "rate_limited";

const LOOPS_ACTION_URL =
  "https://app.loops.so/api/newsletter-form/clysy73uf000cte404zm6g98o";

export default function LoopsNewsletterForm({ ctaLabel = "Subscribe" }: { ctaLabel?: string }) {
  const [email, setEmail] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [errorMsg, setErrorMsg] = useState("Oops! Something went wrong, please try again");

  const waitMs = useMemo(() => 60000, []);

  const reset = () => {
    setPhase("idle");
    setErrorMsg("Oops! Something went wrong, please try again");
    setEmail("");
  };

  const rateLimit = () => {
    setPhase("rate_limited");
    setErrorMsg("Too many signups, please try again in a little while");
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // localStorage rate limit (same logic as Loops snippet)
    const now = Date.now();
    const prev = localStorage.getItem("loops-form-timestamp");
    if (prev && Number(prev) + waitMs > now) {
      rateLimit();
      return;
    }
    localStorage.setItem("loops-form-timestamp", String(now));

    setPhase("loading");

    const body = `userGroup=&mailingLists=&email=${encodeURIComponent(email)}`;

    try {
      const res = await fetch(LOOPS_ACTION_URL, {
        method: "POST",
        body,
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });

      if (res.ok) {
        setPhase("success");
        return;
      }

      // attempt to parse JSON error
      let msg = res.statusText;
      try {
        const data = await res.json();
        if (data?.message) msg = data.message;
      } catch {}
      setErrorMsg(msg || "Oops! Something went wrong, please try again");
      setPhase("error");
      localStorage.setItem("loops-form-timestamp", "");
    } catch (err: any) {
      // Loops snippet treats Failed to fetch as rate limit / cloudflare
      if (err?.message === "Failed to fetch") {
        rateLimit();
        return;
      }
      setErrorMsg(err?.message || "Oops! Something went wrong, please try again");
      setPhase("error");
      localStorage.setItem("loops-form-timestamp", "");
    }
  };

  return (
    <div className="loops-newsletter">
      {(phase === "idle" || phase === "loading") && (
        <form className="loops-form" onSubmit={onSubmit}>
          <input
            className="loops-input"
            placeholder="you@example.com"
            required
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={phase === "loading"}
          />

          <button
            type="submit"
            className="loops-cta"
            disabled={phase === "loading"}
          >
            {phase === "loading" ? "Please wait..." : ctaLabel}
          </button>
        </form>
      )}

      {phase === "success" && (
        <div className="loops-newsletter-state">
          <p className="loops-newsletter-success">
            Appreciate your attention, we&apos;ll be in touch.
          </p>
          <button type="button" className="loops-newsletter-back" onClick={reset}>
            ← Back
          </button>
        </div>
      )}

      {(phase === "error" || phase === "rate_limited") && (
        <div className="loops-newsletter-state">
          <p className="loops-newsletter-error">{errorMsg}</p>
          <button type="button" className="loops-newsletter-back" onClick={reset}>
            ← Back
          </button>
        </div>
      )}
    </div>
  );
}


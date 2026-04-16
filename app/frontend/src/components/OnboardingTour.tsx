import { useState, useEffect } from "react";

const TOUR_KEY = "compliance_onboarding_complete";

const STEPS = [
  {
    title: "Compliance Risk at a Glance",
    body: "The Risk Heatmap scores every regulator × obligation category. Green is compliant, amber needs attention, red is critical. Click any cell for detail.",
    anchor: "risk",
  },
  {
    title: "Ask Anything — AI Compliance Copilot",
    body: "The chat panel on the right is powered by Claude Sonnet 4.5. Ask about emissions, enforcement history, obligations, or Safeguard exposure. It queries live Delta tables.",
    anchor: "chat",
  },
  {
    title: "Seven Views, One Platform",
    body: "Explore Enforcement Tracker, Obligation Register, Emissions Overview, Safeguard Forecast, Market Notices, and Compliance Insights — all from the tab bar above.",
    anchor: "tabs",
  },
];

interface Props {
  onComplete: () => void;
}

export default function OnboardingTour({ onComplete }: Props) {
  const [step, setStep] = useState(0);

  const next = () => {
    if (step < STEPS.length - 1) {
      setStep(step + 1);
    } else {
      finish();
    }
  };

  const finish = () => {
    localStorage.setItem(TOUR_KEY, "1");
    onComplete();
  };

  const current = STEPS[step];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Platform onboarding tour"
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,0.65)", backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
    >
      <div style={{
        background: "var(--bg-card-solid)", border: "1px solid var(--border-accent)",
        borderRadius: 14, padding: 32, maxWidth: 440, width: "90%",
        boxShadow: "0 24px 64px rgba(0,0,0,0.5)",
      }}>
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 8, letterSpacing: 1 }}>
          STEP {step + 1} OF {STEPS.length}
        </div>
        <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 10, color: "var(--text-primary)" }}>
          {current.title}
        </h2>
        <p style={{ fontSize: 14, color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: 24 }}>
          {current.body}
        </p>

        {/* Progress dots */}
        <div style={{ display: "flex", gap: 6, marginBottom: 24 }}>
          {STEPS.map((_, i) => (
            <div key={i} style={{
              width: i === step ? 20 : 6, height: 6, borderRadius: 3, transition: "width 0.2s",
              background: i === step ? "var(--accent-blue)" : "var(--border-accent)",
            }} />
          ))}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <button
            onClick={finish}
            style={{ fontSize: 12, color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer" }}
          >
            Skip tour
          </button>
          <button
            onClick={next}
            style={{
              padding: "8px 24px", fontSize: 13, fontWeight: 600,
              background: "var(--gradient-blue)", color: "#fff",
              border: "none", borderRadius: 8, cursor: "pointer",
            }}
          >
            {step < STEPS.length - 1 ? "Next →" : "Get started →"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function useOnboarding() {
  const [showTour, setShowTour] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(TOUR_KEY)) {
      // Small delay so the app renders first
      const t = setTimeout(() => setShowTour(true), 800);
      return () => clearTimeout(t);
    }
  }, []);

  const resetTour = () => {
    localStorage.removeItem(TOUR_KEY);
    setShowTour(true);
  };

  return { showTour, closeTour: () => setShowTour(false), resetTour };
}

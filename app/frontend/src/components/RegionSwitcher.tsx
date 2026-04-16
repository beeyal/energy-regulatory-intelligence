import { useState, useRef, useEffect } from "react";
import { useRegion } from "../context/RegionContext";

export default function RegionSwitcher() {
  const { market, setMarket, markets, activeMarket } = useRegion();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Always render — show default AU flag while markets are loading
  const displayFlag = activeMarket?.flag ?? "🇦🇺";
  const displayCode = market ?? "AU";

  return (
    <div className="region-switcher" ref={ref}>
      <button
        className="region-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="region-flag">{displayFlag}</span>
        <span className="region-code">{displayCode}</span>
        <span className="region-chevron">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="region-dropdown" role="listbox">
          {markets.map((m) => {
            const isActive = m.code === market;
            const hasData = m.data_available === "true";
            return (
              <button
                key={m.code}
                role="option"
                aria-selected={isActive}
                className={`region-option ${isActive ? "active" : ""}`}
                onClick={() => { setMarket(m.code); setOpen(false); }}
              >
                <span className="region-flag">{m.flag}</span>
                <span className="region-option-text">
                  <span className="region-option-name">{m.name}</span>
                  <span className="region-option-market">{m.market_name}</span>
                </span>
                {!hasData && (
                  <span className="region-preview-badge">Preview</span>
                )}
                {isActive && <span className="region-check">✓</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { useRegion } from "../context/RegionContext";

export default function RegionSwitcher() {
  const { market, setMarket, markets, activeMarket } = useRegion();
  const [open, setOpen] = useState(false);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Position the portal dropdown below the trigger button
  useEffect(() => {
    if (!open || !triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    setDropdownStyle({
      position: "fixed",
      top: rect.bottom + 6,
      right: window.innerWidth - rect.right,
    });
  }, [open]);

  // Close on outside click — must exclude both trigger AND portal dropdown
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      const target = e.target as Node;
      const inTrigger = triggerRef.current?.contains(target);
      const inDropdown = dropdownRef.current?.contains(target);
      if (!inTrigger && !inDropdown) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const displayFlag = activeMarket?.flag ?? "🇦🇺";
  const displayCode = market ?? "AU";

  return (
    <div className="region-switcher">
      <button
        ref={triggerRef}
        className="region-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="region-flag">{displayFlag}</span>
        <span className="region-code">{displayCode}</span>
        <span className="region-chevron">{open ? "▲" : "▼"}</span>
      </button>

      {open && createPortal(
        <div className="region-dropdown" role="listbox" style={dropdownStyle} ref={dropdownRef}>
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
        </div>,
        document.body
      )}
    </div>
  );
}

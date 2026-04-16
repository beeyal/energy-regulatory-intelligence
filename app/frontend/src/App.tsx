import { useState, useEffect } from "react";
import RiskHeatMap from "./components/RiskHeatMap";
import EmissionsOverview from "./components/EmissionsOverview";
import EmissionsForecaster from "./components/EmissionsForecaster";
import MarketNotices from "./components/MarketNotices";
import EnforcementTracker from "./components/EnforcementTracker";
import ObligationRegister from "./components/ObligationRegister";
import ComplianceGaps from "./components/ComplianceGaps";
import ChatPanel from "./components/ChatPanel";
import OnboardingTour, { useOnboarding } from "./components/OnboardingTour";
import FreshnessBadge from "./components/FreshnessBadge";
import { useTheme } from "./hooks/useTheme";
import { RegionProvider, useRegion } from "./context/RegionContext";
import RegionSwitcher from "./components/RegionSwitcher";

type Tab = "risk" | "emissions" | "forecast" | "notices" | "enforcement" | "obligations" | "gaps";

interface Metadata {
  tables?: Record<string, string | number>;
  catalog?: string;
  last_ingested_at?: Record<string, string>;
}

const TABS: { id: Tab; label: string }[] = [
  { id: "risk", label: "Risk Overview" },
  { id: "gaps", label: "Compliance Insights" },
  { id: "emissions", label: "Emissions" },
  { id: "forecast", label: "Safeguard Forecast" },
  { id: "notices", label: "Market Notices" },
  { id: "enforcement", label: "Enforcement" },
  { id: "obligations", label: "Obligations" },
];

function TabContent({ tab }: { tab: Tab }) {
  switch (tab) {
    case "risk": return <RiskHeatMap />;
    case "emissions": return <EmissionsOverview />;
    case "forecast": return <EmissionsForecaster />;
    case "notices": return <MarketNotices />;
    case "enforcement": return <EnforcementTracker />;
    case "obligations": return <ObligationRegister />;
    case "gaps": return <ComplianceGaps />;
  }
}

function TabWrapper({ tab, metadata }: { tab: Tab; metadata: Metadata | null }) {
  const tableMap: Partial<Record<Tab, string>> = {
    enforcement: "enforcement_actions",
    obligations: "regulatory_obligations",
    emissions: "emissions_data",
    notices: "market_notices",
    gaps: "compliance_insights",
  };
  const tableKey = tableMap[tab];
  const ts = tableKey ? metadata?.last_ingested_at?.[tableKey] : undefined;

  return (
    <div style={{ position: "relative" }}>
      {ts && (
        <div style={{ position: "absolute", top: 0, right: 0, zIndex: 10 }}>
          <FreshnessBadge timestamp={ts} />
        </div>
      )}
      <TabContent tab={tab} />
    </div>
  );
}

export default function App() {
  return (
    <RegionProvider>
      <AppInner />
    </RegionProvider>
  );
}

function AppInner() {
  const [activeTab, setActiveTab] = useState<Tab>("risk");
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const { showTour, closeTour, resetTour } = useOnboarding();
  const { theme, toggleTheme } = useTheme();
  const { market, activeMarket } = useRegion();

  useEffect(() => {
    fetch(`/api/metadata?market=${market}`)
      .then((r) => r.ok ? r.json() : Promise.reject())
      .then((d) => setMetadata(d))
      .catch(() => {});
  }, [market]);

  return (
    <div className="app-container">
      <div className="app-header">
        <div className="header-actions">
          <RegionSwitcher />
          <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
            {theme === "dark" ? "☀ Light" : "◑ Dark"}
          </button>
          <button className="help-btn" onClick={resetTour} aria-label="Open help tour">
            ? Help
          </button>
        </div>

        <div className="header-logo-row">
          <div className="header-icon" aria-hidden="true">⚡</div>
          <div>
            <h1>Regulatory Intelligence Command Center</h1>
            <div className="subtitle">
              {activeMarket
                ? `${activeMarket.flag} ${activeMarket.name} — ${activeMarket.market_name}`
                : "AI-powered compliance monitoring — CER, AEMO, AER, AEMC"}
            </div>
          </div>
        </div>

        {metadata?.tables && (
          <div className="data-source-banner">
            <div className="stat-pill emissions">
              <span className="pill-value">{metadata.tables.emissions_data || 0}</span>
              <span className="pill-label">emissions</span>
            </div>
            <div className="stat-pill notices">
              <span className="pill-value">{metadata.tables.market_notices || 0}</span>
              <span className="pill-label">notices</span>
            </div>
            <div className="stat-pill enforcement">
              <span className="pill-value">{metadata.tables.enforcement_actions || 0}</span>
              <span className="pill-label">enforcement</span>
            </div>
            <div className="stat-pill obligations">
              <span className="pill-value">{metadata.tables.regulatory_obligations || 0}</span>
              <span className="pill-label">obligations</span>
            </div>
          </div>
        )}
      </div>

      {activeMarket && activeMarket.data_available === "false" && (
        <div className="preview-banner">
          <span>⚠ {activeMarket.name} data pipeline coming soon — the AI assistant is active and answers from regulatory knowledge</span>
        </div>
      )}

      <nav className="tab-nav">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="main-content">
        <div className="panel-area">
          <TabWrapper tab={activeTab} metadata={metadata} />
        </div>
        <div className="chat-area">
          <ChatPanel />
        </div>
      </div>

      {showTour && <OnboardingTour onComplete={closeTour} />}
    </div>
  );
}

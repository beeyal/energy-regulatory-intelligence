import { useState, useEffect } from "react";
import RiskHeatMap from "./components/RiskHeatMap";
import EmissionsOverview from "./components/EmissionsOverview";
import EmissionsForecaster from "./components/EmissionsForecaster";
import MarketNotices from "./components/MarketNotices";
import EnforcementTracker from "./components/EnforcementTracker";
import ObligationRegister from "./components/ObligationRegister";
import ComplianceGaps from "./components/ComplianceGaps";
import RegulatoryHorizon from "./components/RegulatoryHorizon";
import ChatPanel from "./components/ChatPanel";
import OnboardingTour, { useOnboarding } from "./components/OnboardingTour";
import FreshnessBadge from "./components/FreshnessBadge";
import MarketPosture from "./components/MarketPosture";
import ImpactAnalysis from "./components/ImpactAnalysis";
import ESGDisclosure from "./components/ESGDisclosure";
import PeerBenchmark from "./components/PeerBenchmark";
import NotificationBell from "./components/NotificationBell";
import { useTheme } from "./hooks/useTheme";
import { RegionProvider, useRegion } from "./context/RegionContext";
import RegionSwitcher from "./components/RegionSwitcher";

type Tab = "risk" | "horizon" | "emissions" | "forecast" | "notices" | "enforcement" | "obligations" | "gaps" | "markets" | "impact" | "esg" | "benchmark";

interface Metadata {
  tables?: Record<string, string | number>;
  catalog?: string;
  last_ingested_at?: Record<string, string>;
}

const TABS: { id: Tab; label: string; badge?: string }[] = [
  { id: "risk", label: "Risk Overview" },
  { id: "markets", label: "Markets", badge: "NEW" },
  { id: "horizon", label: "Horizon" },
  { id: "gaps", label: "Compliance Insights" },
  { id: "emissions", label: "Emissions" },
  { id: "forecast", label: "Safeguard Forecast" },
  { id: "notices", label: "Market Notices" },
  { id: "enforcement", label: "Enforcement" },
  { id: "obligations", label: "Obligations" },
  { id: "benchmark", label: "Benchmarking" },
  { id: "impact", label: "Impact Analysis", badge: "AI" },
  { id: "esg", label: "ESG Disclosure" },
];

function TabContent({ tab }: { tab: Tab }) {
  switch (tab) {
    case "risk": return <RiskHeatMap />;
    case "markets": return <MarketPosture />;
    case "horizon": return <RegulatoryHorizon />;
    case "emissions": return <EmissionsOverview />;
    case "forecast": return <EmissionsForecaster />;
    case "notices": return <MarketNotices />;
    case "enforcement": return <EnforcementTracker />;
    case "obligations": return <ObligationRegister />;
    case "gaps": return <ComplianceGaps />;
    case "benchmark": return <PeerBenchmark />;
    case "impact": return <ImpactAnalysis />;
    case "esg": return <ESGDisclosure />;
  }
}

function TabWrapper({ tab, metadata }: { tab: Tab; metadata: Metadata | null }) {
  const tableMap: Partial<Record<Tab, string>> = {
    enforcement: "enforcement_actions",
    obligations: "regulatory_obligations",
    emissions: "emissions_data",
    notices: "market_notices",
    gaps: "compliance_insights",
    esg: "emissions_data",
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
          <NotificationBell />
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
            style={{ position: "relative" }}
          >
            {tab.label}
            {tab.badge && (
              <span style={{
                position: "absolute", top: -4, right: -4,
                fontSize: 8, fontWeight: 800, padding: "1px 4px",
                background: "var(--accent-green)", color: "#000",
                borderRadius: 4, letterSpacing: "0.04em",
                lineHeight: 1.4,
              }}>
                {tab.badge}
              </span>
            )}
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

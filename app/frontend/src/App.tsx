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
  const [activeTab, setActiveTab] = useState<Tab>("risk");
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const { showTour, closeTour, resetTour } = useOnboarding();

  useEffect(() => {
    fetch("/api/metadata")
      .then((r) => r.ok ? r.json() : Promise.reject())
      .then((d) => setMetadata(d))
      .catch(() => {});
  }, []);

  return (
    <div className="app-container">
      <div className="app-header">
        <div>
          <h1>Regulatory Intelligence Command Center</h1>
          <div className="subtitle">AI-powered compliance monitoring — CER, AEMO, AER, AEMC</div>
          {metadata?.tables && (
            <div className="data-source-banner">
              <span>{metadata.tables.emissions_data || 0} emissions</span>
              <span className="dot" />
              <span>{metadata.tables.market_notices || 0} notices</span>
              <span className="dot" />
              <span>{metadata.tables.enforcement_actions || 0} enforcement</span>
              <span className="dot" />
              <span>{metadata.tables.regulatory_obligations || 0} obligations</span>
            </div>
          )}
          <button
            onClick={resetTour}
            style={{ fontSize: 11, color: "var(--text-muted)", background: "none", border: "1px solid var(--border)", borderRadius: 5, padding: "3px 10px", cursor: "pointer", marginTop: 6 }}
          >
            ? Help
          </button>
        </div>
      </div>

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

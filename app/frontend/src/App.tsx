import { useState } from "react";
import EmissionsOverview from "./components/EmissionsOverview";
import MarketNotices from "./components/MarketNotices";
import EnforcementTracker from "./components/EnforcementTracker";
import ObligationRegister from "./components/ObligationRegister";
import ComplianceGaps from "./components/ComplianceGaps";
import ChatPanel from "./components/ChatPanel";

type Tab = "emissions" | "notices" | "enforcement" | "obligations" | "gaps";

const TABS: { id: Tab; label: string }[] = [
  { id: "gaps", label: "Compliance Insights" },
  { id: "emissions", label: "Emissions" },
  { id: "notices", label: "Market Notices" },
  { id: "enforcement", label: "Enforcement" },
  { id: "obligations", label: "Obligations" },
];

function TabContent({ tab }: { tab: Tab }) {
  switch (tab) {
    case "emissions": return <EmissionsOverview />;
    case "notices": return <MarketNotices />;
    case "enforcement": return <EnforcementTracker />;
    case "obligations": return <ObligationRegister />;
    case "gaps": return <ComplianceGaps />;
  }
}

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("gaps");

  return (
    <div className="app-container">
      <div className="app-header">
        <div>
          <h1>Energy Compliance Intelligence Hub</h1>
          <div className="subtitle">Australian energy regulatory data — CER, AEMO, AER</div>
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
          <TabContent tab={activeTab} />
        </div>
        <div className="chat-area">
          <ChatPanel />
        </div>
      </div>
    </div>
  );
}

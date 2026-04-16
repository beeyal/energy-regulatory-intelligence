# Demo Script — Regulatory Intelligence Command Center

**Format:** 5-minute video pitch to CXO audience
**Scoring:** Reusability 30%, Business Impact, Executive Alignment, Technical Excellence, Cross-Region 5%, Localization 5%

---

## 0:00–0:25 | The Problem (set the stakes)

Open on a black screen or title card, then cut to talking head or voiceover.

*"Australian energy companies manage over 600 regulatory obligations across 8 regulators. They track them in spreadsheets. Their compliance teams spend two hours every morning scanning regulator websites. And when they miss something, the consequences are real."*

*"$54 million in AER enforcement penalties last year. $660,000 per day for a missed NGER deadline. Origin Energy paid $17 million for a single rebidding breach. AGL has been hit 5 times."*

*"Meanwhile, Safeguard Mechanism baselines are declining 4.9% per year. Every coal and gas generator is on a compliance cliff — and most of them can't even quantify the exposure."*

*"We built something that fixes this."*

**What judges hear:** Real problem, real dollars, real urgency. Not a toy.

---

## 0:25–1:15 | Risk Heat Map (the hero visual)

Open the app. The Risk Heat Map is the landing page.

*"This is the Regulatory Intelligence Command Center. What you're looking at is a live compliance risk assessment across 5 Australian regulators and 6 obligation categories — 30 risk cells, each scored from the data sitting in Unity Catalog."*

**Click on a red cell** (CER x Environmental — score 100).

*"CER Environmental is critical — that's Safeguard Mechanism and NGER reporting. 12 obligations, $5 million exposure. The score isn't hardcoded — it's computed from obligation severity, enforcement activity, and financial exposure in our Delta tables."*

**Point out the summary stats** at the top.

*"80 total obligations tracked. 7 critical risk cells. The CRO opens this every morning and knows exactly where to focus."*

**What judges score:**
- Business impact — CRO use case, quantified risk
- Technical excellence — Unity Catalog, SQL Warehouse, Delta Lake powering live aggregation

---

## 1:15–2:00 | Board Briefing Generator (the CXO moment)

**Click "Generate Board Briefing"** on the Risk Heat Map.

*"Every quarter, the compliance team spends three weeks assembling a Board Risk Committee paper. Let me show you what replaces that."*

The modal opens with real data populating.

*"This is generated from live data — not a template. Risk distribution: 27 critical, 40 high. $10.5 million in penalties across 16 companies. The 5 most recent enforcement actions. The 10 highest-risk obligations. Top emitters by Scope 1. Repeat offenders."*

**Scroll to Recommended Actions.**

*"And it generates prioritised recommendations — P1: address Safeguard exposure at Loy Yang B, P2: audit hardship program compliance, P3: review NGER reporting automation."*

**Click "Copy to Clipboard".**

*"Three weeks to three minutes. Copy, paste into your board paper, done."*

**What judges score:**
- Executive alignment — Board Risk Committee is the audience. Every CFO and CRO understands this.
- Business impact — quantifiable time savings (3 weeks x 4 quarters = 12 weeks/year of senior compliance team time)
- Technical excellence — FMAPI + Unity Catalog + 5 Delta tables aggregated in one view

---

## 2:00–2:50 | AI Copilot with Streaming + UC Functions (the wow)

**Click into the chat sidebar.** It's always visible.

*"The AI Copilot answers any compliance question using real data. Watch."*

**Type:** *"What enforcement actions has AGL faced?"*

Show the streaming response appearing word by word.

*"That's Claude Sonnet 4.5 via the Foundation Model API, streaming over Server-Sent Events. It classified the intent as 'enforcement', queried the Delta table, injected the results as context, and generated a cited answer. Every interaction is traced in MLflow."*

**Now type:** *"What is AGL's Safeguard exposure if they reduce emissions 5% per year?"*

*"This is the one. Watch what happens."*

The response streams in with the Safeguard projection.

*"The copilot detected a Safeguard intent, called a Unity Catalog Function — `calculate_safeguard_exposure` — which models the emissions trajectory against the declining baseline and calculates the shortfall cost. That's a UC Function being used as an AI agent tool."*

**What judges score:**
- Technical excellence — FMAPI, SSE Streaming, UC Functions as agent tools, MLflow Tracing, intent classification
- Business impact — "What if" scenario modelling that CFOs actually need
- This is the highest-density feature showcase in the demo

---

## 2:50–3:30 | Safeguard Emissions Forecaster (predictive intelligence)

**Click the "Safeguard Forecast" tab.**

*"Every company in the NEM is tracked. AGL, Origin, EnergyAustralia, CS Energy — you can see who breaches their Safeguard baseline and when."*

**Click on AGL** in the company selector.

*"AGL's combined Scope 1 is 32 million tonnes. The green dashed line is the Safeguard baseline declining 4.9% per year. The red line is projected emissions at a 2% annual reduction. They breach in 2025."*

**Point at the shortfall cost column.**

*"And the shortfall cost: 275% of the ACCU price — that's $225 per tonne. By 2029, AGL's annual shortfall cost is $X million. This is the number that changes boardroom decisions."*

*"No GRC tool does this. No spreadsheet does this. This is predictive compliance intelligence."*

**What judges score:**
- Business impact — Safeguard Mechanism is the #1 regulatory issue in Australian energy right now
- Executive alignment — CFO and CRO both care about this number
- Technical excellence — UC Function, Delta Lake, Recharts visualisation

---

## 3:30–4:10 | Reusability + Regional Adaptability (30% of score + 10% bonus)

**Show the terminal or a code view of `region.yaml`.**

*"Everything you've seen is for Australia. But the schema is universal — emissions, enforcement, obligations, market notices. That's every energy market."*

*"This is region.yaml. 8 APJ markets configured: Australia, New Zealand, Singapore, Japan, India, South Korea, Thailand, Philippines. Each with their real regulators, real companies, real legislation, and real carbon schemes."*

**Scroll through a few entries** — show Japan (METI, OCCTO, GX-ETS), India (CERC, 28 SERCs, PAT Scheme).

*"India alone has 28 state electricity regulatory commissions — the highest regulatory fragmentation in APJ. This platform handles that."*

**Show `databricks.yml`.**

*"Deployment is one command. Databricks Asset Bundles — dev, staging, prod targets. A new SA picks this up, runs `databricks bundle deploy`, and they're live in 15 minutes with their customer's data."*

**What judges score:**
- Reusability (30%) — DAB, <15 min setup, region.yaml
- Cross-region (5%) — 8 APJ markets with real regulators
- Localization (5%) — currency, companies, legislation per jurisdiction

---

## 4:10–4:40 | Quick Feature Showcase (depth of platform)

Rapid-fire through remaining tabs — 5 seconds each. Don't dwell.

**Enforcement tab:** *"85 real AER enforcement actions. Sortable by penalty. Filter by company, breach type."*

**Obligations tab:** *"80 verified regulatory obligations. Full-text search. Expandable with key requirements and legislative references."*

**Emissions tab:** *"CER NGER data — Scope 1 and 2 by facility, state, fuel source."*

**Market Notices tab:** *"200 AEMO market notices. Non-conformance, reclassification, reserve notices by NEM region."*

**Compliance Insights tab:** *"Cross-referenced intelligence — repeat offenders, enforcement trends, notice anomalies."*

**Open the Genie Space URL** (or mention it): *"And there's a Genie Space connected to all 5 tables — business users can query compliance data in natural language without writing SQL."*

**What judges score:**
- Technical excellence — breadth of data sources, real regulatory data
- Business impact — every tab solves a real compliance workflow

---

## 4:40–5:00 | Architecture + Close (land the technical story)

Show architecture diagram or call out the stack verbally.

*"11 Databricks features in one coherent platform:"*

*"Databricks Apps for deployment. Foundation Model API for AI. SSE streaming for real-time chat. Unity Catalog for governance. UC Functions as agent tools. MLflow for AI observability. SQL Warehouse for queries. Delta Lake for storage. Genie Spaces for natural language SQL. DAB for infrastructure-as-code. And config-driven regional adaptability."*

*"This isn't a demo hack. This is a production architecture that any SA can deploy in 15 minutes for any energy customer in APJ."*

*"Prevent one enforcement action — this pays for itself. $2-10 million per year ROI. 3-10x return."*

*"Thank you."*

**What judges score:**
- Technical excellence — 11 features, coherent architecture
- Reusability — the close reinforces "any SA, any customer, 15 minutes"
- Business impact — concrete ROI

---

## Timing Checklist

| Segment | Duration | Cumulative | Primary Scoring Criteria |
|---------|----------|------------|------------------------|
| The Problem | 25s | 0:25 | Business impact, exec alignment |
| Risk Heat Map | 50s | 1:15 | Technical excellence, business impact |
| Board Briefing | 45s | 2:00 | Executive alignment, FMAPI |
| AI Copilot + UC Functions | 50s | 2:50 | Technical excellence (highest density) |
| Safeguard Forecaster | 40s | 3:30 | Business impact, predictive intelligence |
| Reusability + region.yaml + DAB | 40s | 4:10 | Reusability (30%), cross-region (10%) |
| Quick Feature Showcase | 30s | 4:40 | Breadth |
| Architecture + Close | 20s | 5:00 | Technical excellence, ROI |

---

## Demo Prep Checklist

Before recording:

- [ ] App is running: https://energy-compliance-hub-7474649094582855.aws.databricksapps.com
- [ ] Open the app in browser, verify Risk Heat Map loads with data
- [ ] Click a cell — verify detail panel opens
- [ ] Click "Generate Board Briefing" — verify it loads with real numbers
- [ ] Type a chat message — verify streaming works
- [ ] Type a Safeguard question — verify UC Function intent fires
- [ ] Click through all 7 tabs — verify each loads data
- [ ] Have `region.yaml` and `databricks.yml` open in a code editor
- [ ] Have the Genie Space URL ready to show or screenshot
- [ ] Browser zoom at 90-100%, full screen, no bookmarks bar
- [ ] Close all other tabs and notifications

---

## Key Phrases to Land

Use these exact phrases — they're calibrated for CXO audience and buildathon judges:

- *"600+ obligations across 8 regulators — tracked in spreadsheets"*
- *"$54 million in annual fines"*
- *"Three weeks to three minutes"*
- *"Prevent one enforcement action — this pays for itself"*
- *"UC Function used as an AI agent tool"*
- *"Every interaction traced in MLflow"*
- *"8 APJ markets, one config file"*
- *"Any SA, any customer, 15 minutes"*
- *"$2-10 million per year ROI. 3-10x return."*
- *"No GRC tool does this. No spreadsheet does this."*

---

## If You Have Extra Time

If the demo comes in under 5 minutes, add one of these:

**Option A — ProcessIQ connection (10 seconds):**
*"This platform tells you what you need to comply with. Our companion platform, ProcessIQ, captures how you actually comply — through AI-powered SME interviews. The gap between the two is where fines happen."*

**Option B — Customer examples (10 seconds):**
*"AusNet uses this for ESV safety obligations and network compliance. Alinta uses it for Safeguard exposure at Loy Yang B and retail enforcement risk. Same platform, different risk profiles."*

**Option C — Second copilot question (15 seconds):**
Type *"What are our AEMO market operation obligations?"* and show the response.

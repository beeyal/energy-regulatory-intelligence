"""
Multi-region data generators for all non-AU APJ markets.
Data is generated from real regulatory knowledge: actual companies, real legislation,
accurate penalty ranges in local currency converted to AUD, correct regulator names.

Markets: SG, NZ, JP, IN, KR, TH, PH
"""

import random
import uuid
from datetime import date, datetime, timedelta

import pandas as pd

# Approximate exchange rates to AUD (2024-25)
FX_TO_AUD = {
    "SG": 1.10,   # 1 SGD ≈ 1.10 AUD
    "NZ": 0.92,   # 1 NZD ≈ 0.92 AUD
    "JP": 0.010,  # 1 JPY ≈ 0.010 AUD
    "IN": 0.018,  # 1 INR ≈ 0.018 AUD
    "KR": 0.0011, # 1 KRW ≈ 0.0011 AUD
    "TH": 0.043,  # 1 THB ≈ 0.043 AUD
    "PH": 0.027,  # 1 PHP ≈ 0.027 AUD
}

rng = random.Random(42)  # deterministic seed for reproducibility


def _rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=rng.randint(0, delta))


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


# ──────────────────────────────────────────────────────────────────────────────
# SINGAPORE
# ──────────────────────────────────────────────────────────────────────────────

def sg_emissions() -> pd.DataFrame:
    companies = [
        ("Sembcorp Industries", "Sembcorp Cogen Plant", "Central", "Gas", 4_200_000),
        ("Keppel Infrastructure", "Keppel Merlimau Cogen", "West", "Gas", 3_800_000),
        ("Senoko Energy", "Senoko Power Station", "North", "Gas", 5_100_000),
        ("YTL PowerSeraya", "PowerSeraya Plant", "West", "Gas", 3_600_000),
        ("Tuas Power", "Tuas Power Station", "West", "Gas", 4_500_000),
        ("Pacific Light Power", "PLP Power Plant", "West", "Gas", 2_200_000),
        ("City Energy", "City Gas Operations", "Central", "Gas", 480_000),
        ("ExxonMobil Singapore", "Jurong Island Refinery", "West", "Oil", 6_800_000),
        ("Shell Eastern Petroleum", "Shell Bukom Refinery", "South", "Oil", 5_900_000),
        ("Linde Singapore", "Tuas Industrial Gases", "West", "Gas", 320_000),
        ("Air Products Singapore", "Jurong Chemical Complex", "West", "Gas", 290_000),
        ("Sunseap Group", "Tengeh Reservoir Solar", "West", "Solar", 12_000),
        ("SP PowerAssets", "Grid Operations Central", "Central", "Multiple", 180_000),
        ("Chevron Singapore", "Singapore Refinery", "West", "Oil", 3_100_000),
        ("BASF SE Singapore", "Jurong Island Chemical", "West", "Gas", 1_400_000),
    ]
    rows = []
    for corp, fac, state, fuel, base_s1 in companies:
        rows.append({
            "market": "SG",
            "corporation_name": corp,
            "facility_name": fac,
            "state": state,
            "scope1_emissions_tco2e": round(base_s1 * rng.uniform(0.92, 1.08)),
            "scope2_emissions_tco2e": round(base_s1 * 0.08 * rng.uniform(0.8, 1.2)),
            "net_energy_consumed_gj": round(base_s1 * 0.015 * rng.uniform(0.9, 1.1)),
            "electricity_production_mwh": round(base_s1 * 0.0004) if fuel != "Solar" else round(base_s1 * 2),
            "primary_fuel_source": fuel,
            "reporting_year": "2023-24",
        })
    return pd.DataFrame(rows)


def sg_market_notices() -> pd.DataFrame:
    types = ["GENERATION CONSTRAINT", "PRICE CAP NOTICE", "RESERVE SHORTFALL",
             "DIRECTION NOTICE", "MARKET SUSPENSION", "REGULATORY ADVISORY"]
    regions = ["Central", "East", "West", "North"]
    reasons = [
        "Unplanned outage at Senoko Power Station — capacity constraint in North region",
        "Half-hourly settlement price exceeded regulatory cap at SGD 4,500/MWh",
        "Reserve margin below 30-minute operating reserve requirement per EMA rule 4.2",
        "EMA direction to PowerSeraya to maintain minimum generation output",
        "Extreme demand event — NEMS market suspension triggered under EMA Rule 16.3",
        "EMA advisory: planned maintenance Tuas Power Unit 3, 15-18 Jan 2025",
        "Gas supply curtailment affecting combined cycle units — system advisory",
        "Load forecasting deviation exceeding 5% threshold — grid operator notice",
        "Interruptible load activation — demand response event SGD incentive SGD 180/MWh",
        "Non-conformance: PLP failed to follow dispatch instruction reference EMA-NC-2024-041",
        "Frequency regulation event — automatic generation control activated 03:14-03:28 SGT",
        "Capacity bidding irregularity — EMA Market Surveillance Unit notified",
        "Reactive power support notice — SP PowerAssets grid stability advisory",
        "Carbon tax reporting deadline reminder — NEA CPA-2024 Q4 submissions",
        "NEMS market clearing price anomaly investigation — EMA Market Monitoring notice",
    ]
    rows = []
    for i in range(40):
        rows.append({
            "market": "SG",
            "notice_id": f"SG-MN-{2024000 + i}",
            "notice_type": rng.choice(types),
            "creation_date": datetime.combine(_rand_date(date(2024, 1, 1), date(2025, 3, 31)), datetime.min.time()),
            "issue_date": datetime.combine(_rand_date(date(2024, 1, 1), date(2025, 3, 31)), datetime.min.time()),
            "region": rng.choice(regions),
            "reason": rng.choice(reasons),
            "external_reference": f"EMA-{rng.randint(1000,9999)}/{2024 + rng.randint(0,1)}",
        })
    return pd.DataFrame(rows)


def sg_enforcement() -> pd.DataFrame:
    actions = [
        ("Senoko Energy", "Licence Condition Breach", "Market Conduct", "Failed to comply with EMA dispatch instruction on 14 occasions in Q3 2023", 2_500_000, "Penalty issued", "EMA Licence Condition 4.3(b)"),
        ("YTL PowerSeraya", "Infringement Notice", "Price Manipulation", "Suspicious bidding patterns identified during peak demand period Aug 2023", 1_800_000, "Penalty paid", "Electricity Act s.12A"),
        ("Pacific Light Power", "Enforcement Order", "Capacity Compliance", "Failure to maintain declared available capacity within 5% tolerance", 900_000, "Compliance plan submitted", "EMA Rule 4.1.2"),
        ("Keppel Infrastructure", "Court Proceedings", "Safety Violation", "Unplanned outage caused by inadequate maintenance — grid stability incident", 4_200_000, "Court order issued", "Electricity Act s.36"),
        ("Tuas Power", "Infringement Notice", "Reporting Failure", "Late submission of quarterly generation data — 23 days overdue", 450_000, "Penalty paid", "EMA Market Rules r.6.2"),
        ("ExxonMobil Singapore", "Penalty Notice", "Carbon Tax Non-Compliance", "Under-reporting of CO2 emissions by 45,000 tCO2e in 2022-23 NEA submission", 3_100_000, "Amended report filed", "Carbon Pricing Act s.18"),
        ("Shell Eastern Petroleum", "Compliance Audit", "Environmental Breach", "Excess SO2 emissions detected at Bukom refinery Q2 2024", 1_600_000, "Remediation completed", "EPMA r.14"),
        ("Sembcorp Industries", "Voluntary Disclosure", "Market Conduct", "Self-reported bidding system error resulting in non-conforming dispatch bid", 680_000, "Penalty reduced", "EMA Rule 3.4.1"),
        ("City Energy", "Infringement Notice", "Gas Safety", "Inadequate pressure monitoring at 3 district regulation stations", 520_000, "Penalty paid", "Gas Act s.8(2)"),
        ("SP PowerAssets", "Direction Notice", "Grid Code Breach", "Failure to maintain power factor within required ±0.95 at 4 substations", 1_200_000, "Grid upgrades completed", "Grid Code s.5.2"),
        ("BASF SE Singapore", "Penalty Notice", "Carbon Tax", "Missing supporting documentation for eligible deductions in CPA submission", 380_000, "Documentation provided", "Carbon Pricing Act s.21"),
        ("Linde Singapore", "Compliance Audit", "Safety", "Pressure safety valve maintenance records incomplete for 2 vessels", 290_000, "Records updated", "Pressure Vessels Act"),
    ]
    rows = []
    for i, (company, atype, breach, desc, penalty_local, outcome, ref) in enumerate(actions):
        penalty_aud = round(penalty_local * FX_TO_AUD["SG"])
        rows.append({
            "market": "SG",
            "action_id": _uid("SG-ENF"),
            "company_name": company,
            "action_date": _rand_date(date(2020, 1, 1), date(2025, 3, 31)),
            "action_type": atype,
            "breach_type": breach,
            "breach_description": desc,
            "penalty_aud": float(penalty_aud),
            "outcome": outcome,
            "regulatory_reference": ref,
        })
    return pd.DataFrame(rows)


def sg_obligations() -> pd.DataFrame:
    rows = [
        ("EMA", "NEMS Market Registration", "Market", "Ongoing", "Critical", 5_000_000, "Electricity Act s.6", "All generation facilities must hold an EMA generation licence and be registered as Market Participants.", "Submit registration, maintain technical standards, comply with dispatch instructions."),
        ("EMA", "Dispatch Compliance", "Market", "Continuous", "Critical", 2_000_000, "EMA Market Rules r.4.3", "Market participants must comply with all dispatch instructions from NEMS market operator.", "Accept and follow dispatch instructions within required response times."),
        ("EMA", "Capacity Declaration", "Market", "Daily", "High", 1_000_000, "EMA Market Rules r.4.1", "Generators must declare available capacity accurately within 5% tolerance.", "Submit daily capacity bids; update on unplanned outage within 30 minutes."),
        ("NEA", "Carbon Tax Registration", "Environment", "Annual", "Critical", 200_000, "Carbon Pricing Act s.7", "Facilities emitting ≥25,000 tCO2e annually must register under the Carbon Pricing Act.", "Register, monitor emissions, submit annual GHG report, surrender carbon credits."),
        ("NEA", "GHG Monitoring & Reporting", "Environment", "Annual", "Critical", 500_000, "Carbon Pricing Act s.18", "Registered facilities must monitor and report GHG emissions using approved methodologies.", "Install approved monitoring equipment, submit verified annual report by 30 June."),
        ("NEA", "Carbon Tax Payment", "Financial", "Annual", "Critical", 1_000_000, "Carbon Pricing Act s.20", "Liable parties must surrender carbon credits equal to their verified emissions.", "Purchase and surrender eligible carbon credits (ICCs/domestic) by 30 September."),
        ("EMA", "Grid Code Compliance", "Technical", "Continuous", "High", 1_500_000, "EMA Grid Code s.5", "All transmission-connected parties must comply with Grid Code voltage and frequency requirements.", "Maintain power factor, respond to reactive power instructions, comply with protection settings."),
        ("EMA", "Metering Standards", "Market", "Continuous", "High", 800_000, "EMA Metering Code", "All market participants must install and maintain EMA-approved metering equipment.", "Calibrate meters annually, submit meter data within 5 business days of each trading period."),
        ("SP Group", "Network Connection Agreement", "Technical", "Ongoing", "Medium", 600_000, "Electricity Act s.24", "All parties connecting to the transmission network must hold a valid connection agreement.", "Apply for connection, comply with technical specifications, maintain connection assets."),
        ("EMA", "Market Surveillance Cooperation", "Market", "Ongoing", "High", 1_000_000, "Electricity Act s.43", "Market participants must cooperate with EMA Market Surveillance Unit investigations.", "Provide records within 10 business days of request; permit on-site audits."),
        ("MAS", "Climate Risk Disclosure", "Financial", "Annual", "Medium", 300_000, "MAS Notice SFA 04-N16", "Listed energy companies must disclose climate-related financial risks per TCFD framework.", "Publish annual TCFD-aligned disclosure in annual report."),
        ("NEA", "Environmental Permit", "Environment", "Annual renewal", "High", 400_000, "EPMA s.5", "Industrial facilities with significant emissions must hold a valid NEA environmental permit.", "Apply for permit renewal 6 months before expiry; comply with permit conditions."),
        ("EMA", "Ancillary Services Provision", "Technical", "Ongoing", "Medium", 500_000, "EMA Market Rules r.5.1", "Eligible generators must be capable of providing primary, secondary and contingency reserves.", "Register ancillary service capability, respond within specified activation times."),
        ("EMA", "Cybersecurity Standards", "Technical", "Annual audit", "High", 1_000_000, "EMA CCoP 2021", "Critical energy infrastructure must comply with EMA Cybersecurity Code of Practice.", "Implement controls, conduct annual penetration testing, report incidents within 1 hour."),
        ("NEA", "Energy Efficiency Reporting", "Environment", "Annual", "Medium", 150_000, "ECA s.21", "Corporations with energy use >54,000 GJ/year must submit energy efficiency improvement plans.", "Conduct energy audit, submit improvement plan, report progress annually to NEA."),
    ]
    result = []
    for i, (body, name, cat, freq, risk, penalty_local, leg, desc, req) in enumerate(rows):
        result.append({
            "market": "SG",
            "obligation_id": _uid("SG-OBL"),
            "regulatory_body": body,
            "obligation_name": name,
            "category": cat,
            "frequency": freq,
            "risk_rating": risk,
            "penalty_max_aud": round(penalty_local * FX_TO_AUD["SG"]),
            "source_legislation": leg,
            "description": desc,
            "key_requirements": req,
        })
    return pd.DataFrame(result)


# ──────────────────────────────────────────────────────────────────────────────
# NEW ZEALAND
# ──────────────────────────────────────────────────────────────────────────────

def nz_emissions() -> pd.DataFrame:
    companies = [
        ("Meridian Energy", "Manapouri Power Station", "SI", "Hydro", 45_000),
        ("Meridian Energy", "Tekapo Power Station", "SI", "Hydro", 38_000),
        ("Contact Energy", "Wairakei Geothermal", "NI", "Geothermal", 820_000),
        ("Contact Energy", "Taranaki Combined Cycle", "NI", "Gas", 1_400_000),
        ("Genesis Energy", "Huntly Power Station", "NI", "Coal", 3_200_000),
        ("Genesis Energy", "Huntly e3p Gas Peaker", "NI", "Gas", 680_000),
        ("Mercury Energy", "Waikato Hydro Scheme", "NI", "Hydro", 52_000),
        ("Todd Energy", "McKee Gas Field", "NI", "Gas", 920_000),
        ("Nova Energy", "Southdown Power Station", "NI", "Gas", 560_000),
        ("Trustpower", "Tararua Wind Farm", "NI", "Wind", 8_000),
        ("NZ Steel", "Glenbrook Steel Mill", "NI", "Coal", 2_800_000),
        ("Methanex NZ", "Waitara Valley Methanol", "NI", "Gas", 1_100_000),
        ("Fonterra Co-operative", "Whareroa Dairy Factory", "NI", "Gas", 780_000),
        ("New Zealand Aluminium Smelters", "Tiwai Point Smelter", "SI", "Hydro/Coal", 1_650_000),
        ("Transpower New Zealand", "Grid Operations NI", "NI", "Multiple", 95_000),
    ]
    rows = []
    for corp, fac, state, fuel, base_s1 in companies:
        rows.append({
            "market": "NZ",
            "corporation_name": corp,
            "facility_name": fac,
            "state": state,
            "scope1_emissions_tco2e": round(base_s1 * rng.uniform(0.92, 1.08)),
            "scope2_emissions_tco2e": round(base_s1 * 0.05 * rng.uniform(0.8, 1.2)),
            "net_energy_consumed_gj": round(base_s1 * 0.018 * rng.uniform(0.9, 1.1)),
            "electricity_production_mwh": round(base_s1 * 0.0003),
            "primary_fuel_source": fuel,
            "reporting_year": "2023-24",
        })
    return pd.DataFrame(rows)


def nz_market_notices() -> pd.DataFrame:
    types = ["CONSTRAINT NOTICE", "RESERVE SHORTAGE", "MARKET SUSPENDED",
             "DISPATCH ADVISORY", "OUTAGE NOTIFICATION", "PRICE SPIKE ALERT"]
    regions = ["NI", "SI", "HAY", "BEN", "OTA", "ISL"]
    reasons = [
        "Hvdc link operating at reduced capacity — North Island reserve constraint active",
        "Waikato river low inflow event — hydro generation limited this dispatch period",
        "Genesis Huntly Unit 4 unplanned outage — system security constraint NI",
        "Frequency keeping capacity shortfall — additional reserve procurement required",
        "Transpower SO instruction — North Island voltage support required",
        "Price spike event: Haywards node price NZD 18,500/MWh at 16:30-16:35 NZST",
        "Planned outage Manapouri Unit 7 — SI generation reduced 120 MW 14-21 Feb",
        "Wind generation below forecast by 350 MW — NI thermal dispatch increased",
        "Contact Energy Wairakei geothermal output curtailed — planned maintenance",
        "Reserve shortage notice — spinning reserve below 3,500 MW threshold",
        "Market suspension event: generation shortfall > demand at 18:15-18:22 NZST",
        "Interruptible load activation — demand response 280 MW SI node Benmore",
        "HVDC transfer limit reduced to 900 MW due to transmission fault TKA-HAY",
        "EA market advisory: gate closure time change effective 1 April 2025",
        "Dispatch advisory: Tiwai Point aluminium smelter demand reduction 200 MW",
    ]
    rows = []
    for i in range(45):
        rows.append({
            "market": "NZ",
            "notice_id": f"NZ-MN-{2024000 + i}",
            "notice_type": rng.choice(types),
            "creation_date": datetime.combine(_rand_date(date(2024, 1, 1), date(2025, 3, 31)), datetime.min.time()),
            "issue_date": datetime.combine(_rand_date(date(2024, 1, 1), date(2025, 3, 31)), datetime.min.time()),
            "region": rng.choice(regions),
            "reason": rng.choice(reasons),
            "external_reference": f"EA-{rng.randint(1000,9999)}/{2024 + rng.randint(0,1)}",
        })
    return pd.DataFrame(rows)


def nz_enforcement() -> pd.DataFrame:
    actions = [
        ("Genesis Energy", "Infringement Notice", "Market Conduct", "Failure to comply with dispatch offer format requirements on 12 trading periods", 250_000, "Penalty paid", "Electricity Industry Participation Code cl.13.8"),
        ("Contact Energy", "Compliance Order", "Offer Behaviour", "Investigation into whether pivot pricing strategy breached Part 13 of the Code", 1_800_000, "Compliance undertaking accepted", "Electricity Industry Act s.32"),
        ("Meridian Energy", "Warning Letter", "Disclosure Breach", "Late disclosure of generation asset outage — 4 hours beyond required notification window", 0, "Warning issued", "EIPC cl.14.2"),
        ("NZ Steel", "Penalty Notice", "ETS Obligation", "Failure to surrender sufficient NZUs by 31 May deadline — shortfall 12,400 units", 620_000, "Penalty paid + NZUs surrendered", "Climate Change Response Act s.134"),
        ("Todd Energy", "Court Proceedings", "Resource Consent Breach", "Gas extraction exceeded consented volumes by 8% in 2022-23 reporting year", 3_200_000, "Court order — consent conditions tightened", "Resource Management Act s.338"),
        ("Methanex NZ", "Infringement Notice", "ETS Reporting", "Methanol production emissions under-reported by 28,000 tCO2e in 2022 return", 450_000, "Amended return filed", "Climate Change Response Act s.81"),
        ("Nova Energy", "Compliance Audit", "Metering", "Revenue metering equipment found non-compliant during routine EA audit", 180_000, "Metering replaced", "EIPC Schedule 7"),
        ("Fonterra Co-operative", "Penalty Notice", "ETS Obligation", "Failure to account for process heat emissions correctly under NZ ETS", 380_000, "Penalty paid", "Climate Change Response Act s.62"),
        ("Transpower New Zealand", "Enforcement Order", "Grid Reliability", "HVDC link maintenance deferral led to system security event — inadequate planning", 2_100_000, "Remediation plan approved", "Electricity Industry Act s.46"),
        ("New Zealand Aluminium Smelters", "Compliance Audit", "Energy Efficiency", "Energy audit requirements not met for 2022-23 period under Energy Efficiency Act", 120_000, "Audit completed", "Energy Efficiency and Conservation Act s.24"),
    ]
    rows = []
    for company, atype, breach, desc, penalty_local, outcome, ref in actions:
        penalty_aud = round(penalty_local * FX_TO_AUD["NZ"])
        rows.append({
            "market": "NZ",
            "action_id": _uid("NZ-ENF"),
            "company_name": company,
            "action_date": _rand_date(date(2019, 1, 1), date(2025, 3, 31)),
            "action_type": atype,
            "breach_type": breach,
            "breach_description": desc,
            "penalty_aud": float(penalty_aud),
            "outcome": outcome,
            "regulatory_reference": ref,
        })
    return pd.DataFrame(rows)


def nz_obligations() -> pd.DataFrame:
    rows = [
        ("EA", "Market Participant Registration", "Market", "Ongoing", "Critical", 2_000_000, "Electricity Industry Act 2010 s.6", "All generators, retailers and traders must register as market participants with the Electricity Authority.", "Submit registration application, maintain technical compliance, pay annual levies."),
        ("EA", "Dispatch Offer Compliance", "Market", "Per trading period", "Critical", 500_000, "EIPC Part 13", "All generators must submit compliant dispatch offers for each trading period in accordance with the Code.", "Submit offers before gate closure; comply with offer format requirements."),
        ("MfE", "NZ ETS Surrender Obligation", "Environment", "Annual (31 May)", "Critical", 2_500_000, "Climate Change Response Act s.134", "All participants in NZ ETS must surrender New Zealand Units (NZUs) equal to their net emissions.", "Monitor emissions, calculate net position, surrender NZUs by 31 May each year."),
        ("MfE", "Annual Emissions Return", "Environment", "Annual (31 March)", "Critical", 500_000, "Climate Change Response Act s.81", "ETS participants must submit verified annual emissions return.", "Collect monitoring data, obtain independent verification, submit return to EPA by 31 March."),
        ("Commerce Commission", "Input Methodologies Compliance", "Financial", "Ongoing", "High", 10_000_000, "Commerce Act 1986 Part 4", "Transpower and lines companies must comply with Commerce Commission input methodologies for regulated revenues.", "Apply approved methodologies in pricing decisions; comply with disclosure obligations."),
        ("EA", "Metering Equipment Standards", "Technical", "Continuous", "High", 200_000, "EIPC Schedule 7", "All market participants must install EA-approved revenue metering equipment.", "Install approved meters, maintain calibration records, report data within required timeframes."),
        ("Transpower", "Grid Connection Agreement", "Technical", "Ongoing", "High", 1_000_000, "Electricity Industry Act s.35", "All generators and major consumers must hold a valid grid connection agreement.", "Comply with technical standards in connection agreement; notify Transpower of significant changes."),
        ("EA", "Offer Behaviour Rule", "Market", "Continuous", "Critical", 5_000_000, "Electricity Industry Act s.32", "Generators must not exercise undue market power in the wholesale electricity market.", "Offer in accordance with Part 13 offer behaviour obligations; cooperate with EA investigations."),
        ("MfE", "Resource Consent Compliance", "Environment", "Ongoing", "High", 600_000, "Resource Management Act 1991", "All energy facilities must hold and comply with resource consents for their operations.", "Operate within consented volumes; report any consent conditions breach; seek variation if needed."),
        ("EA", "Information Disclosure", "Market", "Ongoing", "Medium", 300_000, "EIPC Part 14", "Market participants must disclose material information affecting generation or demand.", "Notify market of planned and unplanned outages within required timeframes."),
    ]
    result = []
    for body, name, cat, freq, risk, penalty_local, leg, desc, req in rows:
        result.append({
            "market": "NZ",
            "obligation_id": _uid("NZ-OBL"),
            "regulatory_body": body,
            "obligation_name": name,
            "category": cat,
            "frequency": freq,
            "risk_rating": risk,
            "penalty_max_aud": round(penalty_local * FX_TO_AUD["NZ"]),
            "source_legislation": leg,
            "description": desc,
            "key_requirements": req,
        })
    return pd.DataFrame(result)


# ──────────────────────────────────────────────────────────────────────────────
# JAPAN
# ──────────────────────────────────────────────────────────────────────────────

def jp_emissions() -> pd.DataFrame:
    companies = [
        ("TEPCO (Tokyo Electric Power)", "Kawasaki Thermal Power", "Tokyo", "LNG", 8_200_000),
        ("TEPCO (Tokyo Electric Power)", "Hirono Thermal Power", "Tohoku", "Coal/Oil", 6_800_000),
        ("Kansai Electric Power (KEPCO)", "Himeji No.2 Power", "Kansai", "LNG", 7_100_000),
        ("Chubu Electric Power", "Hekinan Thermal Power", "Chubu", "Coal", 12_400_000),
        ("Kyushu Electric Power", "Matsuura Thermal Power", "Kyushu", "Coal", 9_600_000),
        ("Tohoku Electric Power", "Sendai Thermal Power", "Tohoku", "Oil/LNG", 5_300_000),
        ("JERA", "Yokosuka Power Station", "Tokyo", "Coal/LNG", 11_200_000),
        ("JERA", "Chita LNG Power Station", "Chubu", "LNG", 6_400_000),
        ("Eneos Holdings", "Negishi Oil Refinery", "Tokyo", "Oil", 4_800_000),
        ("Nippon Steel", "Kimitsu Steel Works", "Tokyo", "Coal/Gas", 18_600_000),
        ("JFE Steel", "Fukuyama Steel Works", "Chugoku", "Coal/Gas", 14_200_000),
        ("Sumitomo Chemical", "Ehime Petrochemical", "Shikoku", "Oil/Gas", 3_200_000),
        ("Mitsubishi Chemical", "Kashima Petrochemical", "Tokyo", "Oil/Gas", 4_100_000),
        ("Shin-Etsu Chemical", "Naoetsu LNG Terminal", "Chubu", "LNG", 1_800_000),
        ("Hokkaido Electric Power", "Tomato-Atsuma Thermal", "Hokkaido", "Coal", 7_300_000),
    ]
    rows = []
    for corp, fac, state, fuel, base_s1 in companies:
        rows.append({
            "market": "JP",
            "corporation_name": corp,
            "facility_name": fac,
            "state": state,
            "scope1_emissions_tco2e": round(base_s1 * rng.uniform(0.92, 1.08)),
            "scope2_emissions_tco2e": round(base_s1 * 0.04 * rng.uniform(0.8, 1.2)),
            "net_energy_consumed_gj": round(base_s1 * 0.012 * rng.uniform(0.9, 1.1)),
            "electricity_production_mwh": round(base_s1 * 0.00025),
            "primary_fuel_source": fuel,
            "reporting_year": "2023-24",
        })
    return pd.DataFrame(rows)


def jp_market_notices() -> pd.DataFrame:
    types = ["SUPPLY-DEMAND TIGHTNESS", "EMERGENCY MEASURES", "FREQUENCY DEVIATION",
             "INTERCONNECTOR CONSTRAINT", "MARKET ADVISORY", "CAPACITY ALERT"]
    regions = ["Hokkaido", "Tohoku", "Tokyo", "Chubu", "Kansai", "Chugoku", "Shikoku", "Kyushu"]
    reasons = [
        "OCCTO demand forecast exceeded available supply margin — tight supply-demand advisory issued",
        "Frequency deviation event 49.7 Hz — OCCTO emergency frequency regulation activated",
        "JEPX spot price exceeded JPY 100/kWh cap — emergency supply measures activated",
        "Tokyo area interconnector capacity reduced — 600 MW transfer limit in effect",
        "Kansai-Chugoku interconnector maintenance — transfer capacity reduced to 2,800 MW",
        "Cold wave demand spike — OCCTO requesting voluntary conservation from large consumers",
        "Unplanned outage TEPCO Kawasaki Unit 2 — 600 MW capacity loss Tokyo area",
        "METI advisory: GX League reporting deadline extended to 30 April 2025",
        "Nuclear restart approval — Kepco Takahama Unit 4 returned to service",
        "Renewable output forecast revision: Kyushu curtailment event — 850 MW solar curtailed",
        "OCCTO monthly supply-demand outlook: FY2025 supply reserve margin 8.1% (critical threshold 3%)",
        "LNG supply disruption advisory — fuel procurement emergency measures considered",
        "Peak demand alert: Tokyo area forecast 54,000 MW — reserve margin 3.2%",
        "JEPX market rule revision notice: intraday market trading hours extended from April",
        "Capacity market result notice: clearing price JPY 14,000/kW — FY2027-28 delivery",
    ]
    rows = []
    for i in range(50):
        rows.append({
            "market": "JP",
            "notice_id": f"JP-MN-{2024000 + i}",
            "notice_type": rng.choice(types),
            "creation_date": datetime.combine(_rand_date(date(2024, 1, 1), date(2025, 3, 31)), datetime.min.time()),
            "issue_date": datetime.combine(_rand_date(date(2024, 1, 1), date(2025, 3, 31)), datetime.min.time()),
            "region": rng.choice(regions),
            "reason": rng.choice(reasons),
            "external_reference": f"OCCTO-{rng.randint(1000,9999)}-{2024 + rng.randint(0,1)}",
        })
    return pd.DataFrame(rows)


def jp_enforcement() -> pd.DataFrame:
    actions = [
        ("TEPCO (Tokyo Electric Power)", "Business Improvement Order", "Safety Violation", "Inadequate nuclear facility safety management procedures — METI inspection finding", 0, "Business improvement plan submitted to METI", "Electricity Business Act s.40"),
        ("Chubu Electric Power", "Penalty Order", "GHG Reporting Failure", "Act on Promotion of Global Warming Countermeasures — emission factor calculation error", 1_000_000, "Corrected report filed", "Global Warming Countermeasures Act s.26"),
        ("JERA", "Administrative Guidance", "Capacity Declaration", "Inaccurate capacity market declaration — 200 MW discrepancy found in OCCTO audit", 0, "Corrected declaration submitted", "Electricity Business Act s.33"),
        ("Nippon Steel", "Penalty Notice", "Energy Conservation Violation", "Energy Conservation Act — failure to achieve mandated energy intensity reduction target", 500_000, "Improvement plan submitted to METI", "Act on Rational Use of Energy s.16"),
        ("JFE Steel", "Compliance Order", "GHG Reporting", "Steel sector benchmark emission factor incorrectly applied — 380,000 tCO2 under-reported", 1_500_000, "Third-party verification obtained", "Global Warming Countermeasures Act s.26"),
        ("Eneos Holdings", "Administrative Order", "Safety Management", "Petroleum facility safety management deficiency — emergency shutdown system inadequate", 800_000, "Safety system upgraded", "Fire Defense Act s.14"),
        ("Kansai Electric Power (KEPCO)", "Business Improvement Order", "Market Conduct", "JEPX bidding strategy investigation — potential withholding of capacity during shortage", 0, "Bidding guidelines revised", "Electricity Business Act s.21"),
        ("Kyushu Electric Power", "Penalty Notice", "Renewable Curtailment", "Excessive curtailment of solar output without METI pre-approval during normal system conditions", 600_000, "Curtailment protocol revised", "Electricity Business Act s.28"),
        ("Sumitomo Chemical", "Compliance Audit", "Energy Efficiency", "Energy management system found inadequate — designated energy manager role vacant for 6 months", 300_000, "Qualified manager appointed", "Act on Rational Use of Energy s.8"),
        ("Hokkaido Electric Power", "Court Proceedings", "Environmental", "Coal ash disposal site groundwater contamination — improper waste management", 3_000_000, "Remediation order issued", "Waste Management Law s.25"),
    ]
    rows = []
    for company, atype, breach, desc, penalty_local, outcome, ref in actions:
        penalty_aud = round(penalty_local * FX_TO_AUD["JP"])
        rows.append({
            "market": "JP",
            "action_id": _uid("JP-ENF"),
            "company_name": company,
            "action_date": _rand_date(date(2019, 1, 1), date(2025, 3, 31)),
            "action_type": atype,
            "breach_type": breach,
            "breach_description": desc,
            "penalty_aud": float(penalty_aud),
            "outcome": outcome,
            "regulatory_reference": ref,
        })
    return pd.DataFrame(rows)


def jp_obligations() -> pd.DataFrame:
    rows = [
        ("METI", "Electricity Business Licence", "Market", "Ongoing", "Critical", 100_000_000, "Electricity Business Act s.3", "All entities operating power generation above 1 MW must hold a METI electricity business licence.", "Apply for licence, maintain technical standards, report significant operational changes."),
        ("METI", "GHG Emission Reporting", "Environment", "Annual (July)", "Critical", 10_000_000, "Global Warming Countermeasures Act s.26", "Facilities emitting ≥3,000 tCO2e must report emissions to national GHG inventory.", "Monitor emissions using approved methods, submit annual report to METI/MOE by end of July."),
        ("METI", "Energy Conservation Reporting", "Environment", "Annual (July)", "Critical", 1_000_000, "Act on Rational Use of Energy s.16", "Designated energy users (≥1,500 kL/year crude oil equivalent) must submit energy management plans.", "Appoint qualified energy manager, submit medium-term energy efficiency plan, report annually."),
        ("OCCTO", "Capacity Market Participation", "Market", "Annual auction", "High", 50_000_000, "Electricity Business Act s.29", "All generation capacity must participate in OCCTO capacity market or hold exemption.", "Submit capacity declaration, meet delivery obligation, pay non-delivery penalties."),
        ("METI", "GX League Participation", "Environment", "Annual", "High", 5_000_000, "GX Promotion Act 2023", "Major emitters are expected to participate in GX League voluntary ETS from FY2023.", "Set GHG reduction targets, trade GX-ETS credits, report progress to GX League secretariat."),
        ("METI", "Renewable Energy FIT/FIP Compliance", "Market", "Ongoing", "High", 30_000_000, "Act on Special Measures for Procurement of Renewable Electric Energy", "FIT/FIP certified generators must comply with output management and reporting requirements.", "Submit monthly generation reports, comply with curtailment instructions, maintain certification."),
        ("METI", "Nuclear Safety Standards", "Safety", "Continuous", "Critical", 0, "Electricity Business Act s.40 / Nuclear Regulation Act", "Nuclear operators must comply with new regulatory standards post-Fukushima.", "Implement severe accident measures, maintain emergency response plans, pass NRA inspections."),
        ("MOE", "J-Credit Registration", "Environment", "Per project", "Medium", 2_000_000, "Act on Promotion of Global Warming Countermeasures", "Entities seeking J-Credit verification must register projects with J-Credit Scheme secretariat.", "Submit project plan, obtain third-party verification, register credits within 6 months."),
        ("JEPX", "Market Conduct Rules", "Market", "Continuous", "High", 20_000_000, "Electricity Business Act s.21", "JEPX participants must comply with market manipulation prohibition.", "Avoid coordinated bidding; cooperate with JEPX market surveillance; maintain 3-year trading records."),
        ("METI", "Power System Security", "Technical", "Continuous", "Critical", 50_000_000, "Electricity Business Act s.28", "All grid-connected generators must comply with OCCTO grid code requirements.", "Maintain frequency response capability, comply with interconnector limits, report outages promptly."),
    ]
    result = []
    for body, name, cat, freq, risk, penalty_local, leg, desc, req in rows:
        result.append({
            "market": "JP",
            "obligation_id": _uid("JP-OBL"),
            "regulatory_body": body,
            "obligation_name": name,
            "category": cat,
            "frequency": freq,
            "risk_rating": risk,
            "penalty_max_aud": round(penalty_local * FX_TO_AUD["JP"]),
            "source_legislation": leg,
            "description": desc,
            "key_requirements": req,
        })
    return pd.DataFrame(result)


# ──────────────────────────────────────────────────────────────────────────────
# INDIA
# ──────────────────────────────────────────────────────────────────────────────

def in_emissions() -> pd.DataFrame:
    companies = [
        ("NTPC Limited", "Vindhyachal Super Thermal", "Western Region", "Coal", 32_000_000),
        ("NTPC Limited", "Sipat Thermal Power", "Western Region", "Coal", 24_000_000),
        ("Adani Power", "Mundra Thermal Power", "Western Region", "Coal", 28_000_000),
        ("Tata Power", "Mundra Ultra Mega Power", "Western Region", "Coal", 22_000_000),
        ("JSW Energy", "Vijayanagar Power", "Southern Region", "Coal", 8_600_000),
        ("Torrent Power", "Sugen Combined Cycle", "Western Region", "Gas", 4_200_000),
        ("CESC", "Budge Budge Thermal", "Eastern Region", "Coal", 6_800_000),
        ("Greenko Group", "Pinnapuram Pumped Storage", "Southern Region", "Hydro", 85_000),
        ("ReNew Power", "Rajasthan Wind Farm", "Northern Region", "Wind", 42_000),
        ("Steel Authority of India (SAIL)", "Bhilai Steel Plant", "Western Region", "Coal/Gas", 18_400_000),
        ("Tata Steel", "Jamshedpur Steel Works", "Eastern Region", "Coal/Gas", 14_200_000),
        ("Indian Oil Corporation", "Panipat Refinery", "Northern Region", "Oil", 7_600_000),
        ("Reliance Industries", "Jamnagar Refinery Complex", "Western Region", "Oil", 19_800_000),
        ("ONGC", "Mumbai High Offshore", "Western Region", "Oil/Gas", 8_200_000),
        ("Vedanta Limited", "Jharsuguda Aluminium Smelter", "Eastern Region", "Coal", 11_600_000),
    ]
    rows = []
    for corp, fac, state, fuel, base_s1 in companies:
        rows.append({
            "market": "IN",
            "corporation_name": corp,
            "facility_name": fac,
            "state": state,
            "scope1_emissions_tco2e": round(base_s1 * rng.uniform(0.92, 1.08)),
            "scope2_emissions_tco2e": round(base_s1 * 0.06 * rng.uniform(0.8, 1.2)),
            "net_energy_consumed_gj": round(base_s1 * 0.014 * rng.uniform(0.9, 1.1)),
            "electricity_production_mwh": round(base_s1 * 0.00028),
            "primary_fuel_source": fuel,
            "reporting_year": "2023-24",
        })
    return pd.DataFrame(rows)


def in_market_notices() -> pd.DataFrame:
    types = ["GRID ALERT", "DEMAND FORECAST ADVISORY", "GENERATION CONSTRAINT",
             "TRANSMISSION CONSTRAINT", "MARKET ADVISORY", "FREQUENCY REGULATION"]
    regions = ["Northern Region", "Western Region", "Southern Region", "Eastern Region", "Northeastern Region"]
    reasons = [
        "POSOCO grid alert: Northern Region frequency below 49.8 Hz — load shedding initiated",
        "IEX day-ahead market clearing: Western Region price INR 12.50/kWh — peak demand event",
        "Transmission corridor constraint: Vindhyachal-Agra 765 kV line outage — 3,500 MW transfer limit",
        "NLDC advisory: monsoon hydropower generation 15% below forecast — thermal backup required",
        "NTPC Vindhyachal Unit 8 forced outage — 500 MW capacity loss Western Region",
        "CERC advisory: renewable energy curtailment in Southern Region — grid absorption constraint",
        "BEE PAT Cycle-III result notification — sector-wise energy saving certificates issued",
        "MNRE advisory: RPO compliance shortfall states — green energy open access facilitation",
        "POSOCO demand alert: Northern Region 19:00-21:00 — reserve margin below 5%",
        "CERC market advisory: cross-border electricity trade rules updated effective April 2025",
        "Grid disturbance report: Western Region — 1,200 MW frequency deviation event 14:23 IST",
        "NLDC notice: Interstate transmission congestion charges — revised allocation method",
        "REC market notice: renewable energy certificate trading session — settlement 14 Jan 2025",
        "IEX advisory: green DAM trading volume record — 3,420 MU in December 2024",
        "CERC order: review of deviation settlement mechanism — public consultation open",
    ]
    rows = []
    for i in range(55):
        rows.append({
            "market": "IN",
            "notice_id": f"IN-MN-{2024000 + i}",
            "notice_type": rng.choice(types),
            "creation_date": datetime.combine(_rand_date(date(2024, 1, 1), date(2025, 3, 31)), datetime.min.time()),
            "issue_date": datetime.combine(_rand_date(date(2024, 1, 1), date(2025, 3, 31)), datetime.min.time()),
            "region": rng.choice(regions),
            "reason": rng.choice(reasons),
            "external_reference": f"CERC-{rng.randint(1000,9999)}/{2024 + rng.randint(0,1)}",
        })
    return pd.DataFrame(rows)


def in_enforcement() -> pd.DataFrame:
    actions = [
        ("Adani Power", "CERC Order", "Tariff Non-Compliance", "Failure to comply with CERC tariff order provisions — excess recovery from beneficiaries", 500_000_000, "Refund ordered", "Electricity Act 2003 s.61"),
        ("Tata Power", "Penalty Order", "RPO Non-Compliance", "Renewable Purchase Obligation shortfall — 1,200 MU renewable energy certificates not purchased", 120_000_000, "Penalty paid + REC purchase completed", "Electricity Act s.86(1)(e)"),
        ("NTPC Limited", "CERC Direction", "Deviation Settlement", "Repeated deviation from approved generation schedule — DSM charges not paid within 30 days", 80_000_000, "DSM charges cleared", "CERC DSM Regulations 2014"),
        ("JSW Energy", "Compliance Notice", "Merit Order Violation", "State SLDC found JSW did not follow merit order dispatch on 8 occasions", 45_000_000, "Compliance report submitted", "Electricity Act s.32"),
        ("Steel Authority of India (SAIL)", "BEE Penalty", "PAT Non-Compliance", "PAT Cycle-II — failed to achieve mandatory energy saving target by 18% shortfall", 35_000_000, "ESCerts purchased", "Energy Conservation Act s.17"),
        ("Indian Oil Corporation", "Penalty Notice", "Environment", "Panipat refinery SO2 emissions exceeded CPCB standards during Q2 2023", 25_000_000, "Flue gas desulfurization installed", "Environment Protection Act Rule 5"),
        ("Reliance Industries", "CERC Investigation", "Market Conduct", "Unusual bidding pattern in real-time market — investigation into potential market power", 0, "Investigation ongoing", "Electricity Act s.60"),
        ("Vedanta Limited", "MoEF Notice", "Environmental Compliance", "Jharsuguda smelter — aluminium fluoride emissions exceeded consent limits", 40_000_000, "Abatement plan filed", "Environment Protection Act s.5"),
        ("Torrent Power", "SERC Order", "Consumer Protection", "Billing irregularities affecting 12,000 industrial consumers — Gujarat SERC investigation", 15_000_000, "Refunds issued", "Electricity Act s.86"),
        ("CESC", "Penalty Order", "Outage Reporting", "Failure to report 3 major supply interruptions to CERC within required 2-hour window", 8_000_000, "Improved reporting protocols", "Electricity Act s.56"),
    ]
    rows = []
    for company, atype, breach, desc, penalty_local, outcome, ref in actions:
        penalty_aud = round(penalty_local * FX_TO_AUD["IN"])
        rows.append({
            "market": "IN",
            "action_id": _uid("IN-ENF"),
            "company_name": company,
            "action_date": _rand_date(date(2019, 1, 1), date(2025, 3, 31)),
            "action_type": atype,
            "breach_type": breach,
            "breach_description": desc,
            "penalty_aud": float(penalty_aud),
            "outcome": outcome,
            "regulatory_reference": ref,
        })
    return pd.DataFrame(rows)


def in_obligations() -> pd.DataFrame:
    rows = [
        ("CERC", "Generation Licence", "Market", "Ongoing", "Critical", 500_000_000, "Electricity Act 2003 s.14", "All generators above 1 MW must obtain generation licence from CERC or respective SERC.", "Apply for licence, comply with Grid Code, report significant operational changes to CERC."),
        ("MNRE", "Renewable Purchase Obligation", "Environment", "Annual", "Critical", 1_000_000_000, "Electricity Act s.86(1)(e)", "Distribution licensees and open access consumers must procure specified % of electricity from renewables.", "Purchase RECs or renewable power to meet RPO targets; file compliance report with SERC."),
        ("BEE", "PAT Scheme Compliance", "Environment", "3-year cycles", "Critical", 200_000_000, "Energy Conservation Act s.14A", "Designated consumers in specified sectors must achieve mandatory energy intensity reduction targets.", "Install metering, appoint energy auditor, achieve target or purchase ESCerts from surplus entities."),
        ("CERC", "Deviation Settlement Mechanism", "Market", "Every 15 minutes", "High", 100_000_000, "CERC DSM Regulations 2014", "All generators and distribution licensees must maintain frequency-linked deviation discipline.", "Monitor real-time deviation, settle DSM charges within 30 days, maintain deviation within ±12%."),
        ("MoPNG", "Petroleum Regulatory Compliance", "Environment", "Annual", "High", 100_000_000, "Petroleum and Natural Gas Regulatory Board Act 2006", "Entities in petroleum midstream/downstream must hold PNGRB licence and comply with technical standards.", "Apply for licence, comply with safety and quality standards, submit annual statutory returns."),
        ("SEBI/MCA", "BRSR Sustainability Reporting", "Financial", "Annual", "Medium", 50_000_000, "Companies Act 2013 / SEBI LODR", "Top 1000 listed companies by market cap must disclose ESG performance in Business Responsibility Report.", "Disclose energy, emissions, water and waste KPIs; obtain independent assurance."),
        ("POSOCO", "Grid Code Compliance", "Technical", "Continuous", "Critical", 200_000_000, "Indian Electricity Grid Code 2010", "All utilities connected to interstate transmission system must comply with IEGC.", "Maintain power factor ≥0.90, comply with frequency regulation obligations, follow RLDC dispatch."),
        ("CPCB", "Environmental Consent", "Environment", "Annual renewal", "High", 100_000_000, "Environment Protection Act 1986", "All thermal power plants must hold valid consent to operate from State Pollution Control Board.", "Comply with emission standards, submit online monitoring data, renew consent annually."),
        ("CERC", "Inter-State Transmission Charges", "Financial", "Monthly", "Medium", 50_000_000, "Electricity Act s.49", "All long-term access holders must pay transmission charges as per CERC tariff orders.", "Pay charges within due date, raise disputes within 90 days, maintain billing records for 7 years."),
        ("BEE", "Energy Conservation Building Code", "Technical", "Ongoing", "Medium", 10_000_000, "Energy Conservation Act s.15", "New commercial buildings above 500 sqm in notified cities must comply with ECBC.", "Design to ECBC standards, obtain BEE star rating, conduct periodic energy audits."),
    ]
    result = []
    for body, name, cat, freq, risk, penalty_local, leg, desc, req in rows:
        result.append({
            "market": "IN",
            "obligation_id": _uid("IN-OBL"),
            "regulatory_body": body,
            "obligation_name": name,
            "category": cat,
            "frequency": freq,
            "risk_rating": risk,
            "penalty_max_aud": round(penalty_local * FX_TO_AUD["IN"]),
            "source_legislation": leg,
            "description": desc,
            "key_requirements": req,
        })
    return pd.DataFrame(result)


# ──────────────────────────────────────────────────────────────────────────────
# SOUTH KOREA
# ──────────────────────────────────────────────────────────────────────────────

def kr_emissions() -> pd.DataFrame:
    companies = [
        ("KEPCO (Korea Electric Power)", "Boryeong Thermal Power", "Chungcheong", "Coal", 18_600_000),
        ("Korea South-East Power (KOEN)", "Samcheonpo Thermal Power", "Gyeongsang", "Coal", 14_200_000),
        ("Korea Midland Power (KOMIPO)", "Boryeong Thermal Units", "Chungcheong", "Coal", 16_800_000),
        ("Korea Western Power (KOWEPO)", "Taean Thermal Power", "Chungcheong", "Coal", 13_400_000),
        ("Korea Southern Power (KOSPO)", "Hadong Thermal Power", "Gyeongsang", "Coal", 12_800_000),
        ("SK E&S", "Gwangyang LNG Power", "Gyeongsang", "LNG", 5_200_000),
        ("GS Energy", "Bucheon LNG Power", "Seoul Metropolitan", "LNG", 3_800_000),
        ("Hanwha Energy", "Pyeongtaek LNG Combined Cycle", "Seoul Metropolitan", "LNG", 4_100_000),
        ("POSCO Holdings", "Pohang Integrated Steelworks", "Gyeongsang", "Coal/Gas", 22_600_000),
        ("Hyundai Steel", "Dangjin Electric Arc Furnace", "Chungcheong", "Electricity/Coal", 8_400_000),
        ("Samsung Electronics", "Hwaseong Semiconductor Fab", "Gyeonggi", "Gas/Electricity", 6_200_000),
        ("SK Hynix", "Icheon Semiconductor Complex", "Gyeonggi", "Gas/Electricity", 5_800_000),
        ("LG Chem", "Daesan Petrochemical", "Chungcheong", "Oil/Gas", 7_600_000),
        ("Lotte Chemical", "Yeosu Petrochemical", "Gyeongsang", "Oil/Gas", 6_400_000),
        ("Hanwha Solutions", "Ulsan Chemical Works", "Gyeongsang", "Oil/Gas", 4_200_000),
    ]
    rows = []
    for corp, fac, state, fuel, base_s1 in companies:
        rows.append({
            "market": "KR",
            "corporation_name": corp,
            "facility_name": fac,
            "state": state,
            "scope1_emissions_tco2e": round(base_s1 * rng.uniform(0.92, 1.08)),
            "scope2_emissions_tco2e": round(base_s1 * 0.05 * rng.uniform(0.8, 1.2)),
            "net_energy_consumed_gj": round(base_s1 * 0.013 * rng.uniform(0.9, 1.1)),
            "electricity_production_mwh": round(base_s1 * 0.00022),
            "primary_fuel_source": fuel,
            "reporting_year": "2023-24",
        })
    return pd.DataFrame(rows)


def kr_market_notices() -> pd.DataFrame:
    types = ["SUPPLY TIGHTNESS ALERT", "DEMAND RESPONSE ACTIVATION", "CAPACITY EMERGENCY",
             "OUTAGE NOTIFICATION", "MARKET ADVISORY", "FREQUENCY REGULATION NOTICE"]
    regions = ["Seoul Metropolitan", "Gangwon", "Chungcheong", "Gyeonggi", "Jeolla", "Gyeongsang", "Jeju"]
    reasons = [
        "KPX supply margin alert: reserve rate 5.1% — demand response program Level 1 activated",
        "Winter peak demand forecast — KPX requesting maximum available generation output",
        "Unplanned outage Korea Midland Power Boryeong Unit 4 — 600 MW loss Chungcheong",
        "Frequency deviation 59.8 Hz — KPX emergency generation activation under KEC rule 5.3",
        "K-ETS annual surrender deadline reminder — MOE KAU surrender by 30 June 2025",
        "Jeju Island isolated grid constraint — interconnector capacity limited to 200 MW",
        "Renewable energy curtailment alert: 480 MW wind curtailed Jeju — grid absorption limit",
        "SMP (System Marginal Price) spike — KPX market price KRW 280/kWh during cold wave",
        "Demand response resource bidding window open — KPX curtailable load program activation",
        "KEPCO advisory: new smart meter rollout delay — settlement data reconciliation required",
        "KPX capacity market notice: new entry capacity eligibility verification deadline",
        "Power System Reliability Management Standard revision — effective Q2 2025",
        "MOTIE advisory: 10th Basic Plan for Electricity Supply public consultation period",
        "Gyeonggi region voltage stability notice — transmission reinforcement under construction",
        "Korea Power Exchange year-ahead adequacy report — FY2026 reserve margin projection 15.2%",
    ]
    rows = []
    for i in range(48):
        rows.append({
            "market": "KR",
            "notice_id": f"KR-MN-{2024000 + i}",
            "notice_type": rng.choice(types),
            "creation_date": datetime.combine(_rand_date(date(2024, 1, 1), date(2025, 3, 31)), datetime.min.time()),
            "issue_date": datetime.combine(_rand_date(date(2024, 1, 1), date(2025, 3, 31)), datetime.min.time()),
            "region": rng.choice(regions),
            "reason": rng.choice(reasons),
            "external_reference": f"KPX-{rng.randint(1000,9999)}-{2024 + rng.randint(0,1)}",
        })
    return pd.DataFrame(rows)


def kr_enforcement() -> pd.DataFrame:
    actions = [
        ("POSCO Holdings", "MOE Penalty Order", "K-ETS Non-Compliance", "Excess emissions beyond allocation — 850,000 KAU shortfall not surrendered by deadline", 8_500_000_000, "Penalty paid + KAUs purchased", "Act on Allocation and Trading of GHG Emission Permits s.34"),
        ("Samsung Electronics", "K-ETS Fine", "Allocation Irregularity", "Incorrect benchmark application for semiconductor process emissions — over-allocation claimed", 3_200_000_000, "Corrected allocation accepted", "GHG Emission Permit Act s.28"),
        ("Korea Midland Power (KOMIPO)", "MOTIE Order", "Capacity Market Breach", "Failure to deliver contracted capacity during peak demand event — 300 MW shortfall", 15_000_000_000, "Penalty paid", "Electric Utility Act s.43"),
        ("SK Hynix", "Compliance Notice", "Energy Efficiency", "Failure to submit energy use rationalization plan by statutory deadline", 500_000_000, "Plan submitted with late filing penalty", "Energy Use Rationalization Act s.14"),
        ("LG Chem", "Court Proceedings", "Environmental Violation", "VOC emissions exceeding permit levels at Daesan complex — Clean Air Conservation Act breach", 2_000_000_000, "Emission abatement equipment installed", "Clean Air Conservation Act s.82"),
        ("Korea Western Power (KOWEPO)", "Penalty Notice", "Generation Reporting", "Inaccurate real-time generation data submitted to KPX on 45 occasions in FY2023", 800_000_000, "Data system upgraded", "Electric Utility Act s.67"),
        ("Hyundai Steel", "K-ETS Audit Finding", "Monitoring Protocol", "Non-compliant emission monitoring equipment — 18-month gap in calibration records", 1_500_000_000, "Calibration completed, records updated", "GHG Emission Permit Act s.22"),
        ("GS Energy", "Administrative Fine", "Market Conduct", "Withholding of LNG generation capacity during tightness event — KPX investigation finding", 2_500_000_000, "Bidding protocol revised", "Electric Utility Act s.21"),
        ("Lotte Chemical", "Compliance Audit", "Industrial Safety", "Process safety management deficiency at Yeosu facility — 12 items identified", 600_000_000, "Corrective action plan completed", "Industrial Safety and Health Act"),
        ("Hanwha Energy", "MOTIE Advisory", "Renewable Obligation", "RPS (Renewable Portfolio Standard) obligation — 2.3% shortfall in REC submission", 1_200_000_000, "REC certificates purchased", "Electric Utility Act s.46a"),
    ]
    rows = []
    for company, atype, breach, desc, penalty_local, outcome, ref in actions:
        penalty_aud = round(penalty_local * FX_TO_AUD["KR"])
        rows.append({
            "market": "KR",
            "action_id": _uid("KR-ENF"),
            "company_name": company,
            "action_date": _rand_date(date(2019, 1, 1), date(2025, 3, 31)),
            "action_type": atype,
            "breach_type": breach,
            "breach_description": desc,
            "penalty_aud": float(penalty_aud),
            "outcome": outcome,
            "regulatory_reference": ref,
        })
    return pd.DataFrame(rows)


def kr_obligations() -> pd.DataFrame:
    rows = [
        ("MOTIE", "Electricity Business Licence", "Market", "Ongoing", "Critical", 30_000_000_000, "Electric Utility Act s.7", "All electricity generators and traders must hold MOTIE licence.", "Apply for licence, maintain technical standards, report significant changes to MOTIE within 30 days."),
        ("MOE", "K-ETS Participation", "Environment", "Annual (30 June)", "Critical", 10_000_000_000, "Act on Allocation and Trading of GHG Emission Permits s.8", "Entities in covered sectors (≥125,000 tCO2/yr) must participate in Korean ETS.", "Receive allocation, monitor emissions, surrender KAUs by 30 June, report verified emissions by 31 March."),
        ("MOE", "GHG Monitoring & Verification", "Environment", "Annual", "Critical", 5_000_000_000, "GHG Emissions Trading Act s.22", "K-ETS participants must monitor emissions and obtain third-party verification.", "Install approved monitoring equipment, conduct annual verification, submit to MOE."),
        ("KEA", "Energy Use Rationalization", "Environment", "Annual", "High", 1_000_000_000, "Energy Use Rationalization Act s.14", "Designated energy users (≥2,000 TOE/yr) must submit energy usage rationalization plan.", "Appoint certified energy manager, submit annual plan and report, achieve mandated efficiency improvements."),
        ("MOTIE", "Renewable Portfolio Standard", "Environment", "Annual", "High", 5_000_000_000, "Electric Utility Act s.46a", "Electricity suppliers above threshold must submit REC certificates equal to RPS quota (2024: 13%).", "Purchase RECs or self-generate, submit compliance report to MOTIE by 31 March."),
        ("KPX", "Capacity Market Obligation", "Market", "Annual auction", "Critical", 20_000_000_000, "Electric Utility Act s.43", "All generation capacity must participate in capacity market or hold exemption.", "Submit capacity bid, maintain availability, pay penalty for non-delivery during capacity delivery year."),
        ("KPX", "Real-time Market Compliance", "Market", "Continuous", "High", 3_000_000_000, "Electric Utility Act s.21", "All market participants must comply with KPX market rules on bidding and dispatch.", "Submit timely bids, comply with dispatch instructions, avoid market manipulation."),
        ("MOTIE", "New and Renewable Energy Act", "Environment", "Per project", "Medium", 500_000_000, "New and Renewable Energy Act s.12", "Mandatory REC certification for all renewable generation above 500 kW.", "Register with KEA, obtain REC issuance, transact through KPX REC market."),
        ("MOTIE", "Electricity Supply Plan", "Technical", "Bi-annual", "Medium", 1_000_000_000, "Electric Utility Act s.25", "KEPCO must publish 15-year electricity supply plan and comply with approved plan.", "Submit plan for MOTIE approval, implement capacity additions on schedule."),
        ("MOE", "Environmental Impact Assessment", "Environment", "Per project", "High", 2_000_000_000, "Environmental Impact Assessment Act", "All new power plants above 10 MW require environmental impact assessment approval.", "Conduct EIA, obtain MOE approval before construction, implement mitigation measures."),
    ]
    result = []
    for body, name, cat, freq, risk, penalty_local, leg, desc, req in rows:
        result.append({
            "market": "KR",
            "obligation_id": _uid("KR-OBL"),
            "regulatory_body": body,
            "obligation_name": name,
            "category": cat,
            "frequency": freq,
            "risk_rating": risk,
            "penalty_max_aud": round(penalty_local * FX_TO_AUD["KR"]),
            "source_legislation": leg,
            "description": desc,
            "key_requirements": req,
        })
    return pd.DataFrame(result)


# ──────────────────────────────────────────────────────────────────────────────
# THAILAND
# ──────────────────────────────────────────────────────────────────────────────

def th_emissions() -> pd.DataFrame:
    companies = [
        ("EGAT", "Mae Moh Lignite Power", "Northern", "Lignite", 16_200_000),
        ("EGAT", "Bang Pakong Combined Cycle", "Central", "Gas", 6_800_000),
        ("GULF Energy Development", "GSRC Combined Cycle", "Eastern", "Gas", 8_200_000),
        ("B.Grimm Power", "Amata B.Grimm Power", "Eastern", "Gas", 5_400_000),
        ("Global Power Synergy (GPSC)", "IRPC Clean Power", "Eastern", "Gas", 4_600_000),
        ("RATCH Group", "RATCH Ratchaburi Power", "Central", "Gas", 7_100_000),
        ("Banpu Power", "BLCP Coal Power", "Eastern", "Coal", 9_800_000),
        ("WHA Utilities and Power", "Hemaraj Eastern Seaboard Power", "Eastern", "Gas", 3_200_000),
        ("PTT Global Chemical", "Rayong Petrochemical Complex", "Eastern", "Oil/Gas", 7_600_000),
        ("PTT Public Company", "PTT LNG Terminal Map Ta Phut", "Eastern", "Gas", 4_100_000),
        ("Thai Oil", "Sriracha Refinery", "Eastern", "Oil", 5_800_000),
        ("IRPC", "Rayong Integrated Refinery", "Eastern", "Oil", 4_200_000),
        ("SCG Chemicals", "Map Ta Phut Olefins", "Eastern", "Gas/Oil", 6_400_000),
        ("Indorama Ventures", "TPT Petrochemicals", "Eastern", "Gas", 3_600_000),
        ("Siam Cement Group", "Kaeng Khoi Cement Plant", "Central", "Coal/Biomass", 2_800_000),
    ]
    rows = []
    for corp, fac, state, fuel, base_s1 in companies:
        rows.append({
            "market": "TH",
            "corporation_name": corp,
            "facility_name": fac,
            "state": state,
            "scope1_emissions_tco2e": round(base_s1 * rng.uniform(0.92, 1.08)),
            "scope2_emissions_tco2e": round(base_s1 * 0.07 * rng.uniform(0.8, 1.2)),
            "net_energy_consumed_gj": round(base_s1 * 0.016 * rng.uniform(0.9, 1.1)),
            "electricity_production_mwh": round(base_s1 * 0.00030),
            "primary_fuel_source": fuel,
            "reporting_year": "2023-24",
        })
    return pd.DataFrame(rows)


def th_market_notices() -> pd.DataFrame:
    types = ["GENERATION ADVISORY", "DEMAND MANAGEMENT NOTICE", "OUTAGE NOTIFICATION",
             "CAPACITY ALERT", "MARKET ADVISORY", "ENVIRONMENTAL NOTICE"]
    regions = ["Central", "Northern", "Northeastern", "Eastern", "Southern"]
    reasons = [
        "EGAT system advisory: Mae Moh lignite unit scheduled maintenance — 800 MW capacity reduction",
        "Peak demand forecast Central region 31,500 MW — EGAT requesting demand response activation",
        "Natural gas supply interruption Gulf of Thailand field — EGAT fuel switching to oil",
        "Drought condition: Bhumibol dam inflow 40% below average — hydro generation limited",
        "ERC notice: solar rooftop tariff revision effective 1 April 2025",
        "T-VER project registration window open — TGO voluntary carbon standard submission",
        "EGAT Bang Pakong unit outage — combined cycle maintenance 10-24 March 2025",
        "Southern Thailand grid constraint — interconnector capacity limited after transmission fault",
        "EGAT advisory: renewable energy forecast deviation >15% — backup thermal dispatch",
        "ERC public hearing: PDP 2024 power development plan consultation open",
        "Carbon footprint disclosure deadline — TEI (Thailand Environment Institute) submission",
        "Map Ta Phut industrial estate load shedding schedule — IEAT coordination notice",
        "EGAT tender notice: solar plus storage project 3,000 MW round 2 bidding",
        "Peak season electricity conservation campaign — ERC public advisory",
        "Floating solar Sirindhorn dam project commissioning — 45 MW new generation online",
    ]
    rows = []
    for i in range(42):
        rows.append({
            "market": "TH",
            "notice_id": f"TH-MN-{2024000 + i}",
            "notice_type": rng.choice(types),
            "creation_date": datetime.combine(_rand_date(date(2024, 1, 1), date(2025, 3, 31)), datetime.min.time()),
            "issue_date": datetime.combine(_rand_date(date(2024, 1, 1), date(2025, 3, 31)), datetime.min.time()),
            "region": rng.choice(regions),
            "reason": rng.choice(reasons),
            "external_reference": f"ERC-{rng.randint(1000,9999)}/{2024 + rng.randint(0,1)}",
        })
    return pd.DataFrame(rows)


def th_enforcement() -> pd.DataFrame:
    actions = [
        ("Banpu Power", "ERC Penalty Order", "Licence Condition Breach", "BLCP coal power plant emissions exceeded permitted SO2 levels by 35% in Q2 2023", 50_000_000, "Penalty paid, FGD system upgraded", "Energy Industry Act B.E. 2550 s.92"),
        ("PTT Global Chemical", "MoI Enforcement Order", "Environmental Violation", "Map Ta Phut facility VOC emissions exceeded EIA conditions — community health complaints", 30_000_000, "VOC abatement system installed", "Factory Act s.37"),
        ("GULF Energy Development", "ERC Investigation", "Power Purchase Agreement", "Alleged breach of PPA availability guarantee — below minimum 92% availability threshold", 0, "Investigation ongoing, arbitration pending", "ERC Energy Industry Act s.71"),
        ("Thai Oil", "ONEP Notice", "Environmental Compliance", "Refinery stormwater runoff — petroleum hydrocarbon contamination in drainage canal", 20_000_000, "Remediation completed", "Hazardous Substances Act s.22"),
        ("Siam Cement Group", "DIW Penalty", "Air Emissions", "Kaeng Khoi plant PM10 emissions above permitted level — stack testing failure", 15_000_000, "Baghouse filter replaced", "Factory Act B.E. 2535 s.32"),
        ("RATCH Group", "ERC Compliance Order", "Grid Code Breach", "Reactive power support non-compliance at Ratchaburi substation — voltage deviation", 8_000_000, "Power factor compensation installed", "ERC Grid Code s.4.2"),
        ("B.Grimm Power", "IEAT Notice", "Industrial Estate Compliance", "Wastewater treatment plant effluent quality below IEAT standards in Q4 2024", 5_000_000, "WWTP upgraded", "IEAT Act s.46"),
        ("PTT Public Company", "TGO Notice", "Carbon Footprint", "Failure to submit corporate carbon footprint report by TGO deadline for 3 consecutive years", 3_000_000, "Report submitted with penalty", "Energy Industry Act s.97"),
        ("WHA Utilities and Power", "ERC Order", "Tariff Compliance", "Industrial customer billing error — overcharging discovered in ERC audit", 12_000_000, "Refunds issued to affected customers", "Energy Industry Act s.83"),
        ("SCG Chemicals", "ONEP Compliance", "Environmental Impact", "EIA follow-up monitoring reports submitted 6 months late for Map Ta Phut expansion", 4_000_000, "Monitoring reporting schedule corrected", "Enhancement of National Environmental Quality Act s.48"),
    ]
    rows = []
    for company, atype, breach, desc, penalty_local, outcome, ref in actions:
        penalty_aud = round(penalty_local * FX_TO_AUD["TH"])
        rows.append({
            "market": "TH",
            "action_id": _uid("TH-ENF"),
            "company_name": company,
            "action_date": _rand_date(date(2019, 1, 1), date(2025, 3, 31)),
            "action_type": atype,
            "breach_type": breach,
            "breach_description": desc,
            "penalty_aud": float(penalty_aud),
            "outcome": outcome,
            "regulatory_reference": ref,
        })
    return pd.DataFrame(rows)


def th_obligations() -> pd.DataFrame:
    rows = [
        ("ERC", "Power Generation Licence", "Market", "Ongoing", "Critical", 200_000_000, "Energy Industry Act B.E. 2550 s.47", "All power generators must obtain ERC licence before commercial operation.", "Apply for licence, comply with technical and environmental conditions, renew every 5 years."),
        ("ERC", "PPA Compliance", "Market", "Continuous", "Critical", 500_000_000, "Energy Industry Act s.71", "IPPs must comply with Power Purchase Agreement terms including availability guarantees.", "Maintain minimum 92% availability, submit monthly generation reports, notify EGAT of planned outages 30 days in advance."),
        ("EGAT", "Grid Code Compliance", "Technical", "Continuous", "High", 100_000_000, "EGAT Grid Code", "All grid-connected generators must comply with EGAT Grid Code technical requirements.", "Maintain power factor ≥0.85, comply with voltage and frequency tolerance, provide reactive power support."),
        ("TGO", "T-VER Carbon Registration", "Environment", "Per project", "Medium", 10_000_000, "Energy Industry Act s.97", "Companies seeking voluntary carbon credits must register T-VER projects with TGO.", "Submit project design document, obtain validation, monitor and verify emission reductions annually."),
        ("DIW", "Factory Licence & EIA", "Environment", "Annual renewal", "High", 50_000_000, "Factory Act B.E. 2535", "All energy facilities classified as controlled factories must hold valid DIW factory licence.", "Comply with emission standards, submit annual environmental monitoring reports, renew licence annually."),
        ("ONEP", "Environmental Impact Assessment", "Environment", "Per project", "Critical", 100_000_000, "Enhancement of National Environmental Quality Act s.46", "Energy projects above threshold size require ONEP EIA approval before construction.", "Conduct EIA study, obtain approval, implement mitigation measures, submit monitoring reports."),
        ("ERC", "Renewable Energy Policy", "Market", "Per contract", "Medium", 50_000_000, "Energy Industry Act s.89", "Renewable energy generators must comply with ERC VSPP/SPP programme requirements.", "Meet technical standards, comply with grid connection requirements, submit generation data to EGAT."),
        ("MOE/ONEP", "Carbon Footprint Disclosure", "Environment", "Annual", "Medium", 5_000_000, "Government policy (voluntary-mandatory transition)", "Large industrial facilities are encouraged (and increasingly required) to disclose carbon footprints.", "Calculate GHG inventory per ISO 14064, submit to TGO database, publish in sustainability report."),
        ("IEAT", "Industrial Estate Environmental", "Environment", "Annual", "High", 20_000_000, "IEAT Act B.E. 2522", "Facilities in industrial estates must comply with IEAT environmental standards.", "Comply with IEAT air, water and waste standards, submit quarterly monitoring data."),
        ("ERC", "Electricity Metering Standards", "Technical", "Continuous", "Medium", 10_000_000, "ERC Metering Regulation", "All electricity generators and consumers above threshold must install ERC-approved metering.", "Install approved meters, calibrate annually, submit meter data to EGAT within required periods."),
    ]
    result = []
    for body, name, cat, freq, risk, penalty_local, leg, desc, req in rows:
        result.append({
            "market": "TH",
            "obligation_id": _uid("TH-OBL"),
            "regulatory_body": body,
            "obligation_name": name,
            "category": cat,
            "frequency": freq,
            "risk_rating": risk,
            "penalty_max_aud": round(penalty_local * FX_TO_AUD["TH"]),
            "source_legislation": leg,
            "description": desc,
            "key_requirements": req,
        })
    return pd.DataFrame(result)


# ──────────────────────────────────────────────────────────────────────────────
# PHILIPPINES
# ──────────────────────────────────────────────────────────────────────────────

def ph_emissions() -> pd.DataFrame:
    companies = [
        ("Meralco (Manila Electric Company)", "Meralco Sucat Power Plant", "Luzon", "Oil/Gas", 1_200_000),
        ("First Gen Corporation", "Santa Rita Gas Plant", "Luzon", "Gas", 3_800_000),
        ("First Gen Corporation", "San Gabriel Gas Plant", "Luzon", "Gas", 2_400_000),
        ("San Miguel Energy", "Malita Power Plant", "Mindanao", "Coal", 4_200_000),
        ("Aboitiz Power", "Therma Visayas Coal Power", "Visayas", "Coal", 6_800_000),
        ("SN Aboitiz Power", "Magat Hydroelectric", "Luzon", "Hydro", 68_000),
        ("Energy Development Corporation (EDC)", "Leyte Geothermal", "Visayas", "Geothermal", 580_000),
        ("Global Business Power", "Toledo Power Plant", "Visayas", "Coal", 3_200_000),
        ("ACEN Corporation", "South Luzon Thermal", "Luzon", "Coal", 5_100_000),
        ("Therma South", "Davao Coal Power Plant", "Mindanao", "Coal", 4_600_000),
        ("Semirara Mining and Power", "Calaca Power Plant", "Luzon", "Coal", 7_200_000),
        ("Masinloc Power Partners", "Masinloc Coal Power", "Luzon", "Coal", 5_800_000),
        ("Alsons Power", "Sarangani Energy", "Mindanao", "Coal", 2_800_000),
        ("Trans-Asia Oil & Energy", "Trans-Asia Bataan", "Luzon", "Oil", 1_600_000),
        ("Philippine Geothermal Production Company", "Tiwi Geothermal", "Luzon", "Geothermal", 420_000),
    ]
    rows = []
    for corp, fac, state, fuel, base_s1 in companies:
        rows.append({
            "market": "PH",
            "corporation_name": corp,
            "facility_name": fac,
            "state": state,
            "scope1_emissions_tco2e": round(base_s1 * rng.uniform(0.92, 1.08)),
            "scope2_emissions_tco2e": round(base_s1 * 0.06 * rng.uniform(0.8, 1.2)),
            "net_energy_consumed_gj": round(base_s1 * 0.017 * rng.uniform(0.9, 1.1)),
            "electricity_production_mwh": round(base_s1 * 0.00032),
            "primary_fuel_source": fuel,
            "reporting_year": "2023-24",
        })
    return pd.DataFrame(rows)


def ph_market_notices() -> pd.DataFrame:
    types = ["OUTAGE NOTICE", "CAPACITY DEFICIENCY ALERT", "PRICE SPIKE ADVISORY",
             "DEMAND RESPONSE NOTICE", "REGULATORY ADVISORY", "SYSTEM ADVISORY"]
    regions = ["Luzon", "Visayas", "Mindanao"]
    reasons = [
        "IEMOP Luzon grid: Semirara Calaca Unit 2 unplanned outage — 350 MW loss effective 08:00 PHT",
        "Luzon grid capacity deficiency alert — reserve margin below 600 MW threshold as of 14:00",
        "WESM price spike PHP 62.00/kWh Luzon node — tight supply conditions hot season peak",
        "Mindanao grid: insufficient capacity — load shedding schedule issued by NGCP",
        "ERC advisory: Feed-in Tariff rate revision for wind energy effective June 2025",
        "DOE circular: mandatory RCOA (Retail Competition and Open Access) for 1 MW+ consumers",
        "IEMOP notice: Visayas grid — EDC Leyte geothermal output reduced maintenance window",
        "Luzon grid demand response activation — NGCP requesting load reduction from DR providers",
        "Philippine Clean Air Act compliance deadline — DOE reminder to coal plant operators",
        "WESM rule change: secondary registration deadline for trading participants March 31",
        "Mindanao power situation update: Pulangi hydro below critical level — 200 MW reduction",
        "IEMOP: WESM trading floor price review effective Q2 2025 — ERC consultation complete",
        "RE Act certificate issuance: 45 new solar projects registered — COC certificates released",
        "NGCP transmission line outage: Tayabas-Batangas 230 kV — Luzon south area advisory",
        "DOE advisory: coal power phasedown policy consultation — public comments invited",
    ]
    rows = []
    for i in range(45):
        rows.append({
            "market": "PH",
            "notice_id": f"PH-MN-{2024000 + i}",
            "notice_type": rng.choice(types),
            "creation_date": datetime.combine(_rand_date(date(2024, 1, 1), date(2025, 3, 31)), datetime.min.time()),
            "issue_date": datetime.combine(_rand_date(date(2024, 1, 1), date(2025, 3, 31)), datetime.min.time()),
            "region": rng.choice(regions),
            "reason": rng.choice(reasons),
            "external_reference": f"ERC-{rng.randint(1000,9999)}/{2024 + rng.randint(0,1)}",
        })
    return pd.DataFrame(rows)


def ph_enforcement() -> pd.DataFrame:
    actions = [
        ("Meralco (Manila Electric Company)", "ERC Order", "Consumer Protection", "Over-recovery of distribution charge — PHP 2.1 billion excess collection from consumers 2021-23", 2_100_000_000, "Refund ordered to consumers", "EPIRA s.43 / ERC Resolution 09-2003"),
        ("Aboitiz Power", "ERC Penalty", "Renewable Portfolio Standard", "RPS obligation shortfall — 1,450 MWh of RECs not surrendered by ERC deadline", 50_000_000, "RECs purchased and surrendered", "RE Act s.6 / ERC Resolution 09-2020"),
        ("Semirara Mining and Power", "DENR Order", "Air Quality Violation", "Calaca plant particulate matter exceeding Clean Air Act standards — DENR stack testing", 30_000_000, "ESP upgrades completed", "Clean Air Act s.45"),
        ("San Miguel Energy", "ERC Compliance Order", "WESM Non-Compliance", "Trading participant failed to comply with 10-day settlement payment obligation", 15_000_000, "Settlement amount paid with interest", "WESM Rules s.8.4"),
        ("ACEN Corporation", "ERC Investigation", "Market Manipulation", "Investigation into coordinated bidding in WESM during Luzon capacity deficiency event", 0, "Investigation ongoing", "EPIRA s.45 / ERC"),
        ("Global Business Power", "DENR Compliance Order", "Environmental", "Sulfur dioxide emissions exceeded permit limits — 4 exceedances in FY2023", 20_000_000, "FGD system upgraded", "Clean Air Act Rules and Regulations"),
        ("Trans-Asia Oil & Energy", "ERC Order", "Licence Compliance", "Failure to renew generation licence — operating without valid licence for 45 days", 8_000_000, "Licence renewed, penalty paid", "EPIRA s.29"),
        ("First Gen Corporation", "DOE Notice", "Emergency Protocol", "Failure to comply with DOE demand supply outlook — insufficient gas inventory disclosure", 5_000_000, "Disclosure protocol updated", "DOE Circular 2023-06-0019"),
        ("Therma South", "ERC Order", "RPS Obligation", "Mindanao grid RPS shortfall — renewable energy certificates not procured for FY2022", 12_000_000, "Compliance plan approved", "RE Act s.6"),
        ("Philippine Geothermal Production Company", "DOE Compliance", "Service Contract", "Service contract reporting obligations not met — delayed submission of annual work programme", 3_000_000, "Reports submitted, compliance restored", "DOE SC Regulations s.12"),
    ]
    rows = []
    for company, atype, breach, desc, penalty_local, outcome, ref in actions:
        penalty_aud = round(penalty_local * FX_TO_AUD["PH"])
        rows.append({
            "market": "PH",
            "action_id": _uid("PH-ENF"),
            "company_name": company,
            "action_date": _rand_date(date(2019, 1, 1), date(2025, 3, 31)),
            "action_type": atype,
            "breach_type": breach,
            "breach_description": desc,
            "penalty_aud": float(penalty_aud),
            "outcome": outcome,
            "regulatory_reference": ref,
        })
    return pd.DataFrame(rows)


def ph_obligations() -> pd.DataFrame:
    rows = [
        ("DOE", "Generation Licence (COC)", "Market", "Ongoing", "Critical", 500_000_000, "EPIRA RA 9136 s.29", "All power generation companies must obtain Certificate of Compliance (COC) from DOE.", "Apply for COC, comply with technical standards, renew every 5 years, report significant changes."),
        ("IEMOP", "WESM Registration", "Market", "Ongoing", "Critical", 100_000_000, "WESM Rules s.2.3", "All generators and loads above threshold must register as WESM trading participants.", "Submit registration, maintain technical compliance, comply with WESM dispatch and settlement rules."),
        ("ERC", "Renewable Portfolio Standard", "Environment", "Annual", "Critical", 200_000_000, "RE Act s.6 / ERC Resolution", "Distribution utilities, electric cooperatives and RES must procure minimum % of supply from renewables.", "Purchase Green Energy Option RECs, surrender by ERC deadline, submit annual compliance report."),
        ("DENR", "Clean Air Act Compliance", "Environment", "Continuous", "Critical", 300_000_000, "Clean Air Act RA 8749 s.45", "All stationary sources must comply with DENR emission standards and hold valid permits.", "Install monitoring equipment, conduct stack testing annually, renew permit every 2 years."),
        ("ERC", "Distribution Wheeling Charges", "Financial", "Ongoing", "High", 500_000_000, "EPIRA s.43", "Distribution utilities must charge only ERC-approved distribution wheeling rates.", "Apply for rate case, implement approved rates, submit annual true-up filing to ERC."),
        ("DOE", "RE Act Incentives Compliance", "Environment", "Per project", "Medium", 50_000_000, "RE Act RA 9513 s.15", "RE developers receiving fiscal incentives must comply with RE development obligations.", "Meet project milestones, report to DOE annually, maintain RE developer accreditation."),
        ("NGCP", "Grid Code Compliance", "Technical", "Continuous", "High", 100_000_000, "Philippine Grid Code", "All transmission-connected generators must comply with Philippine Grid Code.", "Comply with voltage and frequency requirements, provide reactive power support, respond to NGCP dispatching."),
        ("ERC", "WESM Market Conduct", "Market", "Continuous", "Critical", 200_000_000, "EPIRA s.45", "All WESM participants must avoid anti-competitive conduct and market manipulation.", "Comply with offer capping rules, cooperate with ERC market surveillance, maintain trading records 7 years."),
        ("DOE", "Demand Supply Outlook Reporting", "Market", "Quarterly", "Medium", 10_000_000, "DOE Circular 2023-06-0019", "Generation companies must disclose fuel inventory and plant availability quarterly.", "Submit quarterly reports to DOE, disclose emergency fuel inventory, cooperate with DOE audits."),
        ("LGU/DENR", "Environmental Compliance Certificate", "Environment", "Per project", "High", 50_000_000, "IPAM Law / ECC Rules", "All energy projects require Environmental Compliance Certificate before construction.", "Conduct EIS, obtain DENR ECC approval, implement environmental management plan, submit monitoring reports."),
    ]
    result = []
    for body, name, cat, freq, risk, penalty_local, leg, desc, req in rows:
        result.append({
            "market": "PH",
            "obligation_id": _uid("PH-OBL"),
            "regulatory_body": body,
            "obligation_name": name,
            "category": cat,
            "frequency": freq,
            "risk_rating": risk,
            "penalty_max_aud": round(penalty_local * FX_TO_AUD["PH"]),
            "source_legislation": leg,
            "description": desc,
            "key_requirements": req,
        })
    return pd.DataFrame(result)


# ──────────────────────────────────────────────────────────────────────────────
# Master generator
# ──────────────────────────────────────────────────────────────────────────────

REGION_GENERATORS = {
    "SG": (sg_emissions, sg_market_notices, sg_enforcement, sg_obligations),
    "NZ": (nz_emissions, nz_market_notices, nz_enforcement, nz_obligations),
    "JP": (jp_emissions, jp_market_notices, jp_enforcement, jp_obligations),
    "IN": (in_emissions, in_market_notices, in_enforcement, in_obligations),
    "KR": (kr_emissions, kr_market_notices, kr_enforcement, kr_obligations),
    "TH": (th_emissions, th_market_notices, th_enforcement, th_obligations),
    "PH": (ph_emissions, ph_market_notices, ph_enforcement, ph_obligations),
}


def get_all_region_data(markets: list[str] | None = None) -> dict[str, dict[str, pd.DataFrame]]:
    """
    Generate data for specified markets (or all if None).
    Returns: {market_code: {table_name: DataFrame}}
    """
    target = markets or list(REGION_GENERATORS.keys())
    result = {}
    for market in target:
        if market not in REGION_GENERATORS:
            continue
        em, mn, en, ob = REGION_GENERATORS[market]
        result[market] = {
            "emissions": em(),
            "notices": mn(),
            "enforcement": en(),
            "obligations": ob(),
        }
    return result

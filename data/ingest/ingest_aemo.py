"""
Ingest AEMO market notices from NEMWeb.
Downloads notice files from the public AEMO directory listing and parses structured text.
"""

import logging
import re
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

NEMWEB_NOTICES_URL = "https://www.nemweb.com.au/REPORTS/CURRENT/Market_Notice/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Databricks-Energy-Compliance-Hub/1.0; research)"
}

# Limit how many notices we download in one batch
MAX_NOTICES = 2000


def _get_notice_file_links(base_url: str = NEMWEB_NOTICES_URL) -> list[str]:
    """Parse NEMWeb directory listing to get individual notice file URLs."""
    try:
        resp = requests.get(base_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.endswith(".txt") or href.endswith(".csv"):
                if not href.startswith("http"):
                    href = base_url.rstrip("/") + "/" + href
                links.append(href)
        logger.info(f"Found {len(links)} notice files on NEMWeb")
        return links[:MAX_NOTICES]
    except Exception as e:
        logger.error(f"Failed to list NEMWeb notices: {e}")
        return []


def _parse_notice_text(text: str) -> dict | None:
    """Parse a single AEMO market notice from structured text format.

    AEMO notices typically have key-value pairs like:
    Notice ID: 12345
    Notice Type ID: NON-CONFORMANCE
    Creation Date: 2024/01/15 10:30:00
    ...
    Reason: <description text>
    """
    record = {}

    # Extract key-value pairs
    patterns = {
        "notice_id": r"Notice\s*ID\s*[:\-]\s*(\d+)",
        "notice_type": r"(?:Notice\s*Type(?:\s*ID)?|Type)\s*[:\-]\s*(.+?)(?:\n|$)",
        "creation_date": r"Creation\s*Date\s*[:\-]\s*(.+?)(?:\n|$)",
        "issue_date": r"Issue\s*Date\s*[:\-]\s*(.+?)(?:\n|$)",
        "external_reference": r"External\s*Reference\s*[:\-]\s*(.+?)(?:\n|$)",
        "reason": r"Reason\s*[:\-]\s*([\s\S]+?)(?:(?:\n\s*\n)|$)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            record[key] = match.group(1).strip()

    if not record.get("notice_id"):
        return None

    # Parse dates
    for date_field in ["creation_date", "issue_date"]:
        if record.get(date_field):
            for fmt in ["%Y/%m/%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"]:
                try:
                    record[date_field] = datetime.strptime(record[date_field], fmt)
                    break
                except ValueError:
                    continue

    # Extract region from notice text
    region_pattern = r"(NSW1|VIC1|QLD1|SA1|TAS1|NSW|VIC|QLD|SA|TAS)"
    region_match = re.search(region_pattern, text, re.IGNORECASE)
    record["region"] = region_match.group(1).upper() if region_match else "NEM"

    # Classify notice type if not explicitly stated
    if record.get("notice_type"):
        notice_type = record["notice_type"].upper()
        if "NON-CONFORMANCE" in notice_type or "NON CONFORMANCE" in notice_type:
            record["notice_type"] = "NON-CONFORMANCE"
        elif "RECLASSIF" in notice_type:
            record["notice_type"] = "RECLASSIFY"
        elif "SUSPEND" in notice_type:
            record["notice_type"] = "MARKET SUSPENSION"
        elif "INTER-REGIONAL" in notice_type or "INTERCONNECT" in notice_type:
            record["notice_type"] = "INTER-REGIONAL TRANSFER"
        elif "PRICE" in notice_type:
            record["notice_type"] = "PRICES UNCHANGED"
        elif "DIRECTION" in notice_type:
            record["notice_type"] = "DIRECTION"
        elif "RESERVE" in notice_type or "LOR" in notice_type:
            record["notice_type"] = "RESERVE NOTICE"

    return record


def ingest_market_notices() -> pd.DataFrame:
    """Download and parse AEMO market notices."""
    logger.info("Fetching AEMO market notice file list...")
    links = _get_notice_file_links()

    if not links:
        logger.warning("No notice files found on NEMWeb, using fallback data")
        return _generate_aemo_fallback()

    records = []
    errors = 0
    for i, url in enumerate(links):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            record = _parse_notice_text(resp.text)
            if record:
                records.append(record)
        except Exception:
            errors += 1
            if errors > 50:
                logger.warning(f"Too many download errors ({errors}), stopping early")
                break

        if (i + 1) % 100 == 0:
            logger.info(f"Processed {i + 1}/{len(links)} notice files ({len(records)} parsed)")

    if not records:
        logger.warning("No notices parsed successfully, using fallback data")
        return _generate_aemo_fallback()

    df = pd.DataFrame(records)
    logger.info(f"Parsed {len(df)} AEMO market notices")
    return df


def _generate_aemo_fallback() -> pd.DataFrame:
    """Generate realistic fallback AEMO notice data based on real notice patterns."""
    import random

    random.seed(42)

    notice_types = [
        ("NON-CONFORMANCE", 35),
        ("RECLASSIFY", 25),
        ("INTER-REGIONAL TRANSFER", 15),
        ("RESERVE NOTICE", 10),
        ("DIRECTION", 8),
        ("PRICES UNCHANGED", 5),
        ("MARKET SUSPENSION", 2),
    ]
    types_flat = []
    for t, weight in notice_types:
        types_flat.extend([t] * weight)

    regions = ["NSW1", "VIC1", "QLD1", "SA1", "TAS1"]
    region_weights = [30, 25, 25, 15, 5]

    reason_templates = {
        "NON-CONFORMANCE": [
            "Unit {unit} at {station} is non-conforming. The unit is not following dispatch targets. AEMO is investigating.",
            "Generator {unit} at {station} has been operating outside its dispatch target by more than the conformance tolerance.",
            "AEMO has detected non-conformance at {station} unit {unit}. The participant has been notified and corrective action requested.",
        ],
        "RECLASSIFY": [
            "AEMO has reclassified the contingency event of the trip of {station} as a credible contingency event for the {region} region.",
            "The {line} interconnector has been reclassified due to bushfire risk. Transfer limit reduced.",
            "Reclassification of {station} trip as credible due to severe weather conditions in the {region} region.",
        ],
        "INTER-REGIONAL TRANSFER": [
            "Inter-regional transfer limit on {line} has been revised due to network constraints.",
            "The transfer limit on the {line} interconnector has been updated. New limit: {limit}MW.",
        ],
        "RESERVE NOTICE": [
            "AEMO declares Lack of Reserve 1 (LOR1) condition in the {region} region. Forecast reserve deficit at {time}.",
            "AEMO declares Lack of Reserve 2 (LOR2) condition in the {region} region. Minimum reserve margin breach expected.",
            "LOR1 condition cancelled for {region} region. Reserve levels have returned to normal.",
        ],
        "DIRECTION": [
            "AEMO has issued a direction to {station} to maintain output for system security in the {region} region.",
            "Direction issued to maintain minimum generation levels at {station} for voltage support.",
        ],
        "PRICES UNCHANGED": [
            "Intervention pricing — prices for the {region} region have been set at the same level as the previous dispatch interval.",
        ],
        "MARKET SUSPENSION": [
            "Market suspension pricing schedule activated for the {region} region due to sustained pricing anomalies.",
        ],
    }

    stations = [
        "Bayswater", "Loy Yang A", "Eraring", "Yallourn", "Stanwell",
        "Callide B", "Tarong", "Vales Point", "Mount Piper", "Millmerran",
        "Torrens Island", "Pelican Point", "Kogan Creek", "Liddell",
        "Collie", "Muja", "Gladstone", "Tallawarra", "Mortlake",
        "Loy Yang B", "Colongra", "Uranquinty", "Darling Downs",
    ]
    lines = [
        "VIC-NSW", "QLD-NSW", "VIC-SA", "Basslink (VIC-TAS)", "Terranora (NSW-QLD)",
        "Heywood (VIC-SA)", "Murraylink (VIC-SA)",
    ]
    units = ["Unit 1", "Unit 2", "Unit 3", "Unit 4", "GT1", "GT2"]

    records = []
    base_id = 120000
    start_date = datetime(2024, 1, 1)

    for i in range(800):
        notice_type = random.choice(types_flat)
        region = random.choices(regions, weights=region_weights, k=1)[0]
        station = random.choice(stations)
        line = random.choice(lines)
        unit = random.choice(units)

        templates = reason_templates.get(notice_type, ["Market notice for {region} region."])
        reason = random.choice(templates).format(
            station=station, unit=unit, region=region,
            line=line, limit=random.randint(200, 1200),
            time=f"{random.randint(14, 20):02d}:00",
        )

        days_offset = random.randint(0, 450)
        hours_offset = random.randint(0, 23)
        mins_offset = random.randint(0, 59)
        from datetime import timedelta
        creation = start_date + timedelta(days=days_offset, hours=hours_offset, minutes=mins_offset)

        records.append({
            "notice_id": str(base_id + i),
            "notice_type": notice_type,
            "creation_date": creation,
            "issue_date": creation + timedelta(minutes=random.randint(1, 30)),
            "region": region,
            "reason": reason,
            "external_reference": f"REF-{base_id + i}" if random.random() > 0.6 else None,
        })

    df = pd.DataFrame(records)
    logger.info(f"Generated {len(df)} fallback AEMO notices")
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = ingest_market_notices()
    print(f"\nLoaded {len(df)} market notices")
    print(f"Notice types: {df['notice_type'].value_counts().to_dict()}")
    print(f"Regions: {df['region'].value_counts().to_dict()}")

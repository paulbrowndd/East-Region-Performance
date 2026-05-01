#!/usr/bin/env python3
"""Update dashboard data.js by pulling live data directly from Sigma.

No Excel download, no API token needed. Uses the Sigma MCP integration
already connected in Claude.ai to query two workbooks:

  Spoke OTD + barcode data  → Parcel site quality dashboard - TDD
                               element: EcXx6MAdUu  (Barcode data, filtered)

  Hub missorts + CPT        → Network Operations Dashboard
                               element: W8K9v-xqKn  (Missort Raw Data)
                               element: RM8-5BUgSQ  (Lanes That Missed CPT)

HOW TO USE:
  Just tell Claude: "Update the dashboard for date 4/28"
  Claude will query Sigma directly and give you an updated data.js.

  To run locally (requires SIGMA_API_TOKEN env var):
    export SIGMA_API_TOKEN=your_token
    python3 sigma_update.py --date "4/28"
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SITE_QUALITY_WB = "f37cc4b4-ae38-4b9d-b7c2-74991fbb925f"
NETWORK_OPS_WB  = "f87fb7be-75d5-4df6-8ab3-ad675bf77fdd"

BARCODE_ELEMENT = "EcXx6MAdUu"
MISSORT_ELEMENT = "W8K9v-xqKn"
CPT_ELEMENT     = "RM8-5BUgSQ"

EAST_SPOKES = {
    "ATL-11","ATL-12","BKN-9","BLT-3","BNX-1","BOS-5","BOS-6",
    "CIN-5","CLE-7","CLT-3","CNJ-2","COL-5","DCA-5","DET-13",
    "HBG-2","HFD-3","HGR-1","HUD-1","JAX-2","LIN-1","NAS-2",
    "NNJ-5","NNJ-6","ORL-3","PHL-7","PHL-8","PIT-2","QNS-2",
    "RAL-3","RIC-2","TPA-4","VAB-4",
}

EAST_HUBS = {"ATL-13","EWR-2","GCO-1","MNY-1","NYC-1"}

OTD_ROOTCAUSE_MAP: Dict[str, str] = {
    "dispatched but return: return to dm":                          "returns",
    "hub & spoke delay: delayed arrival at spoke":                  "delayedArrival",
    "late sort":                                                    "lateSort",
    "hub & spoke delay: no spoke scan":                             "noSpokeScan",
    "hub & spoke delay: incorrect facility":                        "incorrectFacility",
    "not included in parcel planner prior to first scan at spoke":  "parcelPlannerMiss",
    "delivered late: 12am - 4am":                                   "deliveredLate",
    "hub & spoke delay: lost at hub or transportation":             "lostAtHubTransport",
    "hub & spoke delay: lost at spoke":                             "lostAtSpoke",
    "otd by 8pm":                                                   "otdBy8pm",
    "auto reschedule":                                              "autoReschedule",
    "site rollover":                                                "siteRollover",
    "others":                                                       "others",
}

STATUS_KEYS = [
    "returns","delayedArrival","lateSort","noSpokeScan",
    "incorrectFacility","parcelPlannerMiss","deliveredLate",
    "sortAppRollover","lostAtHubTransport","lostAtSpoke",
    "otdBy8pm","autoReschedule","siteRollover","others",
]


def parse_date_key(value: str) -> Tuple[int, int]:
    m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})\s*", value)
    if not m:
        raise ValueError(f"Invalid date key '{value}'. Expected M/D e.g. 4/28")
    return int(m.group(1)), int(m.group(2))


def date_range_sql(d: date) -> str:
    return f"'{d.isoformat()}' AND '{(d + timedelta(days=1)).isoformat()}'"


def _sigma_api_query(sql: str, workbook_id: str) -> List[List]:
    import os, json as _j, urllib.request, urllib.error
    token = os.environ.get("SIGMA_API_TOKEN", "")
    if not token:
        raise RuntimeError("SIGMA_API_TOKEN not set.")
    payload = _j.dumps({"query": sql, "workbookId": workbook_id}).encode()
    req = urllib.request.Request(
        "https://aws-api.sigmacomputing.com/v2/query/workbook",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return _j.loads(resp.read()).get("rows", [])
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Sigma API {exc.code}: {exc.read().decode(errors='replace')}") from exc


def fetch_spoke_data(target_date: date, query_fn) -> Tuple[List[Dict], List[Dict]]:
    spoke_list = "'" + "','".join(sorted(EAST_SPOKES)) + "'"

    rows = query_fn(f"""
        SELECT "dPRqj12ypS" AS site, "Dbte26NohW" AS rootcause,
               SUM("8uTBY4sDQ0") AS total, SUM(CAST("jzL9Samq2G" AS decimal)) AS otd_sum
        FROM "workbook"."{BARCODE_ELEMENT}"
        WHERE "xgR59veu1t" BETWEEN {date_range_sql(target_date)}
          AND "dPRqj12ypS" IN ({spoke_list})
        GROUP BY 1,2 ORDER BY 1,2
    """, SITE_QUALITY_WB)

    site_counts: Dict[str, Dict] = {}
    site_otd_num: Dict[str, float] = {}
    site_otd_den: Dict[str, int] = {}

    for site, rootcause, total, otd_sum in rows:
        if not site:
            continue
        if site not in site_counts:
            site_counts[site]  = {k: 0 for k in STATUS_KEYS}
            site_otd_num[site] = 0.0
            site_otd_den[site] = 0

        n = int(total or 0)
        site_otd_den[site] += n
        site_otd_num[site] += float(otd_sum or 0)

        rc = str(rootcause or "").strip().lower()
        if rc in ("1.otd", "otd"):
            pass
        elif "sort app rollover" in rc:
            site_counts[site]["sortAppRollover"] += n
        else:
            key = OTD_ROOTCAUSE_MAP.get(rc)
            site_counts[site][key if key else "others"] += n

    spokes = []
    for site in sorted(site_counts):
        den = site_otd_den[site]
        entry = {"code": site, "otd": round(site_otd_num[site]/den*100, 1) if den else 0.0}
        entry.update(site_counts[site])
        spokes.append(entry)

    bc_rows = query_fn(f"""
        SELECT "Dbte26NohW", SUM("8uTBY4sDQ0")
        FROM "workbook"."{BARCODE_ELEMENT}"
        WHERE "xgR59veu1t" BETWEEN {date_range_sql(target_date)}
          AND "dPRqj12ypS" IN ({spoke_list})
        GROUP BY 1 ORDER BY 2 DESC
    """, SITE_QUALITY_WB)
    barcode = [{"status": str(r[0] or "others"), "count": int(r[1] or 0)} for r in bc_rows]

    return spokes, barcode


def fetch_hub_data(target_date: date, query_fn) -> List[Dict]:
    hub_list = "'" + "','".join(sorted(EAST_HUBS)) + "'"

    miss_rows = query_fn(f"""
        SELECT "MXzoqXTCHn", COUNT(*) FROM "workbook"."{MISSORT_ELEMENT}"
        WHERE "IRL7tB_Kj2" BETWEEN {date_range_sql(target_date)}
          AND "MXzoqXTCHn" IN ({hub_list})
        GROUP BY 1 ORDER BY 1
    """, NETWORK_OPS_WB)
    miss_by_hub = {r[0]: int(r[1] or 0) for r in miss_rows if r[0]}

    cpt_rows = query_fn(f"""
        SELECT "8arEQURO8P", COUNT(*) AS total,
               SUM(CASE WHEN "7d49222d1e4d4350e85ba77cf9353da7" <= "biYHGTPTHf"
                             OR "biYHGTPTHf" IS NULL THEN 1 ELSE 0 END) AS ontime
        FROM "workbook"."{CPT_ELEMENT}"
        WHERE "dteIJNCjbj" BETWEEN {date_range_sql(target_date)}
          AND "8arEQURO8P" IN ({hub_list})
        GROUP BY 1 ORDER BY 1
    """, NETWORK_OPS_WB)
    cpt_by_hub: Dict[str, float] = {}
    lanes_by_hub: Dict[str, int] = {}
    for hub, total, ontime in cpt_rows:
        if hub and total:
            lanes_by_hub[hub] = int(total)
            cpt_by_hub[hub] = round(int(ontime or 0)/int(total)*100, 1)

    hubs = []
    for hub in sorted(EAST_HUBS | set(miss_by_hub) | set(cpt_by_hub)):
        lanes = lanes_by_hub.get(hub, 0)
        missorts = miss_by_hub.get(hub, 0)
        hubs.append({
            "code": hub,
            "missorts": missorts,
            "missortRate": round(missorts/lanes*100, 3) if lanes else 0.0,
            "onTimeCpt": cpt_by_hub.get(hub, 0.0),
        })
    return hubs


def load_data_js(path: Path) -> Dict:
    raw = path.read_text(encoding="utf-8").strip()
    prefix = "window.DASHBOARD_DATA="
    if not raw.startswith(prefix):
        raise ValueError("data.js does not start with window.DASHBOARD_DATA=")
    return json.loads(raw[len(prefix):].rstrip(";"))


def write_data_js(path: Path, payload: Dict) -> None:
    path.write_text(
        "window.DASHBOARD_DATA=" + json.dumps(payload, separators=(",",":")) + ";\n",
        encoding="utf-8",
    )


def build_weekly_snapshot(daily_periods: List[Dict], week_label: str) -> Dict:
    spokes_by_code: Dict[str, List] = defaultdict(list)
    for p in daily_periods:
        for s in p.get("spokes", []):
            spokes_by_code[s["code"]].append(s)

    weekly_spokes = []
    for code, rows in sorted(spokes_by_code.items()):
        item = {"code": code, "otd": round(sum(r["otd"] for r in rows)/len(rows), 1)}
        for k in STATUS_KEYS:
            item[k] = sum(r.get(k, 0) for r in rows)
        weekly_spokes.append(item)

    hubs_by_code: Dict[str, List] = defaultdict(list)
    for p in daily_periods:
        for h in p.get("hubs", []):
            hubs_by_code[h["code"]].append(h)

    weekly_hubs = []
    for code, rows in sorted(hubs_by_code.items()):
        weekly_hubs.append({
            "code": code,
            "missorts": sum(r.get("missorts",0) for r in rows),
            "missortRate": round(sum(r.get("missortRate",0) for r in rows)/len(rows), 3),
            "onTimeCpt": round(sum(r.get("onTimeCpt",0) for r in rows)/len(rows), 1),
        })

    bc_totals: Dict[str, int] = defaultdict(int)
    for p in daily_periods:
        for row in p.get("barcode", []):
            bc_totals[row["status"]] += int(row["count"])

    return {
        "label": week_label,
        "spokes": weekly_spokes,
        "hubs": weekly_hubs,
        "barcode": sorted([{"status":s,"count":c} for s,c in bc_totals.items()],
                          key=lambda x: (-x["count"], x["status"])),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",      required=True)
    parser.add_argument("--data-file", default="data.js")
    parser.add_argument("--week-key",   default=None)
    parser.add_argument("--week-dates", default=None)
    parser.add_argument("--week-label", default="Weekly (Mon-Sun)")
    parser.add_argument("--dry-run",    action="store_true")
    args = parser.parse_args()

    mo, day = parse_date_key(args.date)
    target = date(date.today().year, mo, day)
    print(f"Fetching data for {target} from Sigma...")

    print("  → Spoke OTD + barcode...", flush=True)
    spokes, barcode = fetch_spoke_data(target, _sigma_api_query)
    print(f"     {len(spokes)} spokes, {len(barcode)} barcode categories")

    print("  → Hub missorts + CPT...", flush=True)
    hubs = fetch_hub_data(target, _sigma_api_query)
    print(f"     {len(hubs)} hubs")

    snapshot = {"label": f"Daily {args.date}", "spokes": spokes, "hubs": hubs, "barcode": barcode}

    if args.dry_run:
        print(json.dumps(snapshot, indent=2))
        return

    data_path = Path(args.data_file).expanduser().resolve()
    payload = load_data_js(data_path)
    payload.setdefault("dailySnapshots", {})
    payload.setdefault("weeklySnapshots", {})

    payload["dailySnapshots"][args.date] = snapshot
    sorted_keys = sorted(payload["dailySnapshots"].keys(), key=parse_date_key)
    payload["dailySnapshots"] = {k: payload["dailySnapshots"][k] for k in sorted_keys}

    week_dates = (
        [p.strip() for p in args.week_dates.split(",") if p.strip()]
        if args.week_dates else sorted_keys
    )
    missing = [k for k in week_dates if k not in payload["dailySnapshots"]]
    if missing:
        raise ValueError(f"Dates not found in daily snapshots: {missing}")

    weekly_key = args.week_key or (
        list(payload["weeklySnapshots"].keys())[0]
        if payload["weeklySnapshots"] else f"Week of {args.date}"
    )
    payload["weeklySnapshots"][weekly_key] = build_weekly_snapshot(
        [payload["dailySnapshots"][k] for k in week_dates], args.week_label
    )

    write_data_js(data_path, payload)
    print(f"\nUpdated {data_path}")
    print(f"  Daily: {args.date}  ({len(spokes)} spokes, {len(hubs)} hubs)")
    print(f"  Weekly: {weekly_key} from {', '.join(week_dates)}")
    print(f"\nNext: git add data.js && git commit -m 'Add {args.date} data' && git push")


if __name__ == "__main__":
    main()

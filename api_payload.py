"""Build the JSON payload consumed by the Regional Labour Market Dashboard.

The frontend (frontend/index.html) renders everything client-side from a single
`{defs, map}` object — one entry per economic region containing its monthly
series and the industry/wage snapshot for its province. This module assembles
that object from the SQLite tables staged by pipeline.py.
"""
import re
import sqlite3

import pandas as pd

DB_NAME = "okanagan_economics.db"

# StatCan NAICS names carry a bracketed code suffix, e.g. "Construction [23]".
_BRACKET = re.compile(r"\s*\[[^\]]*\]\s*$")

# Short, dashboard-friendly labels for the long official NAICS names.
SECTOR_SHORT = {
    "Wholesale and retail trade": "Retail & wholesale trade",
    "Health care and social assistance": "Health care",
    "Professional, scientific and technical services": "Professional",
    "Finance, insurance, real estate, rental and leasing": "Finance & real estate",
    "Accommodation and food services": "Accommodation & food",
    "Business, building and other support services": "Business support",
    "Forestry, fishing, mining, quarrying, oil and gas": "Natural resources",
    "Information, culture and recreation": "Info, culture & rec",
    "Transportation and warehousing": "Transportation",
    "Other services (except public administration)": "Other services",
    "Educational services": "Educational services",
    "Public administration": "Public administration",
    "Manufacturing": "Manufacturing",
    "Construction": "Construction",
    "Agriculture": "Agriculture",
    "Utilities": "Utilities",
}

# Which labour-force characteristic feeds each monthly series.
SERIES_CHARS = {
    "unempS": "Unemployment rate",
    "partS": "Participation rate",
    "empS": "Employment rate",
    "lfS": "Labour force",
}

_MONTHS = ["", "January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _clean_naics(name):
    return _BRACKET.sub("", str(name)).strip()


def _month_label(ref_date):
    """'2026-05' -> {'short': "May '26", 'full': 'May 2026'}."""
    try:
        y, m = ref_date.split("-")
        mi = int(m)
        return {"short": _MONTHS[mi][:3] + " '" + y[2:], "full": _MONTHS[mi] + " " + y}
    except Exception:
        return {"short": str(ref_date), "full": str(ref_date)}


def _industry_by_province(conn):
    """Return {province: [sector dicts]} joined across employment + wages."""
    emp = pd.read_sql_query("SELECT * FROM employment_by_industry", conn)
    wag = pd.read_sql_query("SELECT * FROM wages_by_industry", conn)
    emp["clean"] = emp["naics"].map(_clean_naics)
    wag["clean"] = wag["naics"].map(_clean_naics)
    wag = wag[["prov", "clean", "avg_hourly_wage"]]

    merged = emp.merge(wag, on=["prov", "clean"], how="inner")
    out = {}
    for prov, grp in merged.groupby("prov"):
        total = float(grp["employed"].sum())
        sectors = []
        for _, r in grp.iterrows():
            employed = float(r["employed"]) if pd.notna(r["employed"]) else 0.0
            ft = float(r["ft"]) if pd.notna(r["ft"]) else 0.0
            ft_share = max(0.0, min(1.0, ft / employed)) if employed else 0.0
            sectors.append({
                "name": SECTOR_SHORT.get(r["clean"], r["clean"]),
                "jobs": round(employed),
                "share": round(employed / total * 100, 1) if total else 0.0,
                "wage": round(float(r["avg_hourly_wage"]), 2) if pd.notna(r["avg_hourly_wage"]) else None,
                "ft": round(ft_share, 3),
            })
        sectors.sort(key=lambda s: s["jobs"], reverse=True)
        out[prov] = sectors
    return out


def build_payload(db_name=DB_NAME):
    conn = sqlite3.connect(db_name)
    try:
        labour = pd.read_sql_query("SELECT * FROM labour_by_region", conn)
        industry = _industry_by_province(conn)
        ind_period = pd.read_sql_query(
            "SELECT MAX(ref_date) AS p FROM employment_by_industry", conn)["p"][0]
        wage_period = pd.read_sql_query(
            "SELECT MAX(ref_date) AS p FROM wages_by_industry", conn)["p"][0]
    finally:
        conn.close()

    defs = []
    region_map = {}

    # One region at a time: pivot its characteristics onto a shared month axis.
    for geo, grp in labour.groupby("geo"):
        region = grp["region"].iloc[0]
        prov = grp["prov"].iloc[0]
        rid = _slug(region)

        pivot = grp.pivot_table(index="ref_date", columns="characteristic",
                                values="metric_value", aggfunc="first").sort_index()

        def series(char):
            if char not in pivot.columns:
                return []
            s = pivot[char].ffill().bfill()
            return [round(float(v), 1) for v in s.tolist()]

        unempS = series(SERIES_CHARS["unempS"])
        if not unempS:
            continue  # region without the core series — skip

        axis = list(pivot.index)
        labels = [_month_label(d) for d in axis]

        # Region-level full-time / total employment for the donut (real FT/PT).
        emp_series = pivot.get("Employment")
        ft_series = pivot.get("Full-time employment")
        tot_jobs = float(emp_series.ffill().bfill().iloc[-1]) if emp_series is not None else 0.0
        ft_jobs = float(ft_series.ffill().bfill().iloc[-1]) if ft_series is not None else 0.0

        secs = industry.get(prov, [])

        defs.append({"id": rid, "name": region, "label": geo, "prov": prov})
        region_map[rid] = {
            "def": {"id": rid, "name": region, "label": geo, "prov": prov},
            "labels": labels,
            "unempS": unempS,
            "partS": series(SERIES_CHARS["partS"]),
            "empS": series(SERIES_CHARS["empS"]),
            "lfS": [round(v) for v in series(SERIES_CHARS["lfS"])],
            "secs": secs,
            "ftJobs": round(ft_jobs, 1),
            "totJobs": round(tot_jobs, 1),
            "industryProv": prov,
        }

    defs.sort(key=lambda d: d["name"])
    latest_period = max((m["labels"][-1]["full"]
                         for m in region_map.values() if m["labels"]), default="")

    return {
        "defs": defs,
        "map": region_map,
        "meta": {
            "industryPeriod": str(ind_period),
            "wagePeriod": str(wage_period),
            "updated": latest_period,
        },
    }


if __name__ == "__main__":
    import json
    p = build_payload()
    print(f"regions: {len(p['defs'])}")
    tok = p["map"].get("thompson-okanagan")
    if tok:
        print(f"thompson-okanagan months: {len(tok['unempS'])}, "
              f"latest unemp: {tok['unempS'][-1]}, sectors: {len(tok['secs'])}, "
              f"prov: {tok['industryProv']}")
        print("top sector:", tok["secs"][0] if tok["secs"] else None)
    print("payload bytes:", len(json.dumps(p)))

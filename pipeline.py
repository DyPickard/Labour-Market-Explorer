import io
import zipfile

import requests
import pandas as pd

from database_loader import load_data_to_sqlite

# ---------------------------------------------------------------------------
# Configuration: StatCan Web Data Service product (table) IDs
# ---------------------------------------------------------------------------
# 14100462 Labour force characteristics by economic region (monthly, 3-mo MA).
#          -> KPIs, trend line, FT/PT donut, region selector, regional ranking.
# 14100023 Labour force characteristics BY INDUSTRY (annual, by province).
#          -> employment-by-industry bars + industry detail table + FT share.
# 14100064 Employee wages by industry (annual, by province).
#          -> average hourly wage bars + wage column in the table.
#
# Industry & wage data are only published at the province level, so those
# panels show the province that the selected economic region belongs to.
PID_LABOUR = "14100462"
PID_INDUSTRY = "14100023"
PID_WAGES = "14100064"

CSV_ENDPOINT = "https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/{pid}/en"

# Dimension slices we keep from the industry/wage cubes.
GENDER_TOTAL = "Total - Gender"
AGE_TOTAL = "15 years and over"

# NAICS roll-up rows that would double-count if treated as sectors.
NAICS_AGGREGATES = {
    "Total, all industries",
    "Total employed, all industries",
    "Total employees, all industries",
    "Goods-producing sector",
    "Services-producing sector",
    "Business sector, goods-producing industries",
    "Business sector, services-producing industries",
    "Non-business sector industries",
}


def _download_table(pid):
    """Download and unzip a StatCan full-table CSV into a pandas DataFrame.

    Returns None on any network/parse failure so callers can skip gracefully.
    """
    api_url = CSV_ENDPOINT.format(pid=pid)
    print(f"\n[{pid}] Requesting current data link from Statistics Canada...")
    resp = requests.get(api_url, timeout=120)
    if resp.status_code != 200:
        print(f"[ERROR] [{pid}] API connection failed: {resp.status_code}")
        return None

    download_url = resp.json().get("object")
    if not download_url:
        print(f"[ERROR] [{pid}] No download link returned by API.")
        return None

    print(f"[{pid}] Downloading compressed payload...")
    file_resp = requests.get(download_url, timeout=600)
    if file_resp.status_code != 200:
        print(f"[ERROR] [{pid}] Compressed payload download failed.")
        return None

    print(f"[{pid}] Unpacking ZIP archive in-memory...")
    zip_bytes = io.BytesIO(file_resp.content)
    with zipfile.ZipFile(zip_bytes) as archive:
        csv_name = [f for f in archive.namelist() if f.endswith(".csv")][0]
        with archive.open(csv_name) as csv_file:
            dframe = pd.read_csv(csv_file, low_memory=False)
    print(f"[{pid}] Loaded raw dataset: {len(dframe):,} rows, {len(dframe.columns)} cols.")
    return dframe


def _require_cols(dframe, cols, pid):
    missing = [c for c in cols if c not in dframe.columns]
    if missing:
        print(f"[ERROR] [{pid}] Missing expected columns: {missing}")
        print(f"        Available columns: {list(dframe.columns)}")
        return False
    return True


# ---------------------------------------------------------------------------
# Extract + transform for each table
# ---------------------------------------------------------------------------
def build_labour_by_region():
    """All economic regions, all characteristics, Estimate values only."""
    df = _download_table(PID_LABOUR)
    if df is None:
        return None
    cols = ["REF_DATE", "GEO", "Labour force characteristics", "Statistics", "VALUE"]
    if not _require_cols(df, cols, PID_LABOUR):
        return None

    df = df[cols].copy()
    df.columns = ["ref_date", "geo", "characteristic", "statistic_type", "metric_value"]

    # Keep point estimates only; keep the economic regions (labelled "Region, Province").
    df = df[df["statistic_type"] == "Estimate"].copy()
    df = df[df["geo"].str.contains(",", na=False)].copy()

    # Province = text after the final comma (e.g. "Thompson-Okanagan, British Columbia").
    df["prov"] = df["geo"].str.rsplit(",", n=1).str[-1].str.strip()
    df["region"] = df["geo"].str.rsplit(",", n=1).str[0].str.strip()

    out = df[["ref_date", "geo", "region", "prov", "characteristic", "metric_value"]]
    print(f"[{PID_LABOUR}] Kept {len(out):,} region estimate rows "
          f"({out['geo'].nunique()} economic regions).")
    return out


def _slice_industry_like(pid, extra_cols, value_filters):
    """Shared extract for the two province-level NAICS cubes.

    Filters to the latest reference period, total gender/age, provinces only,
    and drops NAICS aggregate roll-ups.
    """
    df = _download_table(pid)
    if df is None:
        return None
    base = ["REF_DATE", "GEO", "North American Industry Classification System (NAICS)",
            "Gender", "Age group", "VALUE"]
    if not _require_cols(df, base + list(extra_cols), pid):
        return None

    keep = base + list(extra_cols)
    df = df[keep].copy()
    df = df.rename(columns={
        "REF_DATE": "ref_date",
        "GEO": "prov",
        "North American Industry Classification System (NAICS)": "naics",
        "VALUE": "value",
    })

    # Total gender / total age only.
    df = df[(df["Gender"] == GENDER_TOTAL) & (df["Age group"] == AGE_TOTAL)].copy()
    # Provinces / Canada only (these cubes have no economic regions).
    df = df[~df["prov"].str.contains(",", na=False)].copy()
    # Latest reference period available.
    latest = df["ref_date"].max()
    df = df[df["ref_date"] == latest].copy()
    # Drop NAICS aggregates.
    df = df[~df["naics"].isin(NAICS_AGGREGATES)].copy()

    for col, allowed in value_filters.items():
        df = df[df[col].isin(allowed)].copy()

    print(f"[{pid}] Latest period {latest}; kept {len(df):,} rows.")
    return df, latest


def build_employment_by_industry():
    """Per-province employment / full-time / part-time by NAICS industry."""
    res = _slice_industry_like(
        PID_INDUSTRY,
        extra_cols=["Labour force characteristics"],
        value_filters={"Labour force characteristics":
                       ["Employment", "Full-time employment", "Part-time employment"]},
    )
    if res is None:
        return None
    df, latest = res
    out = df.rename(columns={"Labour force characteristics": "characteristic"})
    out = out[["ref_date", "prov", "naics", "characteristic", "value"]].copy()
    # Pivot characteristics into columns: employed / ft / pt.
    wide = out.pivot_table(index=["prov", "naics", "ref_date"],
                           columns="characteristic", values="value",
                           aggfunc="first").reset_index()
    wide = wide.rename(columns={
        "Employment": "employed",
        "Full-time employment": "ft",
        "Part-time employment": "pt",
    })
    for c in ["employed", "ft", "pt"]:
        if c not in wide.columns:
            wide[c] = pd.NA
    wide = wide[["prov", "naics", "ref_date", "employed", "ft", "pt"]]
    print(f"[{PID_INDUSTRY}] Industry employment: {len(wide):,} rows "
          f"({wide['prov'].nunique()} provinces).")
    return wide


def build_wages_by_industry():
    """Per-province average hourly wage by NAICS industry."""
    res = _slice_industry_like(
        PID_WAGES,
        extra_cols=["Wages", "Type of work"],
        value_filters={"Wages": ["Average hourly wage rate"],
                       "Type of work": ["Both full- and part-time employees"]},
    )
    if res is None:
        return None
    df, latest = res
    out = df[["ref_date", "prov", "naics", "value"]].copy()
    out = out.rename(columns={"value": "avg_hourly_wage"})
    print(f"[{PID_WAGES}] Industry wages: {len(out):,} rows "
          f"({out['prov'].nunique()} provinces).")
    return out


def run_etl():
    print("=" * 70)
    print("Okanagan Economics ETL  --  Statistics Canada Labour Force Survey")
    print("=" * 70)

    labour = build_labour_by_region()
    if labour is not None:
        load_data_to_sqlite(labour, "labour_by_region")

    industry = build_employment_by_industry()
    if industry is not None:
        load_data_to_sqlite(industry, "employment_by_industry")

    wages = build_wages_by_industry()
    if wages is not None:
        load_data_to_sqlite(wages, "wages_by_industry")

    print("\n[DONE] Pipeline complete.")


if __name__ == "__main__":
    run_etl()

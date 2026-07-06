import requests
import io
import zipfile
import requests
import pandas as pd

from database_loader import load_data_to_sqlite

# 1. Configuration
# PRODUCT_ID for current active table for Labour Force Characteristics by Economic Region
PRODUCT_ID = "14100462"
API_URL = f"https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/{PRODUCT_ID}/en"
TARGET_GEO = "Thompson-Okanagan, British Columbia"

def run_etl():
    # Phase 1 - Extract
    print("Pinging Statistics Canada API for current data link...")
    response = requests.get(API_URL)
    if response.status_code != 200:
        print(f"[ERROR] API connection failed: {response.status_code}")
        return
    
    download_url = response.json().get("object")
    print(f"Downloading data payload from transient link...")
    file_response = requests.get(download_url)

    if file_response.status_code != 200:
        print("[ERROR] Compressed payload download failed.")
        return
    
    # Unpack zip entirely in memory using a byte stream buffer
    print("Unpacking ZIP archieve in-memory...")
    zip_bytes = io.BytesIO(file_response.content)
    with zipfile.ZipFile(zip_bytes) as archive:
        # Statcan zip archives typically contain one primary CSV file named after the product ID
        csv_filename = [f for f in archive.namelist() if f.endswith('.csv')][0]
        with archive.open(csv_filename) as csv_file:
            # load into pandas dataframe
            dframe = pd.read_csv(csv_file)
    
    print(f"Loaded raw dataset containing {len(dframe):,} total rows.")

    # Transform data
    print(f"Filtering data for region: '{TARGET_GEO}'...")

    # Filter by geography
    dframe_filtered = dframe[dframe['GEO'] == TARGET_GEO].copy()

    if dframe_filtered.empty:
        print("[WARNING] No matching regional rows found. Checking column configuration...")
        print("Available regions sample:", dframe['GEO'].unique()[:5])
        return

    # Debug utility: Log actual columns present in the source file
    print(f"Detected columns in file: {list(dframe_filtered.columns)}")

    # TODO: Handle missing columns by implementing dynamic column verification or population

    # clean and select essential structural columns 
    # standard columns in this dataset: REF_DATE, GEO, Labour force characteristics, Statistics, UOM, VALUE
    keep_cols = ['REF_DATE', 'Labour force characteristics', 'Statistics', 'VALUE']
    dframe_clean = dframe_filtered[keep_cols].copy()

    # rename columns to standard lowercase database snake_case format
    dframe_clean.columns = ['ref_date', 'characteristic', 'statistic_type', 'metric_value']

    print(f"[SUCCESS] Filtered down to {len(dframe_clean)} records for {TARGET_GEO}.")
    print("\nSample data preview:")
    print(dframe_clean.head(10))

    return dframe_clean

if __name__ == "__main__":
    okanagan_data = run_etl()
    load_data_to_sqlite(okanagan_data)
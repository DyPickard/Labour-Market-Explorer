import requests

PRODUCT_ID = "14100387"
url = f"https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/{PRODUCT_ID}/en"

print("Sending request to Statistics Canada. . .")
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    if data.get("status") == "SUCCESS":
        download_url = data.get("object")
        print(f"\n[SUCCESS] Target CSV URL found:")
        print(download_url)
    else:
        print(f"[ERROR] API responded with status: {data.get('status')}")
else:
    print(f"[ERROR] HTTP Request failed with status code: {response.status_code}")
    
#!/bin/sh
set -e

python - <<'PY'
import os
import sqlite3
import subprocess
from config import DB_NAME

required_tables = (
    "labour_by_region",
    "employment_by_industry",
    "wages_by_industry",
)
required_set = set(required_tables)
db_name = os.getenv("DB_NAME", DB_NAME)

if not os.path.exists(db_name):
    print(f"Database file '{db_name}' not found. Running ETL pipeline to create it...")
    subprocess.run(["python", "pipeline.py"], check=True)
else:
    conn = sqlite3.connect(db_name)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?, ?, ?)",
            required_tables,
        )
        found = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()

    if not required_set.issubset(found):
        print("Required database tables are missing. Running ETL pipeline to rebuild them...")
        subprocess.run(["python", "pipeline.py"], check=True)
PY

exec gunicorn --bind 0.0.0.0:8080 api:app

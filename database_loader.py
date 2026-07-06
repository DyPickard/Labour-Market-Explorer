import sqlite3
import pandas as pd
from sqlalchemy import create_engine

DB_NAME = "okanagan_economics.db"
TABLE_NAME = "okanagan_labour_stats"

def load_data_to_sqlite(dframe):
    if dframe is None or dframe.empty:
        print("[ERROR] No data provided to load step.")
        return
    
    print(f"Connecting to local SQLite database '{DB_NAME}'...")
    # SQLAlchemy engine handles the translation between pandas and SQL
    engine = create_engine(f"sqlite:///{DB_NAME}")

    # load data into a table named 'okanagan_labour_stats'
    print(f"Streaming data into SQL table '{TABLE_NAME}'...")
    dframe.to_sql(
        name=TABLE_NAME,
        con=engine,
        if_exists="replace",
        index=False
    )

    print("[SUCCESS] Data pipeline execution complete.")

    # SQL verification check
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM "+TABLE_NAME)
        row_count = cursor.fetchone()[0]
        print(f"Total SQL rows written = {row_count:,}")






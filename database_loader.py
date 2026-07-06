import sqlite3
import pandas as pd
from sqlalchemy import create_engine

DB_NAME = "okanagan_economics.db"


def load_data_to_sqlite(dframe, table_name):
    """Load a dataframe into a named SQLite table (replacing any existing one).

    Generalised from the original single-table loader so the pipeline can stage
    several StatCan tables (labour, industry employment, wages) into one DB.
    """
    if dframe is None or dframe.empty:
        print(f"[ERROR] No data provided to load step for '{table_name}'.")
        return

    print(f"Connecting to local SQLite database '{DB_NAME}'...")
    # SQLAlchemy engine handles the translation between pandas and SQL
    engine = create_engine(f"sqlite:///{DB_NAME}")

    print(f"Streaming {len(dframe):,} rows into SQL table '{table_name}'...")
    dframe.to_sql(
        name=table_name,
        con=engine,
        if_exists="replace",
        index=False,
    )

    # SQL verification check
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM " + table_name)
        row_count = cursor.fetchone()[0]
        print(f"[SUCCESS] Total SQL rows written to '{table_name}' = {row_count:,}")

"""Optional raw-data explorer (Streamlit).

The primary dashboard is the Flask app in api.py, which serves the Claude Design
frontend. This module is a lightweight secondary tool for browsing the staged
`labour_by_region` table directly:  streamlit run streamlit_explorer.py
"""
import sqlite3

import pandas as pd
import streamlit as st
import plotly.express as px

DATABASE_NAME = "okanagan_economics.db"
TABLE_NAME = "labour_by_region"

st.set_page_config(page_title="Labour Force Data Explorer", layout="wide")
st.title("Labour Force Data Explorer")

conn = sqlite3.connect(DATABASE_NAME)
dframe = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
conn.close()

regions = sorted(dframe["region"].unique())
default_ix = regions.index("Thompson-Okanagan") if "Thompson-Okanagan" in regions else 0
region = st.sidebar.selectbox("Economic region", regions, index=default_ix)

metrics = sorted(dframe["characteristic"].unique())
metric = st.sidebar.selectbox("Characteristic", metrics)

filtered = dframe[(dframe["region"] == region) & (dframe["characteristic"] == metric)]
filtered = filtered.sort_values("ref_date")

fig = px.line(filtered, x="ref_date", y="metric_value",
              title=f"{metric} over time — {region}")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Filtered rows")
st.dataframe(filtered, use_container_width=True)

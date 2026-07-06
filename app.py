import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px

DATABASE_NAME = "okanagan_economics.db"
TABLE_NAME = "okanagan_labour_stats"
TARGET_GEO = "Thompson-Okanagan"

st.set_page_config(page_title=TARGET_GEO+" Economic Dashboard", layout="wide")
st.title(TARGET_GEO+" Economic Indicator Tracking")

# connect to pipeline database
conn = sqlite3.connect(DATABASE_NAME)

# load data into fresh dataframe for virtualization
dframe = pd.read_sql_query("SELECT * FROM "+TABLE_NAME, conn)
conn.close()

# Dashboard Layout
metrics = dframe['characteristic'].unique()
selected_metric = st.sidebar.selectbox("Select Economic Metric", metrics)

# Filter data by selection
#dframe_filtered = dframe[dframe['characteristic'] == selected_metric].sort_values('ref_date')
dframe_metric = dframe[dframe["characteristic"] == selected_metric]

dframe_filtered = dframe_metric[dframe_metric['statistic_type'] == 'Estimate'].sort_values('ref_date')

# Display interactive line chart
fig = px.line(
    dframe_filtered,
    x='ref_date',
    y='metric_value',
    title=f"{selected_metric} Over Time ({TARGET_GEO})"
)

# Display data preview table
st.subheader("Raw filtered pipeline data")
st.dataframe(dframe_filtered, use_container_width=True)
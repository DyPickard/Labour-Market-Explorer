# Okanagan Economics — Regional Labour Market Dashboard

A Statistics Canada Labour Force Survey dashboard. A Python ETL pipeline stages
StatCan data into SQLite; a Flask server serves a Claude Design frontend that
fetches that data as JSON and renders it entirely client-side (no build step).
The entire application is containerized with Docker and ready for deployment.

## Architecture

```
pipeline.py ──► okanagan_economics.db (SQLite)
                 ├─ labour_by_region        14-10-0462  (65 economic regions, monthly, 3-mo MA)
                 ├─ employment_by_industry   14-10-0023  (by province, latest year, NAICS)
                 └─ wages_by_industry        14-10-0064  (by province, latest year, NAICS)
                          │
api.py (Flask)  ─────────┤  api_payload.py builds the JSON
   GET /                 → frontend/index.html   (the design)
   GET /support.js       → frontend/support.js   (design runtime)
   GET /api/labour       → { defs, map, meta }   (all regions' real data)
   POST /api/refresh     → clears the in-process cache
                          │
frontend/index.html ─────┘  design JS rewired to fetch instead of mock
```

### Data-granularity note
StatCan publishes **labour force** figures by economic region, but **industry
employment and wages only by province**. So the industry bars, wage bars and
industry table show the **province** that the selected region belongs to
(e.g. Thompson-Okanagan → British Columbia). Panels are labelled accordingly.

## Setup

### Option 1: Docker (Recommended)
```bash
docker build -t okanagan-app .
docker run -p 8080:8080 okanagan-app
```
Then navigate to `http://localhost:8080`.

### Option 2: Local Python Environment
```bash
pip install -r requirements.txt
python pipeline.py     # downloads 3 StatCan tables → okanagan_economics.db
python api.py          # serves the dashboard at http://127.0.0.1:5000
```

The database is git-ignored, so run `python pipeline.py` once after cloning.

## Refreshing data

StatCan updates the LFS monthly. To refresh:

```bash
python pipeline.py                                   # re-stage the tables
curl -X POST http://127.0.0.1:5000/api/refresh       # or just restart api.py
```

## Files

| File | Purpose |
|------|---------|
| `pipeline.py` | ETL: download + clean 3 StatCan tables into SQLite |
| `database_loader.py` | Generic `load_data_to_sqlite(df, table_name)` |
| `api_payload.py` | Builds the `{defs, map, meta}` JSON from the DB |
| `api.py` | Flask server (main app) |
| `frontend/index.html` | Claude Design dashboard, wired to `/api/labour` |
| `frontend/support.js` | Claude Design runtime (unmodified) |
| `streamlit_explorer.py` | Optional raw-data browser: `streamlit run streamlit_explorer.py` |
| `extract_test.py` | Standalone StatCan API connectivity check |

## How the frontend was adapted

The original design (`frontend/index.html`) generated all data client-side with a
seeded PRNG. It was rewired to real data with minimal surgery:

- The mock generators (`build`, `regionDefs`, `sectorDefs`, `monthLabels`, PRNG)
  were removed.
- `componentDidMount()` now fetches `/api/labour` once and stores it in state.
- `renderVals()` reads the fetched `{defs, map}` instead of the mock, with a
  loading/error skeleton for the pre-fetch render.
- All SVG chart renderers (sparklines, trend line, bar charts, donut) are
  unchanged — the JSON payload matches the shape they already expected.
- Labels corrected to match the real source: "3-month moving average, unadjusted"
  (not seasonally adjusted), and provincial labelling on industry/wage panels.

Data source: Statistics Canada, Labour Force Survey — product IDs 14-10-0462,
14-10-0023, 14-10-0064.

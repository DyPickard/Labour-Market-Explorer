"""Flask server for the Regional Labour Market Dashboard.

Serves the Claude Design frontend (frontend/index.html + support.js) and a
single JSON endpoint that feeds it real Statistics Canada data staged in SQLite
by pipeline.py. No build step: the browser loads the design, then fetches
/api/labour once and renders everything client-side.
"""
import os

from flask import Flask, jsonify, send_from_directory

from api_payload import build_payload

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

app = Flask(__name__, static_folder=None)

# The payload is derived from a static monthly DB, so build it once and cache.
_cache = {}


def get_payload():
    if "data" not in _cache:
        _cache["data"] = build_payload()
    return _cache["data"]


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/support.js")
def support_js():
    return send_from_directory(FRONTEND_DIR, "support.js", mimetype="text/javascript")


@app.route("/style.css")
def style_css():
    return send_from_directory(FRONTEND_DIR, "style.css", mimetype="text/css")


@app.route("/about")
def about():
    return send_from_directory(FRONTEND_DIR, "about.html")


@app.route("/api/labour")
def api_labour():
    return jsonify(get_payload())


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Clear the cache so the next request rebuilds from the DB (after re-running
    the pipeline) without restarting the server."""
    _cache.pop("data", None)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

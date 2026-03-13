# 4D Strategy Web

Simple FastAPI + Jinja2 app to view strategy data and outcomes in the browser.

## Run

From project root:

```bash
uv run uvicorn web.main:app --reload --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000/

Requires `4d_history.csv` in the project root. First load may take a few seconds while data is computed.

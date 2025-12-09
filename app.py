from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
from datetime import datetime
from dateutil import parser
from pathlib import Path

CSV_PATH = Path("shunting_track_schedule.csv")   # <= same folder as app.py
import os
from pathlib import Path

CSV_PATH = Path(os.environ.get("SHUNT_CSV", "shunting_track_schedule.csv"))


# ----------------------- Utility Functions ------------------------

def to_dt(value):
    """Convert any datetime string into datetime object."""
    return parser.parse(str(value))

def load_schedule():
    """Load the shunting schedule CSV."""
    if not CSV_PATH.exists():
        return pd.DataFrame(columns=["TrainID", "Track", "Arrival", "Departure"])
    df = pd.read_csv(CSV_PATH, parse_dates=["Arrival", "Departure"])
    return df

def merge_intervals(intervals):
    """Merge overlapping intervals."""
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: x[0])
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged

def get_busy_intervals(df, track, ws, we):
    """Return busy intervals on a track."""
    rows = df[df["Track"] == track]
    intervals = []
    for _, r in rows.iterrows():
        start = max(r["Arrival"], ws)
        end = min(r["Departure"], we)
        if start < end:
            intervals.append((start, end))
    return merge_intervals(intervals)

def get_free_intervals(busy, ws, we):
    """Return free slots when track is not occupied."""
    free = []
    cursor = ws
    for start, end in busy:
        if cursor < start:
            free.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < we:
        free.append((cursor, we))
    return free


# ----------------------- FastAPI Models ------------------------

class SlotQuery(BaseModel):
    window_start: str
    window_end: str
    track: Optional[str] = None


# ----------------------- FastAPI App ------------------------

app = FastAPI(title="Shunting Slot Finder API")

@app.get("/")
def home():
    return {"message": "Shunting API is running 🚂"}


@app.get("/tracks")
def list_tracks():
    df = load_schedule()
    tracks = sorted(df["Track"].dropna().unique().tolist())
    return {"tracks": tracks}


@app.post("/slots")
def compute_slots(query: SlotQuery):
    df = load_schedule()

    ws = to_dt(query.window_start)
    we = to_dt(query.window_end)

    if ws >= we:
        raise HTTPException(status_code=400, detail="window_start must be before window_end")

    tracks = [query.track] if query.track else sorted(df["Track"].dropna().unique().tolist())

    results = []

    for track in tracks:
        busy = get_busy_intervals(df, track, ws, we)
        free = get_free_intervals(busy, ws, we)

        results.append({
            "track": track,
            "busy": [(s.isoformat(), e.isoformat()) for s, e in busy],
            "free": [(s.isoformat(), e.isoformat()) for s, e in free]
        })

    return results


@app.get("/health")
def health():
    return {
        "status": "ok",
        "csv_found": CSV_PATH.exists()
    }

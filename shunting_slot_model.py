# shunting_slot_model.py
from typing import List, Tuple, Dict
from datetime import datetime
from dateutil import parser
import pandas as pd
from pathlib import Path

CSV_PATH = Path("shunting_track_schedule.csv")  # change if needed


def _to_dt(v) -> datetime:
    if isinstance(v, datetime):
        return v
    return parser.parse(str(v))


def load_schedule(csv_path: Path = CSV_PATH) -> pd.DataFrame:
    """
    Load schedule CSV. CSV must include columns: TrainID, Track, Arrival, Departure
    Arrival/Departure should be parseable datetime strings.
    """
    if not csv_path.exists():
        # return empty dataframe with expected columns
        return pd.DataFrame(columns=["TrainID", "Track", "Arrival", "Departure"])
    df = pd.read_csv(csv_path, parse_dates=["Arrival", "Departure"])
    # ensure columns exist
    for c in ["TrainID", "Track", "Arrival", "Departure"]:
        if c not in df.columns:
            df[c] = None
    return df[["TrainID", "Track", "Arrival", "Departure"]].copy()


def merge_intervals(intervals: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    """
    Merge overlapping intervals. Intervals must be (start, end) datetimes.
    Returns a list of non-overlapping merged intervals sorted by start time.
    """
    if not intervals:
        return []
    intervals_sorted = sorted(intervals, key=lambda x: x[0])
    merged = [intervals_sorted[0]]
    for s, e in intervals_sorted[1:]:
        last_s, last_e = merged[-1]
        if s <= last_e:
            # overlap -> merge
            merged[-1] = (last_s, max(last_e, e))
        else:
            merged.append((s, e))
    return merged


def get_busy_intervals_for_track(df: pd.DataFrame, track: str,
                                 window_start: datetime, window_end: datetime) -> List[Tuple[datetime, datetime]]:
    """
    Return merged busy intervals for a specific track, clipped to [window_start, window_end).
    """
    rows = df[df["Track"] == track]
    intervals = []
    for _, r in rows.iterrows():
        s = max(_to_dt(r["Arrival"]), window_start)
        e = min(_to_dt(r["Departure"]), window_end)
        if s < e:
            intervals.append((s, e))
    return merge_intervals(intervals)


def get_free_intervals_for_track(df: pd.DataFrame, track: str,
                                 window_start: datetime, window_end: datetime) -> List[Tuple[datetime, datetime]]:
    """
    Return free intervals (complement of busy intervals) for the track in the window.
    """
    busy = get_busy_intervals_for_track(df, track, window_start, window_end)
    free = []
    cursor = window_start
    for s, e in busy:
        if cursor < s:
            free.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < window_end:
        free.append((cursor, window_end))
    return free


def compute_slots_for_all_tracks(csv_path: Path = CSV_PATH,
                                 window_start: str = "2025-12-01 05:00",
                                 window_end: str = "2025-12-01 09:00") -> Dict[str, Dict[str, List[Tuple[str,str]]]]:
    """
    Convenience wrapper. Returns a dictionary:
      { track_name: { "busy": [(iso_start, iso_end), ...], "free": [...] } }
    """
    ws = _to_dt(window_start)
    we = _to_dt(window_end)
    if ws >= we:
        raise ValueError("window_start must be before window_end")

    df = load_schedule(csv_path)
    tracks = sorted(df["Track"].dropna().unique().tolist())
    result = {}
    for t in tracks:
        busy = get_busy_intervals_for_track(df, t, ws, we)
        free = get_free_intervals_for_track(df, t, ws, we)
        # format to ISO strings
        result[t] = {
            "busy": [(s.isoformat(), e.isoformat()) for s, e in busy],
            "free": [(s.isoformat(), e.isoformat()) for s, e in free]
        }
    return result


# simple CLI example
if __name__ == "__main__":
    import json
    slots = compute_slots_for_all_tracks(window_start="2025-12-01 05:00", window_end="2025-12-01 09:00")
    print(json.dumps(slots, indent=2))

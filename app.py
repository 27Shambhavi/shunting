# app.py  (Streamlit UI + Shunting Logic)
import streamlit as st
from datetime import datetime, timedelta
from dateutil import parser
import csv
from io import StringIO
from typing import List, Tuple

st.set_page_config(page_title="Shunting Slot Viewer", layout="wide")

CSV_COLUMNS = ["TrainID", "Track", "Arrival", "Departure"]

# ---------- Utilities ----------
def to_dt(v: str) -> datetime:
    return parser.parse(str(v))

def parse_csv_text(csv_text: str):
    """Return list of rows dict with parsed datetimes."""
    f = StringIO(csv_text)
    reader = csv.DictReader(f)
    rows = []
    for r in reader:
        try:
            arrival = to_dt(r.get("Arrival") or r.get("arrival"))
            departure = to_dt(r.get("Departure") or r.get("departure"))
        except Exception:
            continue
        rows.append({
            "TrainID": r.get("TrainID") or "",
            "Track": (r.get("Track") or "").strip(),
            "Arrival": arrival,
            "Departure": departure
        })
    return rows

def rows_to_csv_text(rows):
    out = StringIO()
    writer = csv.DictWriter(out, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "TrainID": r.get("TrainID",""),
            "Track": r.get("Track",""),
            "Arrival": r["Arrival"].isoformat(sep=" "),
            "Departure": r["Departure"].isoformat(sep=" ")
        })
    return out.getvalue()

def merge_intervals(intervals: List[Tuple[datetime, datetime]]):
    if not intervals:
        return []
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]
    for s,e in intervals[1:]:
        last_s, last_e = merged[-1]
        if s <= last_e:
            merged[-1] = (last_s, max(last_e, e))
        else:
            merged.append((s,e))
    return merged

def get_busy_intervals(rows, track, ws, we):
    intervals = []
    for r in rows:
        if (r["Track"] or "") != track:
            continue
        s = max(r["Arrival"], ws)
        e = min(r["Departure"], we)
        if s < e:
            intervals.append((s,e))
    return merge_intervals(intervals)

def get_free_intervals(busy, ws, we):
    free = []
    cursor = ws
    for s,e in busy:
        if cursor < s:
            free.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < we:
        free.append((cursor, we))
    return free

def find_first_free_slot(free_intervals, required_minutes=10):
    for s,e in free_intervals:
        if (e - s).total_seconds() >= required_minutes * 60:
            return (s, s + timedelta(minutes=required_minutes))
    return None

# ---------- UI ----------
st.title("🚆 Shunting Slot Viewer (Streamlit)")

col1, col2 = st.columns([1, 2])

with col1:
    st.header("Schedule CSV")
    uploaded = st.file_uploader("Upload shunting_track_schedule.csv", type=["csv"])

    if uploaded:
        csv_bytes = uploaded.read()
        csv_text = csv_bytes.decode("utf-8")
        rows = parse_csv_text(csv_text)
        st.success(f"Loaded {len(rows)} rows from uploaded CSV")
    else:
        st.info("No CSV uploaded. Load sample data if needed.")
        if st.button("Load sample dataset"):
            sample = """TrainID,Track,Arrival,Departure
T001,Shunting_Neck,2025-12-01 05:10,2025-12-01 05:25
T002,Stabling_Line_1,2025-12-01 05:05,2025-12-01 06:00
T003,Inspection_Line_1,2025-12-01 05:30,2025-12-01 07:00
T004,Stabling_Line_2,2025-12-01 05:45,2025-12-01 06:30
T005,Shunting_Neck,2025-12-01 06:10,2025-12-01 06:40
"""
            rows = parse_csv_text(sample)
            st.success("Sample data loaded")

    if 'rows' not in locals():
        rows = []

    if rows:
        if st.button("Download Current CSV"):
            csv_out = rows_to_csv_text(rows)
            st.download_button("Download CSV", csv_out, file_name="updated_shunting_schedule.csv")

with col2:
    st.header("Query Slots")
    tracks = sorted({r["Track"] for r in rows})

    if not tracks:
        st.warning("No tracks found. Upload CSV or load sample.")
    else:
        track = st.selectbox("Select Track", tracks)
        window_start = st.text_input("Window Start", "2025-12-01 05:00")
        window_end = st.text_input("Window End", "2025-12-01 09:00")
        required_minutes = st.number_input("Minimum Slot Duration (min)", 1, 300, 10)

        if st.button("Compute Slots"):
            ws = to_dt(window_start)
            we = to_dt(window_end)

            if ws >= we:
                st.error("Window start must be before window end.")
            else:
                busy = get_busy_intervals(rows, track, ws, we)
                free = get_free_intervals(busy, ws, we)

                st.subheader(f"Track: {track}")

                st.write("### Busy Intervals")
                if busy:
                    for s, e in busy:
                        st.write(f"- {s} → {e}")
                else:
                    st.write("- None")

                st.write("### Free Intervals")
                if free:
                    for s, e in free:
                        st.write(f"- {s} → {e}")
                else:
                    st.write("- None")

                slot = find_first_free_slot(free, required_minutes)
                if slot:
                    s, e = slot
                    st.success(f"First Free Slot: {s} → {e}")
                    if st.button("Reserve Slot"):
                        new_id = f"RESV_{len(rows)+1}"
                        rows.append({"TrainID": new_id, "Track": track, "Arrival": s, "Departure": e})
                        st.success(f"Reserved slot as TrainID {new_id}. Download CSV to save.")
                else:
                    st.info("No slot of required duration available.")

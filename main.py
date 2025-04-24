# electricity_usage_viewer.py
# Streamlit app: 100-day window  OR  same-day comparison across files
# ------------------------------------------------------------------

import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="Electricity-usage visualiser", layout="wide")
st.title("⚡ Electricity-usage visualiser")

MODE = st.radio(
    "Choose a view:",
    ["100-day window (single file)", "Compare one day across multiple files"],
    horizontal=True,
)

# ────────────────────────────────────────────────
# Common helper functions
# ────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def parse_hourly(csv_file) -> pd.DataFrame:
    """Return hourly rows <timestamp, kwh> for a single CSV."""
    df = pd.read_csv(
        csv_file,
        sep=";",
        decimal=",",
        header=None,
        names=["timestamp", "kwh"],
        engine="python",
        skiprows=4
    )
    mask = df["timestamp"].str.match(r"\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}")
    df = df[mask]
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%d.%m.%Y %H:%M")
    df["kwh"] = df["kwh"].astype(float)
    return df.sort_values("timestamp").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def hourly_to_daily(hourly_df) -> pd.DataFrame:
    return (
        hourly_df.assign(date=hourly_df["timestamp"].dt.date)
        .groupby("date", as_index=False)["kwh"]
        .sum()
        .rename(columns={"kwh": "daily_kwh"})
    )


# ────────────────────────────────────────────────
# MODE 1  –  100-day rolling window (single file)
# ────────────────────────────────────────────────
if MODE == "100-day window (single file)":
    file = st.file_uploader(
        "Upload a CSV (semicolon-separated, decimal comma)", type=["csv"]
    )
    if file:
        hourly = parse_hourly(file)
        daily = hourly_to_daily(hourly)

        st.success(
            f"Loaded **{len(daily)} days** "
            f"({daily['date'].iloc[0]} → {daily['date'].iloc[-1]})."
        )

        WINDOW = 100
        min_day = daily["date"].min()
        max_day = daily["date"].max() - timedelta(days=WINDOW - 1)

        start_day = st.date_input(
            "First day of the 100-day window",
            value=min_day,
            min_value=min_day,
            max_value=max_day,
        )

        end_day = start_day + timedelta(days=WINDOW - 1)
        window_df = daily[(daily["date"] >= start_day) & (daily["date"] <= end_day)]

        st.subheader(f"Daily kWh  —  {start_day} → {end_day}")
        st.line_chart(window_df.set_index("date")["daily_kwh"], height=450)

        with st.expander("Show daily table"):
            st.dataframe(window_df, hide_index=True, use_container_width=True)
    else:
        st.info("👈 Upload a CSV file to get started.")

# ────────────────────────────────────────────────
# MODE 2  –  Same-day comparison across files
# ────────────────────────────────────────────────
else:
    files = st.file_uploader(
        "Upload **one or more** CSV files (semicolon-separated, decimal comma)",
        type=["csv"],
        accept_multiple_files=True,
    )

    if files:
        # Parse every file → hourly DataFrame, store in dict keyed by name
        hourly_dict = {f.name: parse_hourly(f) for f in files}

        # Determine the union of available dates
        all_dates = set()
        for df in hourly_dict.values():
            all_dates |= set(df["timestamp"].dt.date.unique())
        date_choice = st.date_input(
            "Pick a calendar date to compare",
            value=min(all_dates),
            min_value=min(all_dates),
            max_value=max(all_dates),
        )

        # Build a DataFrame with rows = hour 0-23, columns = file names
        hour_index = pd.Index(range(24), name="hour")
        comparison_df = pd.DataFrame(index=hour_index)

        for name, df in hourly_dict.items():
            day_slice = df[df["timestamp"].dt.date == date_choice]
            if day_slice.empty:
                st.warning(f"⚠️  {name} has **no data** for {date_choice}")
                continue
            # Ensure exactly 24 hours (some meters omit zeros)
            day_slice = (
                day_slice.set_index(day_slice["timestamp"].dt.hour)["kwh"]
                .reindex(hour_index, fill_value=0.0)
            )
            comparison_df[name] = day_slice

        if comparison_df.empty:
            st.error("No datasets contained that date.")
        else:
            st.subheader(f"Hourly kWh on {date_choice} (all files)")
            st.line_chart(comparison_df, height=450)

            with st.expander("Show hourly table"):
                st.dataframe(
                    comparison_df.reset_index()
                    .rename(columns={"hour": "Hour (0-23)"}),
                    use_container_width=True,
                )
    else:
        st.info("👈 Upload at least one CSV file to get started.")

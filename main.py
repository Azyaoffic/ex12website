# electricity_usage_viewer.py
# Streamlit app: 100-day window  OR  same-day comparison across files
# ------------------------------------------------------------------

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px
import random

st.set_page_config(page_title="Electricity-usage visualiser", layout="wide")
st.title("⚡ Electricity-usage visualiser, base written by GPT-o3")

MODE = st.radio(
    "Choose a view:",
    ["100-day window (single file)", "Compare one day across multiple files", "Heatmap"],
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

path = "/electricity/.csv"

default_file_hashes = ["9e9dca492a061e211740838882", "94a4157616804ae51743754974", "c2a91e3d7222f6d51743069686", "c550bcace2429c281741504217", "ed9f4fcf0bfb1afa1741424674", "fe2b07c1f38b5cb91743699228"]
default_file_path = random.choice(default_file_hashes)
default_multiple_files_paths = {csv_file_name: parse_hourly("electricity/" + csv_file_name + ".csv") for csv_file_name in default_file_hashes}


# ────────────────────────────────────────────────
# MODE 1  –  100-day rolling window (single file)
# ────────────────────────────────────────────────
if MODE == "100-day window (single file)":
    file = st.file_uploader(
        "Upload a CSV (semicolon-separated, decimal comma)", type=["csv"]
    )
    if not file:
        st.info(f"Using default CSV with hash {default_file_path}.")

    if file:
        hourly = parse_hourly(file)
    else:
        hourly = parse_hourly(f"electricity/{default_file_path}.csv")

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


# ────────────────────────────────────────────────
# MODE 2  –  Same-day comparison across files
# ────────────────────────────────────────────────
elif MODE == "Compare one day across multiple files":
    files = st.file_uploader(
        "Upload **one or more** CSV files (semicolon-separated, decimal comma)",
        type=["csv"],
        accept_multiple_files=True,
    )

    if files:
        hourly_dict = {f.name: parse_hourly(f) for f in files}
    else:
        hourly_dict = default_multiple_files_paths

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


# ────────────────────────────────────────────
# Mode 3 - Total usage heatmap
# ────────────────────────────────────────────

elif MODE == "Heatmap":
    file = st.file_uploader(
        "Upload a CSV (semicolon-separated, decimal comma)", type=["csv"]
    )
    if not file:
        st.info(f"Using default CSV with hash {default_file_path}.")

    if file:
        hourly = parse_hourly(file)
    else:
        hourly = parse_hourly(f"electricity/{default_file_path}.csv")

    daily = hourly_to_daily(hourly)

    st.success(
        f"Loaded **{len(daily)} days** "
        f"({daily['date'].iloc[0]} → {daily['date'].iloc[-1]})."
    )

    min_day = daily["date"].min()
    max_day = daily["date"].max()

    window_df = daily
    window_df.index = daily["date"]

    fig = px.density_heatmap(window_df["daily_kwh"], y="daily_kwh", nbinsx=300, nbinsy=20, color_continuous_scale=["blue", "lightblue", "yellow", "orange", "red"])

    st.subheader(f"Heatmap of energy usage")
    st.plotly_chart(fig, height=500)

    with st.expander("Show daily table"):
        st.dataframe(window_df, hide_index=True, use_container_width=True)


# ────────────────────────────────────────────
# Mode 4 - Error bands
# ────────────────────────────────────────────
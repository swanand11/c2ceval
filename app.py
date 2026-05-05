import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🏆 Repo Evaluation Dashboard")

df = pd.read_csv("results.csv")

# Filters
st.sidebar.header("Filters")

women = st.sidebar.checkbox("All Women Teams")
junior = st.sidebar.checkbox("All Junior Teams")

sort_by = st.sidebar.selectbox(
    "Sort By",
    ["total_score", "architecture_score", "heuristic_score"]
)

top_n = st.sidebar.slider("Top N", 5, 50, 10)

filtered = df.copy()

if women:
    filtered = filtered[filtered["all_women"].str.lower() == "yes"]

if junior:
    filtered = filtered[filtered["all_junior"].str.lower() != "no"]

filtered = filtered.sort_values(by=sort_by, ascending=False).head(top_n)

# Table
st.subheader("Leaderboard")
st.dataframe(filtered, use_container_width=True)

# Stats
col1, col2, col3 = st.columns(3)
col1.metric("Teams", len(df))
col2.metric("Avg Score", round(df["total_score"].mean(), 2))
col3.metric("Top Score", df["total_score"].max())

# Chart
st.bar_chart(df.set_index("team_name")["total_score"])
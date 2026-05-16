import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import streamlit as st

# ── Konfiguration ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Sensor-Auswertung",
    page_icon="🌡️",
    layout="wide",
)

FARBEN = {
    "indoor":     "#4C9BE8",
    "outdoor":    "#57B56E",
    "greenhouse": "#E88C4C",
}
TREND_FARBEN = {
    "indoor":     "#1A5FA8",
    "outdoor":    "#2A7A44",
    "greenhouse": "#A84A1A",
}

# ── Daten laden ───────────────────────────────────────────────────────────────

@st.cache_data
def lade_daten() -> pd.DataFrame:
    with sqlite3.connect("/app/data/analysis.db") as conn:
        conn.row_factory = sqlite3.Row
        df = pd.read_sql_query(
            "SELECT datum, kategorie, temperatur FROM sensor_data ORDER BY datum",
            conn,
            parse_dates=["datum"],
        )
    return df

df_roh = lade_daten()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Filter")
    st.markdown("---")

    alle_kategorien = sorted(df_roh["kategorie"].unique())
    auswahl = st.multiselect(
        "Kategorien anzeigen",
        options=alle_kategorien,
        default=alle_kategorien,
        format_func=str.capitalize,
    )

    st.markdown("---")
    sigma = st.slider(
        "Anomalie-Schwelle (σ)",
        min_value=1.0,
        max_value=3.0,
        value=1.5,
        step=0.1,
        help="Wie viele Standardabweichungen über dem 7-Tage-Mittelwert gilt als Anomalie?",
    )
    st.markdown("---")
    st.caption("Datenquelle: `analysis.db`")

if not auswahl:
    st.warning("Bitte mindestens eine Kategorie in der Sidebar auswählen.")
    st.stop()

df = df_roh[df_roh["kategorie"].isin(auswahl)].copy()

# ── Rolling Average berechnen ─────────────────────────────────────────────────

def rolling_frame(gruppe: pd.DataFrame) -> pd.DataFrame:
    tmp = gruppe.set_index("datum").sort_index()[["temperatur", "kategorie"]].copy()
    tmp["rolling_7d"]  = tmp["temperatur"].rolling("7D").mean()
    tmp["rolling_std"] = tmp["temperatur"].rolling("7D").std()
    return tmp

df_rolling = pd.concat(
    rolling_frame(g) for _, g in df.groupby("kategorie")
).sort_index()

# ── Titel ─────────────────────────────────────────────────────────────────────

st.title("🌡️ Sensor-Temperatur-Auswertung")
st.markdown("Interaktive Analyse der Sensordaten aus `analysis.db`.")
st.markdown("---")

# ── KPI-Kacheln ───────────────────────────────────────────────────────────────

cols = st.columns(len(auswahl))
for col, kat in zip(cols, sorted(auswahl)):
    serie = df[df["kategorie"] == kat]["temperatur"]
    col.metric(
        label=f"⬥ {kat.capitalize()} – Median",
        value=f"{serie.median():.1f} °C",
        delta=f"±{serie.std():.1f} °C Stddev",
    )

st.markdown("---")

# ── Diagramm ──────────────────────────────────────────────────────────────────

st.subheader("Temperaturverlauf mit 7-Tage-Trend")

fig, ax = plt.subplots(figsize=(14, 5))

for kat in sorted(auswahl):
    teil = df_rolling[df_rolling["kategorie"] == kat]
    ax.plot(
        teil.index, teil["temperatur"],
        color=FARBEN[kat], lw=0.8, alpha=0.5,
        label=f"{kat.capitalize()} – Messwert",
    )
    ax.plot(
        teil.index, teil["rolling_7d"],
        color=TREND_FARBEN[kat], lw=2.5,
        label=f"{kat.capitalize()} – 7-Tage-Trend",
    )

ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
plt.xticks(rotation=30, ha="right")
ax.set_xlabel("Datum", fontsize=11)
ax.set_ylabel("Temperatur (°C)", fontsize=11)
ax.legend(fontsize=9, framealpha=0.85)
ax.grid(True, linestyle="--", alpha=0.35)
fig.tight_layout()

st.pyplot(fig)
plt.close(fig)

# ── Statistik-Tabellen ────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("Statistik")

tab_global, tab_kat = st.tabs(["Global", "Nach Kategorie"])

def stats_df(label: str, serie: pd.Series) -> dict:
    return {
        "Kategorie":   label,
        "Min (°C)":    round(serie.min(), 2),
        "Max (°C)":    round(serie.max(), 2),
        "Median (°C)": round(serie.median(), 2),
        "Stddev (°C)": round(serie.std(), 2),
        "Anzahl":      int(serie.count()),
    }

with tab_global:
    st.dataframe(
        pd.DataFrame([stats_df("Alle ausgewählten", df["temperatur"])]),
        width='stretch',
        hide_index=True,
    )

with tab_kat:
    rows = [stats_df(kat, df[df["kategorie"] == kat]["temperatur"]) for kat in sorted(auswahl)]
    st.dataframe(
        pd.DataFrame(rows),
        width='stretch',
        hide_index=True,
    )

# ── Anomalie-Erkennung Gewächshaus ────────────────────────────────────────────

if "greenhouse" in auswahl:
    st.markdown("---")
    st.subheader("⚠️ Gewächshaus-Anomalien")

    gh = df_rolling[df_rolling["kategorie"] == "greenhouse"].copy()
    gh["obere_grenze"] = gh["rolling_7d"] + sigma * gh["rolling_std"]
    anomalien = gh[gh["temperatur"] > gh["obere_grenze"]].dropna(subset=["obere_grenze"])

    if anomalien.empty:
        st.success(f"Keine Anomalien bei σ = {sigma} gefunden.")
    else:
        anzeige = anomalien[["temperatur", "rolling_7d", "obere_grenze"]].copy()
        anzeige.index = anzeige.index.strftime("%d.%m.%Y")
        anzeige.index.name = "Datum"
        anzeige.columns = ["Messwert (°C)", "7-Tage-Ø (°C)", f"Grenze Ø+{sigma}σ (°C)"]
        anzeige = anzeige.round(2)
        st.error(f"{len(anomalien)} Anomalie(n) erkannt (σ-Schwelle: {sigma})")
        st.dataframe(anzeige, width='stretch')

# ── Rohdaten ─────────────────────────────────────────────────────────────────

with st.expander("Rohdaten anzeigen"):
    st.dataframe(
        df.sort_values("datum", ascending=False).reset_index(drop=True),
        width='stretch',
        hide_index=True,
    )

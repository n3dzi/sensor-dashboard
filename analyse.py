import sqlite3
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import date, timedelta

# ── 1. DB-Setup ──────────────────────────────────────────────────────────────

rng = np.random.default_rng(42)

tage = [date.today() - timedelta(days=i) for i in range(99, -1, -1)]
kategorien = rng.choice(["indoor", "outdoor", "greenhouse"], size=100)

# Basistemperatur: leichter saisonaler Verlauf + Rauschen
basis = np.linspace(18, 28, 100) + rng.normal(0, 2.5, 100)
temperaturen = np.clip(basis, 15, 32)

with sqlite3.connect("/app/data/analysis.db") as conn:
    conn.row_factory = sqlite3.Row
    conn.execute("DROP TABLE IF EXISTS sensor_data")
    conn.execute("""
        CREATE TABLE sensor_data (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            datum     TEXT    NOT NULL,
            kategorie TEXT    NOT NULL,
            temperatur REAL   NOT NULL
        )
    """)
    conn.executemany(
        "INSERT INTO sensor_data (datum, kategorie, temperatur) VALUES (?, ?, ?)",
        [(str(d), str(k), round(float(t), 2)) for d, k, t in zip(tage, kategorien, temperaturen)],
    )
    conn.commit()

print("✔ Datenbank angelegt und 100 Datensätze eingefügt.\n")

# ── 2. Analyse ────────────────────────────────────────────────────────────────

with sqlite3.connect("/app/data/analysis.db") as conn:
    conn.row_factory = sqlite3.Row
    df = pd.read_sql_query(
        "SELECT datum, kategorie, temperatur FROM sensor_data ORDER BY datum",
        conn,
        parse_dates=["datum"],
    )

def stats_row(label: str, series: pd.Series) -> dict:
    return {
        "Kategorie": label,
        "Min (°C)":    round(series.min(), 2),
        "Max (°C)":    round(series.max(), 2),
        "Median (°C)": round(series.median(), 2),
        "Stddev (°C)": round(series.std(), 2),
        "Anzahl":      int(series.count()),
    }

def stats(series: pd.Series) -> str:
    return (
        f"  Min:    {series.min():.2f} °C\n"
        f"  Max:    {series.max():.2f} °C\n"
        f"  Median: {series.median():.2f} °C\n"
        f"  Stddev: {series.std():.2f} °C"
    )

print("══════════════════════════════════════════")
print("  Globale Statistik (alle Kategorien)")
print("══════════════════════════════════════════")
print(stats(df["temperatur"]))
print()

print("══════════════════════════════════════════")
print("  Statistik nach Kategorie")
print("══════════════════════════════════════════")
for kat, gruppe in df.groupby("kategorie"):
    print(f"\n  [{kat.upper()}]")
    print(stats(gruppe["temperatur"]))
print()

# ── Excel-Export ──────────────────────────────────────────────────────────────

df_global = pd.DataFrame([stats_row("Alle Kategorien", df["temperatur"])])

df_kategorien = pd.DataFrame([
    stats_row(kat, gruppe["temperatur"])
    for kat, gruppe in df.groupby("kategorie")
])

with pd.ExcelWriter("statistik.xlsx", engine="openpyxl") as writer:
    df_global.to_excel(writer, sheet_name="Global", index=False)
    df_kategorien.to_excel(writer, sheet_name="Nach Kategorie", index=False)

print("✔ Excel-Export gespeichert: statistik.xlsx")

# ── Rolling Average (7 Tage) pro Kategorie ───────────────────────────────────

df = df.set_index("datum").sort_index()

rolling_frames = []
for kat, gruppe in df.groupby("kategorie"):
    tmp = gruppe[["temperatur"]].copy()
    tmp["rolling_7d"] = tmp["temperatur"].rolling("7D").mean()
    tmp["kategorie"] = kat
    rolling_frames.append(tmp)

df_rolling = pd.concat(rolling_frames).sort_index()

# ── Anomalie-Erkennung Gewächshaus ────────────────────────────────────────────

def pruefe_greenhouse_anomalien(df_roll: pd.DataFrame, sigma: float = 1.5) -> None:
    gh = df_roll[df_roll["kategorie"] == "greenhouse"].copy()
    gh["rolling_std"] = gh["temperatur"].rolling("7D").std()
    gh["obere_grenze"] = gh["rolling_7d"] + sigma * gh["rolling_std"]
    anomalien = gh[gh["temperatur"] > gh["obere_grenze"]].dropna(subset=["obere_grenze"])

    print("══════════════════════════════════════════")
    print("  Gewächshaus-Anomalien (> Ø+1.5σ, 7-Tage)")
    print("══════════════════════════════════════════")
    if anomalien.empty:
        print("  ✔ Keine Anomalien gefunden.\n")
        return
    for datum, zeile in anomalien.iterrows():
        print(
            f"  ⚠ WARNUNG  {datum.strftime('%d.%m.%Y')}  "
            f"{zeile['temperatur']:.2f} °C  "
            f"(Grenze: {zeile['obere_grenze']:.2f} °C, "
            f"Ø: {zeile['rolling_7d']:.2f} °C)"
        )
    print(f"\n  → {len(anomalien)} Anomalie(n) erkannt.\n")

pruefe_greenhouse_anomalien(df_rolling)

# ── 3. Visualisierung ─────────────────────────────────────────────────────────

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

fig, ax = plt.subplots(figsize=(14, 6))

for kat in ["indoor", "outdoor", "greenhouse"]:
    teil = df_rolling[df_rolling["kategorie"] == kat]
    ax.plot(
        teil.index, teil["temperatur"],
        color=FARBEN[kat], lw=0.8, alpha=0.55,
        label=f"{kat.capitalize()} – Messwert",
    )
    ax.plot(
        teil.index, teil["rolling_7d"],
        color=TREND_FARBEN[kat], lw=2.5, alpha=0.95,
        label=f"{kat.capitalize()} – 7-Tage-Trend",
    )

ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
plt.xticks(rotation=35, ha="right")

ax.set_title("Temperaturverlauf nach Kategorie\nmit 7-Tage-Rolling-Average", fontsize=14, fontweight="bold", pad=12)
ax.set_xlabel("Datum", fontsize=11)
ax.set_ylabel("Temperatur (°C)", fontsize=11)
ax.legend(loc="upper left", fontsize=9, framealpha=0.85)
ax.grid(True, linestyle="--", alpha=0.4)

fig.tight_layout()
fig.savefig("sensor_trend.png", dpi=150)
print("✔ Diagramm gespeichert: sensor_trend.png")

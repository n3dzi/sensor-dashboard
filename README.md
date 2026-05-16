# Sensor-Temperatur-Auswertung

Ein containerisiertes Analyse- und Dashboard-System für Temperatursensoren (Indoor, Outdoor, Gewächshaus). Die Datenpipeline erzeugt eine SQLite-Datenbank, wertet sie statistisch aus und stellt die Ergebnisse in einem interaktiven Streamlit-Dashboard bereit.

---

## Features

- **Datenpipeline** (`analyse.py`): Generiert Sensordaten, befüllt eine SQLite-DB, berechnet Statistiken, erkennt Anomalien (σ-Schwelle) und exportiert einen Excel-Report
- **Interaktives Dashboard** (`app.py`): Streamlit-App mit Zeitreihenplot, 7-Tage-Rolling-Average, KPI-Kacheln und konfigurierbarer Anomalie-Erkennung
- **Containerisiert**: Läuft als Docker-Container auf Proxmox LXC 103 — kein lokales Python-Setup erforderlich
- **Persistente Daten**: SQLite-Datenbank wird über ein benanntes Docker-Volume gesichert

---

## Architektur

Das System besteht aus zwei Python-Modulen, die innerhalb eines einzigen Containers ausgeführt werden. Der `entrypoint.sh` steuert den Startup: Falls noch keine Datenbank vorhanden ist, wird `analyse.py` automatisch ausgeführt, bevor Streamlit startet.

```
┌─────────────────────────────────────────────┐
│               Startup-Sequenz                │
│                                             │
│  entrypoint.sh                              │
│       │                                     │
│       ├─ DB vorhanden? ──Nein──▶ analyse.py │
│       │                              │      │
│       │                              ▼      │
│       │                        analysis.db  │
│       │                                     │
│       └──────────────▶ streamlit app.py     │
└─────────────────────────────────────────────┘
```

### Datenfluss

```
analyse.py
    │
    ├── Sensordaten generieren (NumPy)
    ├── SQLite-DB befüllen ──────────────▶ analysis.db
    ├── Statistiken berechnen (Pandas)
    ├── Anomalien erkennen (σ-Schwelle)
    └── Excel-Export ───────────────────▶ statistik.xlsx

app.py (Streamlit)
    │
    ├── analysis.db lesen (Pandas + SQLite)
    ├── Rolling Average berechnen (7 Tage)
    ├── KPI-Kacheln rendern
    ├── Zeitreihenplot (Matplotlib)
    └── Anomalie-Tabelle (Gewächshaus)
```

---

## ASCII-Infrastruktur

```
  Proxmox-Host
  ┌──────────────────────────────────────────────────────────────┐
  │  LXC Container 103  (<HOST-IP>)                         │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  Docker Engine                                         │  │
  │  │  ┌──────────────────────────────────────────────────┐  │  │
  │  │  │  Container: sensor-dashboard                     │  │  │
  │  │  │  Image:     python:3.13-slim                     │  │  │
  │  │  │  WORKDIR:   /app                                 │  │  │
  │  │  │                                                  │  │  │
  │  │  │   entrypoint.sh                                  │  │  │
  │  │  │       │                                          │  │  │
  │  │  │       ├──▶ analyse.py ──▶ /app/data/analysis.db ◀──┐ │  │  │
  │  │  │       │                                        │ │  │  │
  │  │  │       └──▶ streamlit app.py ───────────────────┘ │  │  │
  │  │  │              │                                   │  │  │
  │  │  │              │  Port 8501                        │  │  │
  │  │  └──────────────┼───────────────────────────────────┘  │  │
  │  │                 │                                       │  │
  │  │  Docker Volume: sensor_db (/app/data)                   │  │
  │  │  ┌─────────────────────────────────┐                    │  │
  │  │  │  analysis.db  (SQLite)          │                    │  │
  │  │  │  statistik.xlsx (Excel-Export)  │                    │  │
  │  │  └─────────────────────────────────┘                    │  │
  │  └────────────────────────────────────────────────────────┘  │
  └──────────────────────────────────────────────────────────────┘
         │
         │  HTTP  :8501
         ▼
   Browser / LAN-Client
   http://<HOST-IP>:8501
```

---

## Tech-Stack

| Komponente   | Version       |
|--------------|---------------|
| Python       | 3.13-slim     |
| Streamlit    | 1.57.0        |
| Pandas       | 3.0.3         |
| Matplotlib   | 3.10.9        |
| NumPy        | 2.4.5         |
| openpyxl     | 3.1.5         |
| SQLite       | (stdlib)      |
| Docker       | Compose v2    |

---

## Docker-Setup

### Voraussetzungen

- Docker & Docker Compose installiert
- Port `8501` auf dem Host verfügbar

### Container bauen und starten

```bash
# Image bauen und Container starten
docker compose up -d --build

# Logs verfolgen
docker compose logs -f

# Container stoppen
docker compose down
```

### Dashboard aufrufen

```
http://<HOST-IP>:8501
```

Auf dem Proxmox-LXC 103: `http://<HOST-IP>:8501`

### Container-Status prüfen

```bash
docker ps
docker compose ps
```

---

## Healthcheck

Der Container überwacht sich selbst mit einem eingebauten Docker-HEALTHCHECK. Er prüft alle 30 Sekunden zwei Dinge:

1. **Streamlit antwortet** — HTTP-Request auf `http://localhost:8501/_stcore/health`
2. **Datenbank erreichbar** — `SELECT 1` auf `/app/data/analysis.db`

### Parameter

| Parameter        | Wert  | Bedeutung                                           |
|------------------|-------|-----------------------------------------------------|
| `--interval`     | 30s   | Prüfung alle 30 Sekunden                            |
| `--timeout`      | 10s   | Gilt als fehlgeschlagen, wenn keine Antwort in 10s  |
| `--start-period` | 40s   | Wartezeit beim Start, bevor Fehler gezählt werden   |
| `--retries`      | 3     | Nach 3 Fehlern in Folge → Status `unhealthy`        |

### Status im Cluster abfragen

**Kurzstatus (healthy / starting / unhealthy):**
```bash
docker inspect --format='{{.State.Health.Status}}' sensor-dashboard
```

**Übersicht aller Container inkl. Health-Status:**
```bash
docker compose ps
# oder
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Letzten 5 Healthcheck-Ergebnisse mit Zeitstempel und Output:**
```bash
docker inspect --format='{{json .State.Health}}' sensor-dashboard | python3 -m json.tool
```

**Nur den letzten Healthcheck-Log anzeigen:**
```bash
docker inspect sensor-dashboard \
  --format='{{range .State.Health.Log}}{{.Start}} — {{.Output}}{{end}}' \
  | tail -1
```

**Auf `healthy` warten (z.B. in einem Deploy-Skript):**
```bash
until [ "$(docker inspect --format='{{.State.Health.Status}}' sensor-dashboard)" = "healthy" ]; do
  echo "Warte auf Container..."; sleep 5
done
echo "Container ist bereit."
```

### Mögliche Status

| Status      | Bedeutung                                                  |
|-------------|------------------------------------------------------------|
| `starting`  | Container läuft, `--start-period` ist noch nicht abgelaufen |
| `healthy`   | Alle Prüfungen erfolgreich                                 |
| `unhealthy` | 3 Prüfungen in Folge fehlgeschlagen — Container neu starten |

---

## Persistente Daten (Volumes)

Die SQLite-Datenbank wird über ein **benanntes Docker-Volume** gesichert, sodass sie bei Container-Neustarts oder `-Updates erhalten bleibt.

```yaml
# docker-compose.yml
volumes:
  sensor_db:          # benanntes Volume

services:
  sensor-dashboard:
    volumes:
      - sensor_db:/app/data   # gemountet unter /app/data
```

### Volume-Verwaltung

```bash
# Alle Volumes auflisten
docker volume ls

# Volume inspizieren (Mountpfad auf dem Host)
docker volume inspect analytische-auswertung_sensor_db

# Daten im laufenden Container einsehen
docker exec -it sensor-dashboard ls /app/data

# Volume löschen (Achtung: löscht alle gespeicherten Daten!)
docker volume rm analytische-auswertung_sensor_db
```

> **Hinweis:** Beim ersten Start prüft `entrypoint.sh`, ob `analysis.db` bereits existiert. Ist sie nicht vorhanden, wird `analyse.py` automatisch ausgeführt und die Datenbank neu befüllt.

---

## Projektstruktur

```
analytische-auswertung/
├── app.py              # Streamlit-Dashboard
├── analyse.py          # Datenpipeline & Anomalie-Erkennung
├── entrypoint.sh       # Container-Startup-Logik
├── Dockerfile          # Image-Definition
├── docker-compose.yml  # Service- & Volume-Konfiguration
├── requirements.txt    # Python-Abhängigkeiten
├── analysis.db         # SQLite-Datenbank (lokal / via Volume)
├── statistik.xlsx      # Excel-Export der Statistiken
└── sensor_trend.png    # Exportierter Trendplot
```

---

## Datenbank-Schema

```sql
CREATE TABLE sensor_data (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    datum      TEXT    NOT NULL,   -- ISO-Datum  YYYY-MM-DD
    kategorie  TEXT    NOT NULL,   -- indoor | outdoor | greenhouse
    temperatur REAL    NOT NULL    -- Grad Celsius
);
```

---

## Umgebungsvariablen

| Variable | Standard       | Beschreibung              |
|----------|----------------|---------------------------|
| `TZ`     | `Europe/Berlin`| Zeitzone des Containers   |

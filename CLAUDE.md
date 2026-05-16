# Analytische Auswertung Projekt

## System Behavior & Rules
- **Look Before You Leap:** Analyze the codebase and data structure first, create a plan, and ask for permission (`[Go/No-Go]`) before writing code.
- **Python & SQLite:** Use parameterized queries and context managers (`with sqlite3.connect...`). Always set `conn.row_factory = sqlite3.Row`.
- **Data Analysis & Plots:** Use `pandas` for database queries and calculations. Save charts as high-resolution PNGs into the project root or a plots folder. Do not use `plt.show()`.
- **Clean Environment:** Keep the project root clean. Put data source files, scripts, and output plots in logical places if the project grows.

FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py analyse.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "\
import urllib.request, sqlite3; \
urllib.request.urlopen('http://localhost:8501/_stcore/health'); \
conn = sqlite3.connect('/app/data/analysis.db'); \
conn.execute('SELECT 1'); \
conn.close()" || exit 1

ENTRYPOINT ["./entrypoint.sh"]

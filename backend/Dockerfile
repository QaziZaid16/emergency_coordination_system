FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY start.sh ./start.sh
EXPOSE 8000
CMD ["sh", "./start.sh", "serve"]

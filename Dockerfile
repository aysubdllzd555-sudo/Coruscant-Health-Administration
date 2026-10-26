# Portable image for Cloud Run / ECS / Azure Container Apps / Fly.io
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN DJANGO_SECRET_KEY=build python manage.py collectstatic --no-input
RUN useradd -m cha && chown -R cha /app
USER cha
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --no-input && python manage.py seed_cha ${SEED_DEMO:+--demo} && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --workers 2"]

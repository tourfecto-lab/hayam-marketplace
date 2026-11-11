FROM node:22-alpine AS assets
WORKDIR /build
COPY package*.json ./
RUN npm ci
COPY static ./static
COPY templates ./templates
COPY scripts ./scripts
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.6 && useradd --uid 10001 --create-home hayam
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
COPY --from=assets /build/static/app.css ./static/app.css
COPY --from=assets /build/static/vendor ./static/vendor
RUN mkdir -p /app/media /app/staticfiles && chown -R hayam:hayam /app
USER hayam
ENV PATH="/app/.venv/bin:$PATH" DJANGO_SETTINGS_MODULE=config.settings.production
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "--error-logfile", "-"]

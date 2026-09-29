FROM python:3.12-slim
ARG IMAGE_TAG=afyaplus-triage:dev
ARG GIT_SHA=unknown
ENV IMAGE_TAG=${IMAGE_TAG} GIT_SHA=${GIT_SHA} PYTHONUNBUFFERED=1
LABEL org.opencontainers.image.title="afyaplus-triage" \
      org.opencontainers.image.revision="${GIT_SHA}"
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY VERSION release.json ./
COPY prompts/ prompts/
COPY config/ config/
COPY mcp_server/ mcp_server/
COPY app/ app/
COPY scripts/ scripts/
# Build fails if versions are out of alignment
RUN python scripts/check_release.py
EXPOSE 8000
CMD ["uvicorn", "app.prompt_app:app", "--host", "0.0.0.0", "--port", "8000"]

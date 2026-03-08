FROM python:3.12-slim AS base

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra backend

COPY bootstrap/ bootstrap/
COPY wikigr/ wikigr/
COPY backend/ backend/
COPY mcp_server.py config.yaml ./

FROM base AS backend
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS mcp
CMD ["uv", "run", "python", "mcp_server.py"]

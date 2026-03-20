# RetailGPT — Multi-stage Dockerfile
# Stage 1: Node.js generates the SQLite prototype DB
# Stage 2: Python runs the FastAPI server

# ── Stage 1: Seed the database ────────────────────────────────────────────────
FROM node:20-alpine AS seeder
WORKDIR /seed

COPY package*.json ./
RUN npm install

COPY scripts/generate_synthetic_data.js scripts/
RUN node scripts/generate_synthetic_data.js

# ── Stage 2: Python API ────────────────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy the pre-seeded DB from stage 1
COPY --from=seeder /seed/retailgpt_prototype.db /app/retailgpt_prototype.db

ENV DB_URL=sqlite:///./retailgpt_prototype.db
ENV SYNTHETIC_DATA_MODE=true

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

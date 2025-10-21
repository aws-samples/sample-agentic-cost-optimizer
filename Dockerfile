# Use uv's Python base image (following AWS Bedrock Agent Core pattern)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv (frozen for reproducible builds)
RUN uv sync --group agents --frozen --no-cache

# Copy source code
COPY src/ ./src/

# Set Python path to include src directory
ENV PYTHONPATH=/app/src

# Expose port for the agent service
EXPOSE 8080

# Run the agent application with OpenTelemetry instrumentation
CMD ["uv", "run", "opentelemetry-instrument", "python", "-m", "agents.main"]
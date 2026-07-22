FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy and install IdentityOS first (monorepo dependency)
COPY pyproject.toml /app/
COPY README.md /app/
COPY runtime/ /app/runtime/
COPY core/ /app/core/
COPY adapters/ /app/adapters/
COPY identity_graph/ /app/identity_graph/
COPY sdk/ /app/sdk/
COPY identityos/ /app/identityos/
COPY cli/ /app/cli/

# Copy the Discord agent
COPY examples/discord-agent/ /app/examples/discord-agent/

# Install dependencies
RUN pip install --no-cache-dir -e /app && \
    pip install --no-cache-dir discord.py python-dotenv

WORKDIR /app/examples/discord-agent

# Healthcheck
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" || exit 1

# Run
CMD ["python3", "main.py"]

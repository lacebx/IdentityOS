.PHONY: run docker-build docker-up docker-down test lint clean

# ── Local ─────────────────────────────────────────────────────────────────────

run:
	@echo "Starting Discord Agent..."
	python3 main.py

test:
	@echo "Running agent tests..."
	python3 -m pytest tests/ -v

lint:
	@echo "Checking imports (no internal runtime imports)..."
	python3 -m pytest tests/ -k "no_internal_imports" -v

clean:
	@echo "Cleaning..."
	rm -rf __pycache__ .pytest_cache
	rm -rf tests/__pycache__ commands/__pycache__ listeners/__pycache__
	rm -rf pipeline/__pycache__ scheduler/__pycache__ services/__pycache__

# ── Docker ────────────────────────────────────────────────────────────────────

docker-build:
	@echo "Building Docker image..."
	docker compose build

docker-up:
	@echo "Starting Docker container..."
	docker compose up -d
	@echo "Container started. Check logs with 'make docker-logs'"

docker-down:
	@echo "Stopping Docker container..."
	docker compose down

docker-logs:
	docker compose logs -f

docker-restart: docker-down docker-up

docker-shell:
	docker compose exec discord-agent python3

# ── Identity ──────────────────────────────────────────────────────────────────

inspect:
	@echo "=== Identity ==="
	python3 -c "
from identityos import Identity
i = Identity.load('${ID}') if '${ID}' else None
if i:
    d = i.describe()
    for k, v in d.items():
        print(f'{k}: {v}')
    print('--- Goals ---')
    for g in i.goals('all'):
        print(f'  {g[\"title\"]} [{g[\"status\"]}]')
    print('--- Intentions ---')
    for it in i.intentions('all'):
        print(f'  {it[\"description\"]} [{it[\"status\"]}]')
    print('--- Relationships ---')
    for r in i.relationships():
        print(f'  {r[\"target_id\"]} ({r[\"edge_type\"]}, trust={r[\"trust_level\"]})')
    print('--- Timeline ---')
    for e in i.timeline(10):
        print(f'  {e[\"title\"]} ({e.get(\"occurred_at\", \"?\")[:10]})')
else:
    print('Usage: make inspect ID=your-identity-id')
"

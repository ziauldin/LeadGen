# Shortcuts. On Windows use the scripts/ PowerShell helpers or run the commands directly.
.PHONY: up down logs seed test test-api test-web e2e gen-api lint

up:            ## Start the full stack in Docker
	docker compose up --build -d
down:
	docker compose down
logs:
	docker compose logs -f api worker beat
seed:          ## Demo data (prints the demo password)
	docker compose exec api python scripts/seed.py
lint:
	cd services/api && ruff check . && ruff format --check . && mypy app
	cd apps/web && npm run lint && npm run typecheck
test-api:
	cd services/api && pytest -q
test-web:
	cd apps/web && npm test
test: test-api test-web
e2e:
	cd apps/web && npm run e2e
gen-api:       ## Regenerate the web app's API types
	cd apps/web && npm run gen:api

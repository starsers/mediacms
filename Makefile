ifeq ($(OS),Windows_NT)
COPY_STATIC = powershell -NoProfile -Command "Copy-Item -Path 'frontend/dist/static/*' -Destination 'static/' -Recurse -Force"
else
COPY_STATIC = cp -r frontend/dist/static/* static/
endif

COMPOSE_DEV = docker compose -f docker-compose-dev.yaml
COMPOSE_DEV_FULL = docker compose -f docker-compose-dev.yaml -f docker-compose-dev.full.yaml

.PHONY: admin-shell build-frontend dev-full-build dev-full-up dev-full-down dev-full-logs

admin-shell:
	@container_id=$$(docker compose ps -q web); \
	if [ -z "$$container_id" ]; then \
		echo "Web container not found"; \
		exit 1; \
	else \
		docker exec -it $$container_id /bin/bash; \
	fi

build-frontend:
	$(COMPOSE_DEV) exec frontend npm run dist
	$(COPY_STATIC)
	$(COMPOSE_DEV) restart web

dev-full-build:
	$(COMPOSE_DEV_FULL) build migrations

dev-full-up: dev-full-build
	$(COMPOSE_DEV_FULL) up -d

dev-full-down:
	$(COMPOSE_DEV_FULL) down

dev-full-logs:
	$(COMPOSE_DEV_FULL) logs -f web celery_worker

test:
	$(COMPOSE_DEV) exec --env TESTING=True -T web pytest


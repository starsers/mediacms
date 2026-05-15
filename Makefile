ifeq ($(OS),Windows_NT)
COPY_STATIC = powershell -NoProfile -Command "Copy-Item -Path 'frontend/dist/static/*' -Destination 'static/' -Recurse -Force"
else
COPY_STATIC = cp -r frontend/dist/static/* static/
endif

.PHONY: admin-shell build-frontend

admin-shell:
	@container_id=$$(docker compose ps -q web); \
	if [ -z "$$container_id" ]; then \
		echo "Web container not found"; \
		exit 1; \
	else \
		docker exec -it $$container_id /bin/bash; \
	fi

build-frontend:
	docker compose -f docker-compose-dev.yaml exec frontend npm run dist
	$(COPY_STATIC)
	docker compose -f docker-compose-dev.yaml restart web

test:
	docker compose -f docker-compose-dev.yaml exec --env TESTING=True -T web pytest


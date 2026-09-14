COMPOSE := docker compose

.PHONY: up down logs shell migrate test css

up:            ## Levanta el proyecto en http://localhost:8000
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d --build

down:          ## Para los contenedores
	$(COMPOSE) down

logs:          ## Sigue los logs de web
	$(COMPOSE) logs -f web

shell:         ## Shell de Django dentro del contenedor
	$(COMPOSE) exec web python manage.py shell

migrate:       ## Aplica migraciones
	$(COMPOSE) exec web python manage.py migrate

test:          ## Ejecuta los tests
	$(COMPOSE) exec web pytest

css:           ## Compila Tailwind (usa WATCH=1 para modo vigilancia)
	@bin/tailwind.sh $(if $(WATCH),--watch,) $(if $(MINIFY),--minify,)

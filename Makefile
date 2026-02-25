SHELL := /bin/sh

.PHONY: help env.sync up down ps logs db.clear db.reset db.migrate db.migrate.new db.seed test

COMPOSE ?= docker compose
TEST_PROFILE ?= test
TEST_SERVICE ?= e2e
KEEP_TEST_STACK ?= 0
MIGRATION_NAME ?= schema_update
ENV_SYNC_TARGETS := up down ps logs db.clear db.reset db.migrate db.migrate.new db.seed test

$(ENV_SYNC_TARGETS): env.sync

ifdef NO_COLOR
C_RESET :=
C_BOLD :=
C_DIM :=
C_PRIMARY :=
C_INFO :=
C_OK :=
C_WARN :=
C_ERR :=
C_CMD :=
else
C_RESET := \033[0m
C_BOLD := \033[1m
C_DIM := \033[2m
C_PRIMARY := \033[36m
C_INFO := \033[94m
C_OK := \033[32m
C_WARN := \033[33m
C_ERR := \033[31m
C_CMD := \033[35m
endif

define _title
@printf "\n$(C_BOLD)$(C_PRIMARY)========================================$(C_RESET)\n"
@printf "$(C_BOLD)$(C_PRIMARY)%s$(C_RESET)\n" "$(1)"
@printf "$(C_BOLD)$(C_PRIMARY)========================================$(C_RESET)\n"
endef

define _info
@printf "$(C_INFO)::$(C_RESET) %s\n" "$(1)"
endef

define _ok
@printf "$(C_OK)++$(C_RESET) %s\n" "$(1)"
endef

define _warn
@printf "$(C_WARN)!!$(C_RESET) %s\n" "$(1)"
endef

help: ## Show available commands
	@printf "$(C_BOLD)$(C_PRIMARY)HUMAN RATING PLATFORM$(C_RESET)\n"
	@printf "$(C_DIM)Modern local workflow commands$(C_RESET)\n"
	@printf "$(C_DIM)Set NO_COLOR=1 to disable styling$(C_RESET)\n\n"
	@printf "$(C_BOLD)Core$(C_RESET)\n"
	@printf "  $(C_CMD)%-18s$(C_RESET) %s\n" "make up" "Start db + alembic migrations + api (hot reload)"
	@printf "  $(C_CMD)%-18s$(C_RESET) %s\n" "make down" "Stop services (keep database volume)"
	@printf "  $(C_CMD)%-18s$(C_RESET) %s\n" "make ps" "Show running compose services"
	@printf "  $(C_CMD)%-18s$(C_RESET) %s\n" "make logs" "Tail db/api logs"
	@printf "\n$(C_BOLD)Database$(C_RESET)\n"
	@printf "  $(C_CMD)%-18s$(C_RESET) %s\n" "make db.clear" "Reset development database (destructive)"
	@printf "  $(C_CMD)%-18s$(C_RESET) %s\n" "make db.reset" "Rebuild database from Alembic migrations"
	@printf "  $(C_CMD)%-18s$(C_RESET) %s\n" "make db.migrate" "Apply committed Alembic migrations"
	@printf "  $(C_CMD)%-18s$(C_RESET) %s\n" "make db.migrate.new" "Autogenerate Alembic migration"
	@printf "  $(C_CMD)%-18s$(C_RESET) %s\n" "make db.seed" "Seed local dataset from backend/config.toml"
	@printf "\n$(C_BOLD)Testing$(C_RESET)\n"
	@printf "  $(C_CMD)%-18s$(C_RESET) %s\n" "make test" "Run characterization tests with db+migrations"
	@printf "\n$(C_BOLD)Setup$(C_RESET)\n"
	@printf "  $(C_CMD)%-18s$(C_RESET) %s\n" "make env.sync" "Create backend/.env and frontend/.env when missing"

env.sync: ## Create backend/.env and frontend/.env when missing
	@if [ -f backend/.env ]; then \
		printf "$(C_INFO)::$(C_RESET) backend/.env already exists\n"; \
	else \
		cp backend/.env.example backend/.env; \
		printf "$(C_OK)++$(C_RESET) Created backend/.env from backend/.env.example\n"; \
	fi
	@if [ -f frontend/.env ]; then \
		printf "$(C_INFO)::$(C_RESET) frontend/.env already exists\n"; \
	else \
		cp frontend/.env.example frontend/.env; \
		printf "$(C_OK)++$(C_RESET) Created frontend/.env from frontend/.env.example\n"; \
	fi

up: ## Start db + alembic migrations + api (hot reload)
	$(call _title,==> Bringing up local services)
	$(call _info,Step 1/3 - Starting Postgres)
	@$(COMPOSE) up -d db > /dev/null
	$(call _info,Step 2/3 - Applying Alembic migrations)
	@$(COMPOSE) up -d migrate > /dev/null
	$(call _info,Step 3/3 - Starting API (hot reload))
	@$(COMPOSE) up -d api > /dev/null
	$(call _ok,Services are up)
	@$(MAKE) --no-print-directory ps

down: ## Stop services (keep database volume)
	$(call _title,==> Stopping local services)
	@$(COMPOSE) down --remove-orphans > /dev/null
	$(call _ok,Services stopped)

ps: ## Show running compose services
	$(call _title,==> Service status)
	@$(COMPOSE) ps

logs: ## Tail db/api logs
	$(call _title,==> Streaming logs)
	$(call _info,Press Ctrl+C to stop following logs)
	@$(COMPOSE) logs -f --tail=200 db api

db.clear: ## Reset development database (destructive)
	$(call _title,==> Resetting local database)
	$(call _warn,This deletes local Postgres data volumes.)
	@$(COMPOSE) down --volumes --remove-orphans > /dev/null
	$(call _ok,Local database volumes removed)

db.reset: ## Rebuild database from migrations and start API
	$(call _title,==> Rebuilding database and services)
	@$(MAKE) --no-print-directory db.clear
	@$(MAKE) --no-print-directory up
	$(call _ok,Database reset complete)

db.migrate: ## Apply committed Alembic migrations
	$(call _title,==> Applying Alembic migrations)
	@$(COMPOSE) up -d db > /dev/null
	@until $(COMPOSE) exec -T db pg_isready -U postgres -d human_rating_platform > /dev/null 2>&1; do sleep 1; done
	@$(COMPOSE) run --rm --no-deps migrate
	$(call _ok,Migrations applied)

db.migrate.new: ## Autogenerate Alembic migration (set MIGRATION_NAME=...)
	$(call _title,==> Creating Alembic migration $(MIGRATION_NAME))
	@$(COMPOSE) up -d db > /dev/null
	@until $(COMPOSE) exec -T db pg_isready -U postgres -d human_rating_platform > /dev/null 2>&1; do sleep 1; done
	@$(COMPOSE) run --rm --no-deps migrate sh -c "uv sync --frozen --no-dev --no-install-project && uv run --no-sync python scripts/migrate.py revision --autogenerate -m '$(MIGRATION_NAME)'"
	$(call _ok,Migration created)

db.seed: ## Seed local dataset from backend/config.toml
	$(call _title,==> Seeding local dataset)
	@$(COMPOSE) up -d db > /dev/null
	@until $(COMPOSE) exec -T db pg_isready -U postgres -d human_rating_platform > /dev/null 2>&1; do sleep 1; done
	@$(COMPOSE) run --rm --no-deps migrate
	@$(COMPOSE) run --rm --no-deps migrate sh -c "uv sync --frozen --no-dev --no-install-project && uv run --no-sync python scripts/seed_dev.py"
	$(call _ok,Seed command finished)

test: ## Run characterization tests with DB+migrations as dependencies
	$(call _title,==> Running characterization tests)
	$(call _info,Using docker compose profile: $(TEST_PROFILE))
	$(call _info,Preparing db)
	@set +e; \
	$(COMPOSE) --profile $(TEST_PROFILE) up -d db > /dev/null; \
	until $(COMPOSE) --profile $(TEST_PROFILE) exec -T db pg_isready -U postgres -d human_rating_platform > /dev/null 2>&1; do sleep 1; done; \
	printf "$(C_INFO)::$(C_RESET) Applying migrations synchronously\n"; \
	$(COMPOSE) --profile $(TEST_PROFILE) run --rm --no-deps migrate > /dev/null; \
	printf "$(C_INFO)::$(C_RESET) Executing test service: $(TEST_SERVICE)\n"; \
	$(COMPOSE) --profile $(TEST_PROFILE) run --rm --no-deps $(TEST_SERVICE); \
	exit_code=$$?; \
	if [ "$(KEEP_TEST_STACK)" != "1" ]; then \
		$(COMPOSE) --profile $(TEST_PROFILE) down --remove-orphans > /dev/null; \
	else \
		printf "$(C_WARN)!!$(C_RESET) Keeping compose test stack up (KEEP_TEST_STACK=1)\n"; \
	fi; \
	if [ $$exit_code -eq 0 ]; then \
		printf "$(C_OK)++$(C_RESET) Characterization tests passed\n"; \
	else \
		printf "$(C_ERR)xx$(C_RESET) Characterization tests failed (exit=$$exit_code)\n"; \
	fi; \
	exit $$exit_code

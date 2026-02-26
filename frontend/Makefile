SHELL := /bin/sh

.PHONY: help deps up

help:
	@printf "Frontend commands\n"
	@printf "  make up    Install deps when needed, then run Vite dev server on 0.0.0.0:5173\n"
	@printf "  make deps  Install deps only when package.json/package-lock.json changed\n"

deps:
	@set -e; \
	current=$$(shasum package-lock.json package.json | shasum | awk '{print $$1}'); \
	stored=$$(cat node_modules/.deps-hash 2>/dev/null || true); \
	if [ ! -d node_modules ] || [ "$$current" != "$$stored" ]; then \
		echo "Installing frontend dependencies..."; \
		npm ci; \
		mkdir -p node_modules; \
		echo "$$current" > node_modules/.deps-hash; \
	else \
		echo "Frontend dependencies already up to date."; \
	fi

up: deps
	npm run dev -- --host 0.0.0.0 --port 5173

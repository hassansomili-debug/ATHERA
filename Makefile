.DEFAULT_GOAL := help
COMPOSE := docker compose -f infra/compose/docker-compose.dev.yml

help: ## عرض الأوامر | list targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n",$$1,$$2}'

dev: ## تشغيل المنظومة كاملة | run the full stack
	$(COMPOSE) up --build

down: ## إيقاف | stop
	$(COMPOSE) down

migrate: ## تطبيق الترحيلات | apply migrations
	cd infra/db && alembic upgrade head

migrate-down: ## التراجع خطوة | rollback one revision
	cd infra/db && alembic downgrade -1

test: test-api test-arch ## كل الاختبارات | all tests

test-offline: ## اختبارات لا تحتاج قاعدة بيانات | tests that need no database
	cd apps/api && pytest -q \
	  tests/test_at_s1_03_parsing_locators.py \
	  tests/test_at_s5_01_09_golden_thread.py tests/test_at_s5_10_11_methodology.py \
	  tests/test_at_s7_01_06_journals.py tests/test_at_s7_07_11_manuscript_review.py \
	  tests/test_at_s8_01_06_lineage_plan.py tests/test_at_s8_07_11_outputs_tools.py \
	  tests/test_at_s9_trend_intelligence.py

verify-constraints: ## يحاول كل ممنوع ويفشل إن نجح | attempt every forbidden action
	python3 scripts/verify_db_constraints.py

migrate-roundtrip: ## ترحيل كامل صعودًا ونزولًا | full up/down migration drill
	cd infra/db && alembic upgrade head && alembic downgrade base && alembic upgrade head

test-api: ## اختبارات القبول | acceptance tests AT-S0-*
	cd apps/api && pytest -v

test-arch: ## اختبارات معمارية | architecture boundary tests (§38.6.8)
	cd apps/api && lint-imports && pytest -v tests/test_at_s0_08_09_boundaries.py

lint: ## فحص | lint & type-check
	cd apps/api && ruff check . && mypy athera_api
	cd apps/web && pnpm lint && pnpm typecheck

openapi: ## توليد العقد | export OpenAPI contract
	cd apps/api && python -m athera_api.contracts > ../../packages/contracts/openapi.json

verify-audit: ## التحقق من سلسلة التدقيق | verify audit hash chain
	cd apps/api && python -m athera_api.services.audit_verify

.PHONY: help dev down migrate migrate-down test test-api test-arch test-offline \
	verify-constraints migrate-roundtrip lint openapi verify-audit

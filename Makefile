test-semantic-pgvector:
	docker compose -f docker-compose.test.yml up -d
	PYTHONPATH=. python -m pytest tests/integration/test_pgvector_semantic_store.py -q

validate-semantic-demo:
	docker exec metera-app sh -lc "cd /app && PYTHONPATH=. python scripts/demo_semantic_hit.py"

bootstrap-policy-store:
	docker exec metera-app sh -lc "cd /app && PYTHONPATH=. python scripts/bootstrap_policy_store.py"

validate-shadow-mode:
	python scripts/validate_shadow_mode.py

validate-shadow-stack:
	$(MAKE) bootstrap-policy-store
	$(MAKE) validate-semantic-demo
	$(MAKE) validate-shadow-mode

validate-system-slice:
	python scripts/validate_system_slice.py

test-in-container:
	docker compose up -d metera-test
	docker exec metera-test-runner sh -lc "cd /app && PYTHONPATH=. python -m pytest tests/test_semantic_store_backend.py tests/test_policy_state.py -q"

dashboard:
	docker compose up -d --build metera-dashboard

clean-semantic-pgvector:
	docker compose -f docker-compose.test.yml down -v

PY := uv run python
PYTEST := uv run pytest
CHECK := scripts/check_consumers.py

.PHONY: validate validate-consumer verify-baseline verify-perf

validate: ## Invariantes del core: estructura, plantillas, ADR-0, sintaxis, evidencia
	bash -n scripts/compat_check.sh
	$(PY) $(CHECK) --self
	$(PY) scripts/collect_metrics.py --self-auto
	$(PYTEST) -q

verify-baseline: ## Ejecuta el baseline de verificación y escribe docs/verification/{baseline.json,BASELINE.md}
	$(PY) scripts/verification_baseline.py --markdown

verify-perf: ## Ejecuta el baseline de rendimiento y escribe docs/verification/{perf.json,PERF.md}
	$(PY) scripts/verification_perf.py --markdown

validate-consumer: ## Invariantes de un repo consumidor: make validate-consumer CONSUMER=../mi-repo
	@test -n "$(CONSUMER)" || { echo "uso: make validate-consumer CONSUMER=<ruta>"; exit 2; }
	$(PY) $(CHECK) $(CONSUMER)
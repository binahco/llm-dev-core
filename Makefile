PY := uv run python
PYTEST := uv run pytest
CHECK := scripts/check_consumers.py

.PHONY: validate validate-consumer

validate: ## Invariantes del core: estructura, plantillas, ADR-0, sintaxis, evidencia
	bash -n scripts/compat_check.sh
	$(PY) $(CHECK) --self
	$(PY) scripts/collect_metrics.py --self-auto
	$(PYTEST) -q

validate-consumer: ## Invariantes de un repo consumidor: make validate-consumer CONSUMER=../mi-repo
	@test -n "$(CONSUMER)" || { echo "uso: make validate-consumer CONSUMER=<ruta>"; exit 2; }
	$(PY) $(CHECK) $(CONSUMER)
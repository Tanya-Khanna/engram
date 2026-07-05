# Engram — one-line demo commands. Every phase must keep these honest.

.PHONY: smoke-llm demo-cold demo-warm curator bench serve break-site test

smoke-llm:       ## one real qwen3.6-flash call, prints logged metrics
	.venv/bin/python -c "\
	from engram import llm, metrics; \
	r = llm.complete('smoke-llm', [{'role':'user','content':'Reply with exactly: ENGRAM OK'}], model_tier='cheap'); \
	print('reply:', r.choices[0].message.content); \
	import json; print('metrics:', json.dumps(metrics.summary(llm.SESSION_ID), indent=2))"

demo-cold:       ## vision-loop a task cold on Skyfinder, store Procedure (Phase 2)
	@echo "not built yet — Phase 2   usage: make demo-cold TASK=\"find a flight from SFO to Tokyo on July 20\""

demo-warm:       ## replay same task from memory, ~2s (Phase 2)
	@echo "not built yet — Phase 2"

curator:         ## run one Curator sweep now: consolidate, decay, reverify, relearn (Phase 3)
	@echo "not built yet — Phase 3"

bench:           ## run benchmark suite, export 3 charts to bench/out/ (Phase 3)
	@echo "not built yet — Phase 3"

serve:           ## FastAPI: /memories /recall /metrics (+/task /chat in Phase 2+)
	.venv/bin/uvicorn engram.server.api:app --host 0.0.0.0 --port 8080

serve-mcp:       ## MCP server over SSE on :8765 (stdio: python -m engram.server.mcp_server)
	.venv/bin/python -m engram.server.mcp_server --sse

break-site:      ## swap Skyfinder v1 → v2 — the staleness demo (Phase 3)
	@echo "not built yet — Phase 3"

test:
	pytest

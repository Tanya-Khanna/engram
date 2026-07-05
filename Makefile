# Engram — one-line demo commands. Every phase must keep these honest.

.PHONY: smoke-llm demo-cold demo-warm curator bench serve break-site test

smoke-llm:       ## one real qwen3.6-flash call, prints logged metrics
	.venv/bin/python -c "\
	from engram import llm, metrics; \
	r = llm.complete('smoke-llm', [{'role':'user','content':'Reply with exactly: ENGRAM OK'}], model_tier='cheap'); \
	print('reply:', r.choices[0].message.content); \
	import json; print('metrics:', json.dumps(metrics.summary(llm.SESSION_ID), indent=2))"

SKYFINDER_URL ?= http://127.0.0.1:8090
TASK ?= find the cheapest flight from SFO to NRT on 2026-07-20

demo-site:       ## run Skyfinder on :8090 (make break-site flips it to v2 live)
	cd demo-site && ../.venv/bin/uvicorn serve:app --port 8090

demo-cold:       ## vision-loop TASK cold on Skyfinder, consolidate + store Procedure
	.venv/bin/python -m engram.agent.worker --task "$(TASK)" --url $(SKYFINDER_URL) --force-cold

demo-warm:       ## same TASK from memory: recall → replay → flash-verify
	.venv/bin/python -m engram.agent.worker --task "$(TASK)" --url $(SKYFINDER_URL)

curator:         ## run one Curator sweep now: consolidate, decay, reverify, relearn (Phase 3)
	@echo "not built yet — Phase 3"

bench:           ## run benchmark suite, export 3 charts to bench/out/ (Phase 3)
	@echo "not built yet — Phase 3"

serve:           ## FastAPI: /memories /recall /metrics (+/task /chat in Phase 2+)
	.venv/bin/uvicorn engram.server.api:app --host 0.0.0.0 --port 8080

serve-mcp:       ## MCP server over SSE on :8765 (stdio: python -m engram.server.mcp_server)
	.venv/bin/python -m engram.server.mcp_server --sse

break-site:      ## swap Skyfinder v1 → v2 — the staleness demo
	echo v2 > demo-site/.version

restore-site:    ## back to Skyfinder v1
	echo v1 > demo-site/.version

test:
	pytest

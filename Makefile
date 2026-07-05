# Engram — one-line demo commands. Every phase must keep these honest.

.PHONY: smoke-llm demo-cold demo-warm curator bench serve break-site test

smoke-llm:       ## one real qwen3.6-flash call, prints logged metrics (Phase 1)
	@echo "not built yet — Phase 1"

demo-cold:       ## vision-loop a task cold on Skyfinder, store Procedure (Phase 2)
	@echo "not built yet — Phase 2   usage: make demo-cold TASK=\"find a flight from SFO to Tokyo on July 20\""

demo-warm:       ## replay same task from memory, ~2s (Phase 2)
	@echo "not built yet — Phase 2"

curator:         ## run one Curator sweep now: consolidate, decay, reverify, relearn (Phase 3)
	@echo "not built yet — Phase 3"

bench:           ## run benchmark suite, export 3 charts to bench/out/ (Phase 3)
	@echo "not built yet — Phase 3"

serve:           ## FastAPI: /task /memories /metrics /chat + MCP SSE (Phase 1+)
	@echo "not built yet — Phase 1"

break-site:      ## swap Skyfinder v1 → v2 — the staleness demo (Phase 3)
	@echo "not built yet — Phase 3"

test:
	pytest

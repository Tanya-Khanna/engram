# Engram build journal

5 bullets per phase: what broke, what we learned.

## Phase 0 — July 4 (compliance skeleton)
- Repo scaffolded: CLAUDE.md, full src tree, proof file, MIT license,
  Makefile stubs.
- Workspace API keys (`sk-ws-`) work fine on the compatible-mode endpoint —
  the format warning only applies to Token Plan (`sk-sp-`) keys.

## Phase 1 — July 4–5 (memory engine + MCP)
- qwen3.6-flash runs in thinking mode by default: 142 reasoning tokens and
  10s latency for a 3-token answer. `enable_thinking: false` via extra_body
  fixed it — now a first-class `think=` param on our llm wrapper. Would have
  silently destroyed the 2–4s warm-path budget in Phase 2.
- No Docker on the dev laptop → qdrant-client's embedded local mode instead;
  same interface, zero infra. Docker Qdrant stays for ECS.
- uv made the Python 3.11 pin painless on a Mac that only had 3.9.
- Laptop→Singapore round-trip is ~9s even for tiny completions; the Singapore
  ECS placement isn't cosmetic, it's the latency budget.
- Embeddings got a 3-tier fallback (DashScope → local bge → hash vectors) so
  tests and offline dev never block on the API.

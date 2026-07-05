# Engram — agent muscle memory (Qwen Cloud Hackathon, Track 1: MemoryAgent)

## What this is
An agent with persistent procedural memory. Cold path: Qwen-VL browser agent
explores a task. Consolidation: trajectory → structured procedure. Warm path:
recall procedure via MCP, replay deterministically, verify cheaply. Curator:
background job that decays, re-verifies, and relearns memories.

## Non-negotiable constraints
- All LLM calls go through src/engram/llm.py (single client wrapper). NEVER
  instantiate OpenAI clients elsewhere.
- Base URL: https://dashscope-intl.aliyuncs.com/compatible-mode/v1
- API key from env DASHSCOPE_API_KEY only. Never hardcode secrets.
- Model routing: vision loop = qwen3.7-plus; verification + reverify probes =
  qwen3.6-flash; consolidation = qwen3.7-max. Never use max where flash works.
- Every LLM call MUST log: model, prompt_tokens, completion_tokens, latency_ms,
  purpose — via src/engram/metrics.py. Benchmarks depend on this.
- Python 3.11, FastAPI, Playwright (chromium), Qdrant (docker), SQLite for
  metadata, MCP over stdio + SSE.
- MEMORY IS OURS: never import or wrap third-party memory frameworks
  (mem0, AgentScope memory classes, Qwen-Agent memory, LangChain memory,
  ReMe). The recall packer, decay math, consolidation, and Curator are the
  judged custom components — implement them from scratch in src/engram/memory
  and src/engram/curator. Qdrant is storage only, not a memory framework.
- Type hints everywhere. Small modules. No file >400 lines.
- Tests: pytest; every module gets at least smoke tests. Run pytest before
  declaring any task done.

## Definition of done for any task
Code runs, tests pass, metrics logged, and there is a one-line demo command
in the Makefile proving it.

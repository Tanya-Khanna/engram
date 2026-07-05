# Engram build journal

5 bullets per phase: what broke, what we learned.

## Phase 0, July 4 (compliance skeleton)
- Repo scaffolded: CLAUDE.md, full src tree, proof file, MIT license,
  Makefile stubs.
- Workspace API keys (`sk-ws-`) work fine on the compatible-mode endpoint;
  the format warning only applies to Token Plan (`sk-sp-`) keys.

## Phase 1, July 4–5 (memory engine + MCP)
- qwen3.6-flash runs in thinking mode by default: 142 reasoning tokens and
  10s latency for a 3-token answer. `enable_thinking: false` via extra_body
  fixed it, now a first-class `think=` param on our llm wrapper. Would have
  silently destroyed the 2–4s warm-path budget in Phase 2.
- No Docker on the dev laptop → qdrant-client's embedded local mode instead;
  same interface, zero infra. Docker Qdrant stays for ECS.
- uv made the Python 3.11 pin painless on a Mac that only had 3.9.
- Laptop→Singapore round-trip is ~9s even for tiny completions; the Singapore
  ECS placement isn't cosmetic, it's the latency budget.
- Embeddings got a 3-tier fallback (DashScope → local bge → hash vectors) so
  tests and offline dev never block on the API.

## Phase 2, July 5 (browser agent, cold + warm)
- First cold run looped: Skyfinder's placeholders (SFO/NRT) matched the task,
  and the model read grey placeholder text as filled values, clicked Search
  3× into HTML5 validation. Cycle detection aborted cleanly (guardrail earned
  its keep on day one). Fix: DOM snapshot now reports value= and placeholder=
  as separate facts; screenshots can't be trusted for input state.
- Consolidation found the URL shortcut unprompted: 5-step exploration →
  goto /results?from={origin}&to={dest}&date={date} + extract. The Almanac
  insight, automated by qwen3.7-max.
- Headline numbers, laptop: Skyfinder 42.7s/11,447 tok cold → 6.2s/1,457 tok
  warm (7×/8×). books.toscrape.com 32.4s/5,809 → 8.8s/1,326. Warm latency is
  ~2 Singapore round-trips; ECS placement will cut it under 4s.
- Procedure ids now hash steps too: a relearn after a site change creates a
  new procedure that supersedes the broken one instead of overwriting its
  failure history. Caught by a test, kept as a design rule.

## Phase 3, July 5 (Curator + benchmarks)
- The whole staleness lifecycle ran live on the first try: decay → stale →
  probe fail → invalid → relearn → diff in the overnight report showing the
  exact param rename (origin→from). The 🌙 report is real, not a mockup.
- Design change while rehearsing: a reverify probe failing against the live
  site now marks the procedure invalid immediately (the plan was right, my
  two-consecutive-failures version needed two sweeps to converge on camera).
- Two self-heal paths coexist and both got exercised: worker fall-through
  (fixes at use-time, 52.7s recover-and-relearn) and Curator relearn
  (fixes overnight, before anyone hits the broken memory).
- `make age-memories DAYS=5` simulates elapsed time honestly, it rewinds
  last_verified rather than faking freshness numbers, so the decay math on
  screen is the real function.

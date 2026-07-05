# Engram

**Muscle memory for AI agents — learned once, remembered everywhere, kept fresh automatically.**

> Qwen Cloud Global AI Hackathon · Track 1: MemoryAgent

The first time Engram does a task on your computer, it works it out slowly with
vision (screenshot → plan → act → verify), then consolidates what it learned
into a structured procedural memory. Every later run — in any session, from any
MCP-connected tool — executes from memory in ~2 seconds. A background Curator
agent keeps those memories fresh: decaying them with age, re-verifying stale
ones, and autonomously relearning anything the world has changed underneath.

🚧 **Under active construction for the hackathon (deadline July 9, 2026).**
Full README — quickstart, architecture, benchmarks — lands in Phase 4.

## Proof of deployment
Backend runs on Alibaba Cloud ECS (Singapore) calling Qwen via DashScope:
[`deploy/alibaba_proof.py`](deploy/alibaba_proof.py)

## License
MIT — see [LICENSE](LICENSE).

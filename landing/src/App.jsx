import { useState } from "react";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/700.css";
import EngramField from "./EngramField.jsx";

const LOGO = `███████ ███    ██  ██████  ██████   █████  ███    ███
██      ████   ██ ██       ██   ██ ██   ██ ████  ████
█████   ██ ██  ██ ██   ███ ██████  ███████ ██ ████ ██
██      ██  ██ ██ ██    ██ ██   ██ ██   ██ ██  ██  ██
███████ ██   ████  ██████  ██   ██ ██   ██ ██      ██`;

const DECAY = `freshness(m) = exp(-AGE_LAMBDA * days_since(last_verified))
             * (1 - FAIL_PENALTY) ** failure_count
             * min(1, 0.8 + 0.05 * success_count)

AGE_LAMBDA = 0.15   procedures   half-life 4.6 days
           = 0.02   preferences  people change slowly
< 0.60 stale   -> reverify queue
< 0.25 invalid -> relearn queue`;

const REPORT = `🌙 Curator run 08:06 UTC · 0 consolidated · 1 verified ·
   2 decayed past a threshold · 1 broken · 1 relearned
 • reverify: proc_66fe30c33228: pass, freshness 0.90
 • reverify: proc_8c3197201994: FAIL (step 1: extract:
   timeout), marked invalid
 • relearned proc_8c3197201994 -> proc_93a8c939833d
   (v2 created, v1 archived):
     - goto /results?origin={origin}&dest={dest}
     + goto /results?from={origin}&to={dest}
   est. savings preserved: 7,758 tokens/run`;

const MCP = `{
  "mcpServers": {
    "engram": {
      "command": "python",
      "args": ["-m", "engram.server.mcp_server"]
    }
  }
}`;

function Copy({ text }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="btn"
      onClick={() => {
        navigator.clipboard.writeText(text);
        setDone(true);
        setTimeout(() => setDone(false), 1400);
      }}
    >
      {done ? "[ copied ]" : `$ ${text}`}
    </button>
  );
}

function SectionHead({ no, title }) {
  return (
    <>
      <hr className="rule double" />
      <div className="section-head">
        <span className="no">{no}</span>
        <h2>{title}</h2>
      </div>
    </>
  );
}

export default function App() {
  return (
    <div className="wrap" style={{ paddingTop: 28, paddingBottom: 40 }}>
      {/* masthead */}
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span className="label">agent memory / qwen cloud hackathon 2026</span>
        <a href="https://github.com/Tanya-Khanna/engram">github</a>
      </div>

      {/* hero */}
      <pre className="ascii-logo" style={{ marginTop: 36 }}>{LOGO}</pre>
      <p style={{ marginTop: 20, fontSize: 17 }}>
        <strong>Muscle memory for AI agents.</strong> Learned once. Remembered
        everywhere. Kept fresh automatically.<span className="cursor" style={{ marginLeft: 8 }} />
      </p>
      <div style={{ display: "flex", gap: 12, marginTop: 22, flexWrap: "wrap" }}>
        <Copy text="git clone https://github.com/Tanya-Khanna/engram" />
        <a className="btn primary" href="https://github.com/Tanya-Khanna/engram" style={{ textDecoration: "none" }}>
          view source →
        </a>
      </div>

      <div style={{ marginTop: 36 }}>
        <EngramField />
        <p className="label" style={{ marginTop: 8 }}>
          fig. 1 : an engram field. pulses are recall. dust is decay. the
          bright path is a relearn.
        </p>
      </div>

      {/* 01 */}
      <div style={{ marginTop: 56 }}>
        <SectionHead no="01" title="the first run explores. every run after remembers." />
        <div className="grid2">
          <div>
            <p className="label">cold : vision loop</p>
            <p className="bignum" style={{ marginTop: 10 }}>42.7 s</p>
            <p style={{ color: "var(--dim)" }}>11,447 tokens · ~10 vision calls</p>
            <pre className="terminal" style={{ marginTop: 16 }}>
{`$ make demo-cold
  screenshot -> plan -> act -> verify
  consolidating trajectory (qwen3.7-max)
  stored proc_f8c0c9150cb7`}
            </pre>
          </div>
          <div>
            <p className="label" style={{ color: "var(--accent)" }}>warm : replay from memory</p>
            <p className="bignum accent" style={{ marginTop: 10 }}>4.3 s</p>
            <p style={{ color: "var(--dim)" }}>1,442 tokens · one flash verify</p>
            <pre className="terminal" style={{ marginTop: 16 }}>
{`$ make demo-warm
  recall -> replay (no vision)
  verified: cheapest is EV793 at $998
  `}<span className="hot">10x faster · 8x cheaper</span>
            </pre>
          </div>
        </div>
        <p className="label" style={{ marginTop: 10 }}>
          measured. same task, same site, benchmark suite in the repo.
        </p>
      </div>

      {/* 02 */}
      <div style={{ marginTop: 56 }}>
        <SectionHead no="02" title="memory that knows it can go stale" />
        <pre className="terminal">{DECAY}</pre>
        <dl className="deflist">
          <dt>AWAKE</dt>
          <dd>runs your tasks. warm when memory is fresh, cold exploration when it is not.</dd>
          <dt>CURIOUS</dt>
          <dd>consolidates trajectories into minimal, parameterized, replayable procedures.</dd>
          <dt>ASLEEP</dt>
          <dd>the curator decays freshness, re-verifies stale skills, relearns broken ones.</dd>
        </dl>
        <figure className="figure" style={{ marginTop: 26 }}>
          <img
            src="/chart3_freshness_lifecycle.png?v=2"
            alt="freshness over twelve days: decay, reverify, break, relearn"
            loading="lazy"
          />
          <figcaption>
            fig. 2 : one procedure, twelve days. decay, reverify, the site
            changes, relearn.
          </figcaption>
        </figure>
      </div>

      {/* 03 */}
      <div style={{ marginTop: 56 }}>
        <SectionHead no="03" title="what it did while you slept" />
        <pre className="terminal">{REPORT}</pre>
        <p className="label" style={{ marginTop: 10 }}>
          verbatim output. the demo site renamed its form fields overnight;
          nobody was awake.
        </p>
      </div>

      {/* 04 */}
      <div style={{ marginTop: 56 }}>
        <SectionHead no="04" title="plug into anything" />
        <p>
          Engram serves memory over MCP. Claude Code, Cursor, or any MCP
          client shares the same learned skills.
        </p>
        <pre className="terminal" style={{ marginTop: 16 }}>{MCP}</pre>
      </div>

      {/* footer */}
      <hr className="rule" style={{ marginTop: 56 }} />
      <p className="label" style={{ padding: "16px 0" }}>
        built on qwen cloud + alibaba cloud ecs · mit licensed ·
        qwen cloud global ai hackathon, track 1: memoryagent
      </p>
    </div>
  );
}

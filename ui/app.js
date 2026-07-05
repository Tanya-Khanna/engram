const thread = document.getElementById("thread");
const box = document.getElementById("box");
const send = document.getElementById("send");
const transcript = [];

function add(cls, text) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.textContent = text;
  thread.appendChild(div);
  thread.scrollTop = thread.scrollHeight;
  return div;
}

function freshBar(id, freshness, superseded) {
  const li = document.createElement("li");
  li.className = "mem" + (superseded ? " superseded" : "");
  li.innerHTML = `
    <div class="label"><span class="id">${id}</span>
    <span class="pct">${Math.round(freshness * 100)}%</span></div>
    <div class="bar"><i style="width:${Math.round(freshness * 100)}%"></i></div>`;
  return li;
}

async function refreshState() {
  const res = await fetch("/api/state");
  const state = await res.json();
  if (state.report) document.getElementById("report").textContent = state.report;
  const list = document.getElementById("store");
  list.innerHTML = "";
  for (const m of state.memories.filter((m) => m.kind !== "episode").slice(0, 12)) {
    list.appendChild(freshBar(`${m.id} v${m.version}`, m.freshness, !!m.superseded_by));
  }
}

async function submit(event) {
  event.preventDefault();
  const message = box.value.trim();
  if (!message) return;
  box.value = "";
  send.disabled = true;
  add("user", message);
  transcript.push("user: " + message);
  const working = add("agent working", "on it, checking memory first...");
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const record = await res.json();
    working.remove();
    add("agent", record.reply || "done");
    transcript.push("agent: " + (record.reply || "done"));
    add("meta", `${record.path} path · ${record.seconds}s · ${record.tokens} tokens`);
    document.getElementById("c-path").textContent = record.path;
    document.getElementById("c-seconds").textContent = record.seconds;
    document.getElementById("c-tokens").textContent = record.tokens.toLocaleString();
    const recalled = document.getElementById("recalled");
    recalled.innerHTML = "";
    if (!record.recalled || !record.recalled.length) {
      recalled.innerHTML = '<li class="dim">nothing recalled: cold path</li>';
    } else {
      for (const m of record.recalled) recalled.appendChild(freshBar(m.id, m.freshness));
    }
    await refreshState();
  } catch (err) {
    working.remove();
    add("agent", "request failed: " + err);
  } finally {
    send.disabled = false;
    box.focus();
  }
}

document.getElementById("composer").addEventListener("submit", submit);
window.addEventListener("beforeunload", () => {
  if (transcript.length < 2) return;
  navigator.sendBeacon(
    "/api/end-session",
    new Blob([JSON.stringify({ transcript: transcript.join("\n") })],
             { type: "application/json" })
  );
});
refreshState();
box.focus();

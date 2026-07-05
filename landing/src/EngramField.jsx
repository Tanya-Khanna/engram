import { useEffect, useMemo, useState } from "react";

// The engram field, drawn the way a terminal would draw it: a character
// grid. Pulses ripple between memory cells, decay dims them to dust,
// relearning lights a path back up.
const W = 66;
const H = 16;
const RAMP = [" ", "·", ":", "+", "*", "#", "@"];
const NODE_COUNT = 120;

function buildField() {
  let seed = 7;
  const rand = () => {
    seed = (seed * 16807) % 2147483647;
    return seed / 2147483647;
  };
  const cells = [];
  const taken = new Set();
  while (cells.length < NODE_COUNT) {
    const x = Math.floor(rand() * W);
    const y = Math.floor(rand() * H);
    const key = y * W + x;
    if (taken.has(key)) continue;
    // bias toward an ellipse so it reads as a mass, not confetti
    const dx = (x - W / 2) / (W / 2);
    const dy = (y - H / 2) / (H / 2);
    if (dx * dx + dy * dy > 0.92 * rand() + 0.35) continue;
    taken.add(key);
    cells.push({ x, y });
  }
  const links = cells.map(() => []);
  for (let i = 0; i < cells.length; i++) {
    for (let j = i + 1; j < cells.length; j++) {
      const dx = cells[i].x - cells[j].x;
      const dy = (cells[i].y - cells[j].y) * 2.2; // rows are taller than cols
      if (links[i].length < 3 && links[j].length < 3 && dx * dx + dy * dy < 64) {
        links[i].push(j);
        links[j].push(i);
      }
    }
  }
  return { cells, links };
}

export default function EngramField() {
  const { cells, links } = useMemo(buildField, []);
  const [frame, setFrame] = useState("");

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setFrame(render(cells, cells.map(() => 0.35)));
      return undefined;
    }
    const level = new Float32Array(cells.length).fill(0.3);
    const dimmed = new Uint8Array(cells.length);
    let tick = 0;
    const id = setInterval(() => {
      tick++;
      if (tick % 28 === 1) {
        const start = Math.floor(Math.random() * cells.length);
        level[start] = 1;
        for (const n of links[start]) level[n] = Math.max(level[n], 0.75);
      }
      if (tick % 160 === 80) {
        for (let i = 0; i < cells.length; i++) {
          if (Math.random() < 0.35) dimmed[i] = 1;
        }
      }
      if (tick % 160 === 110) {
        let node = Math.floor(Math.random() * cells.length);
        for (let hop = 0; hop < 7; hop++) {
          dimmed[node] = 0;
          level[node] = 1;
          if (!links[node].length) break;
          node = links[node][Math.floor(Math.random() * links[node].length)];
        }
      }
      for (let i = 0; i < cells.length; i++) {
        const floor = dimmed[i] ? 0.08 : 0.3;
        level[i] = Math.max(floor, level[i] - 0.045);
        if (dimmed[i] && Math.random() < 0.004) dimmed[i] = 0;
      }
      setFrame(render(cells, level));
    }, 90);
    return () => clearInterval(id);
  }, [cells, links]);

  return (
    <pre className="terminal" aria-hidden style={{ lineHeight: 1.25 }}>
      {frame}
    </pre>
  );
}

function render(cells, level) {
  const grid = Array.from({ length: H }, () => Array(W).fill(" "));
  cells.forEach((cell, i) => {
    const idx = Math.min(
      RAMP.length - 1,
      Math.floor(level[i] * (RAMP.length - 0.01))
    );
    grid[cell.y][cell.x] = RAMP[idx];
  });
  return grid.map((row) => row.join("")).join("\n");
}

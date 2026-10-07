// How many pages per second can the thin SSR server render (one process, one
// core), with the loader calling a local stand-in for the Go API? 12-architecture
// 3.5 assumes "peak ten pages a second, Vue 5-15 ms each".
const base = process.argv[2] ?? "http://localhost:5173";
const path = process.argv[3] ?? "/";
const total = Number(process.argv[4] ?? 1000), conc = Number(process.argv[5] ?? 10);
const times = [];
let next = 0;
const start = performance.now();
await Promise.all(Array.from({ length: conc }, async () => {
  while (next < total) {
    next++;
    const t = performance.now();
    const r = await fetch(base + path);
    await r.arrayBuffer();
    times.push(performance.now() - t);
  }
}));
const elapsed = (performance.now() - start) / 1000;
times.sort((a, b) => a - b);
const q = (p) => times[Math.floor(times.length * p)].toFixed(1);
console.log(`${path}: ${total} requests, concurrency ${conc}: ${(total / elapsed).toFixed(0)} req/s, p50 ${q(0.5)} ms, p95 ${q(0.95)} ms, p99 ${q(0.99)} ms`);

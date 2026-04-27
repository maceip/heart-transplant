const BLOCKS = [
  "Identity UI",
  "State Management",
  "Core Rendering",
  "Interaction Design",
  "Asset Delivery",
  "Global Interface",
  "Edge Support",
  "Experimentation",
  "User Observability",
  "Error Boundaries",
  "Persistence Strategy",
  "Visual Systems",
  "Access Control",
  "System Telemetry",
  "Data Persistence",
  "Background Processing",
  "Traffic Control",
  "Network Edge",
  "Search Architecture",
  "Security Ops",
  "Connectivity Layer",
  "Resiliency",
  "Data Sovereignty",
  "Analytical Intelligence",
];

const SIGNALS = [
  ["Access Control", /\b(auth|session|password|jwt|bearer|rbac|permission|role|guard|login|signup)\b/i, 2.0, "auth/session token"],
  ["Data Persistence", /\b(prisma|database|postgres|sqlite|mysql|mongodb|schema|migration|model|supabase|drizzle|redis|query)\b/i, 2.0, "database/schema token"],
  ["Network Edge", /\b(elysia|express|hono|fastify|router|route|middleware|request|response|fetch|axios|webhook|endpoint)\b/i, 1.7, "network edge token"],
  ["System Telemetry", /\b(telemetry|logger?|log\.|tracer|metric|sentry|otel|opentelemetry)\b/i, 1.8, "observability token"],
  ["Security Ops", /\b(secret|api[_-]?key|encrypt|decrypt|hash|salt|csrf|cors|helmet)\b/i, 1.5, "security token"],
  ["Traffic Control", /\b(rate[_-]?limit|throttle|quota|load balanc|proxy)\b/i, 1.4, "traffic control token"],
  ["Background Processing", /\b(queue|worker|job|task|schedule|cron|bullmq)\b/i, 1.7, "async processing token"],
  ["Search Architecture", /\b(search|index|meilisearch|typesense|elastic|opensearch)\b/i, 1.7, "search/index token"],
  ["Analytical Intelligence", /\b(warehouse|etl|analytics|segment|amplitude|mixpanel|report)\b/i, 1.5, "analytics token"],
  ["Data Sovereignty", /\b(gdpr|privacy|retention|archive|pii|cookie|consent)\b/i, 1.4, "privacy token"],
  ["Resiliency", /\b(retry|fallback|circuit|backup|restore|catch|try\s*\{)\b/i, 1.2, "resilience token"],
  ["State Management", /\b(zustand|redux|context|useReducer|store|atom|signal)\b/i, 1.5, "state token"],
  ["Core Rendering", /(jsx|tsx|render|component|className|<\/)/i, 1.3, "render token"],
  ["Interaction Design", /\b(onClick|onSubmit|form|button|input|navigate|router\.push)\b/i, 1.3, "interaction token"],
  ["Asset Delivery", /\b(vite|webpack|rollup|bundle|asset|image|font|css|tailwind)\b/i, 1.2, "asset/build token"],
  ["Error Boundaries", /\b(error boundary|fallback ui|componentDidCatch|useErrorBoundary)\b/i, 1.7, "frontend fault boundary"],
];

const PATH_SIGNALS = [
  ["Data Persistence", /(^|\/)prisma(\/|\.config)|(^|\/)schema\.prisma$|(^|\/)lib\/prisma\./i, 2.3, "persistence path"],
  ["Persistence Strategy", /(^|\/)(libs?\/)?cache(\/|\.)|(^|\/)cache\./i, 4.2, "cache path"],
  ["Background Processing", /(^|\/)(bull|queues?|workers?)(\/|\.)|(^|\/).*(queue|worker)[^/]*\./i, 3.2, "queue/worker path"],
  ["Global Interface", /(^|\/)(env|environment)\.config\.|(^|\/)config\/(env|environment)\./i, 2.6, "environment interface path"],
  ["System Telemetry", /(^|\/)(logger|telemetry|tracing)\./i, 2.0, "telemetry path"],
  ["Access Control", /(^|\/)(auth|passwords?|sessions?|permissions?)[^/]*\./i, 1.7, "access-control path"],
  ["Security Ops", /(^|\/)utils\/security\./i, 2.2, "security utility path"],
  ["Network Edge", /(^|\/)routes?\//i, 1.8, "route path"],
  ["Core Rendering", /(^|\/)emails?\/.*\.(tsx|jsx)$/i, 2.4, "rendered email path"],
  ["Connectivity Layer", /(^|\/)(services?|adapters|providers)\//i, 1.0, "service layer path"],
  ["Search Architecture", /(^|\/)(index|config\/index|database\/index|middlewares\/index|modules\/index|modules\/[^/]+\/index)\.(ts|tsx|js|jsx)$/i, 2.4, "architectural index path"],
];

const COLORS = ["#de3d54", "#22b8c7", "#82d173", "#f5c45d", "#a68cff", "#ff8a65", "#7bdff2", "#b2f7ef"];
const SOURCE_EXTENSIONS = /\.(ts|tsx|js|jsx|mjs|cjs|py|go|prisma|java|rs|cpp|cc|cxx|h|hpp)$/i;
const SKIP_PATHS = /(^|\/)(node_modules|\.git|dist|build|target|vendor|coverage|\.next|\.venv|\.venv-win)\//i;

const state = {
  currentRepo: "immich-app/immich",
  surfaces: [],
  benchmark: null,
};

const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
  $("repo-form").addEventListener("submit", onRepoSubmit);
  loadBenchmark();
  ingestRepo(state.currentRepo);
});

async function onRepoSubmit(event) {
  event.preventDefault();
  const repo = normalizeRepo($("repo-input").value);
  if (!repo) {
    setStatus("Enter a GitHub URL or owner/name.", true);
    return;
  }
  await ingestRepo(repo);
}

async function ingestRepo(repo) {
  state.currentRepo = repo;
  setStatus(`Preparing operating field for ${repo}...`);
  updateBackendCommand(repo);
  const button = document.querySelector("button[type='submit']");
  button.disabled = true;
  try {
    const meta = await fetchJson(`https://api.github.com/repos/${repo}`);
    const branch = meta.default_branch || "main";
    const tree = await fetchJson(`https://api.github.com/repos/${repo}/git/trees/${encodeURIComponent(branch)}?recursive=1`);
    const files = tree.tree
      .filter((item) => item.type === "blob" && SOURCE_EXTENSIONS.test(item.path) && !SKIP_PATHS.test(item.path))
      .slice(0, 280);
    setStatus(`Classifying ${files.length} file surfaces from ${repo}; sampling content from the first 55.`);
    const contentMap = await fetchSampledContent(repo, branch, files.slice(0, 55));
    state.surfaces = files.map((file) => classifySurface(file.path, contentMap.get(file.path) || ""));
    renderRepoResults();
    setStatus(`Intake complete for ${repo}: ${state.surfaces.length} file surfaces classified.`);
  } catch (error) {
    setStatus(`Intake stopped: ${error.message}`, true);
  } finally {
    button.disabled = false;
  }
}

function normalizeRepo(value) {
  const trimmed = value.trim();
  if (!trimmed) return "";
  const match = trimmed.match(/github\.com[:/](?<owner>[^/\s]+)\/(?<repo>[^/\s.]+)(?:\.git)?/i);
  if (match?.groups) return `${match.groups.owner}/${match.groups.repo}`;
  const pair = trimmed.match(/^(?<owner>[\w.-]+)\/(?<repo>[\w.-]+)$/);
  return pair?.groups ? `${pair.groups.owner}/${pair.groups.repo}` : "";
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/vnd.github+json" } });
  if (!response.ok) throw new Error(`${response.status} from ${url.replace("https://api.github.com/", "GitHub API ")}`);
  return response.json();
}

async function fetchSampledContent(repo, branch, files) {
  const out = new Map();
  const batches = [];
  for (let i = 0; i < files.length; i += 10) batches.push(files.slice(i, i + 10));
  for (const batch of batches) {
    await Promise.all(
      batch.map(async (file) => {
        try {
          const url = `https://raw.githubusercontent.com/${repo}/${encodeURIComponent(branch)}/${file.path.split("/").map(encodeURIComponent).join("/")}`;
          const response = await fetch(url);
          if (response.ok) out.set(file.path, (await response.text()).slice(0, 4000));
        } catch {
          out.set(file.path, "");
        }
      }),
    );
  }
  return out;
}

function classifySurface(path, content) {
  const scores = new Map();
  const evidence = new Map();
  const hay = `${path} ${content.slice(0, 2000)}`;
  addScore(scores, evidence, "Search Architecture", 0.8, "file-level architecture surface");
  for (const [block, pattern, weight, label] of PATH_SIGNALS) {
    if (pattern.test(path)) addScore(scores, evidence, block, weight, label);
  }
  for (const [block, pattern, weight, label] of SIGNALS) {
    if (pattern.test(hay)) addScore(scores, evidence, block, weight, label);
  }
  const exportCount = (content.match(/\bexport\b/g) || []).length;
  const importCount = (content.match(/\bimport\b/g) || []).length;
  if (/\/?index\.(ts|tsx|js|jsx)$/i.test(path)) {
    addScore(scores, evidence, "Search Architecture", 2.0 + Math.min(exportCount, 4) * 0.25, "index/barrel surface");
  }
  if (/(^|\/)(config|env|settings|drizzle|prisma)(\/|\.)/i.test(path)) {
    addScore(scores, evidence, "Global Interface", 1.6, "configuration boundary");
  }
  if (importCount >= 2 && exportCount >= 1) {
    addScore(scores, evidence, "Connectivity Layer", 0.8, "bridges imports and exports");
  }
  const ranked = [...scores.entries()].sort((a, b) => b[1] - a[1]);
  const [primary, score] = ranked[0] || ["Identity UI", 0.1];
  const runnerUp = ranked[1]?.[1] || 0;
  const confidence = Math.min(0.42 + 0.08 * score + 0.06 * Math.max(score - runnerUp, 0), 0.95);
  return {
    path,
    block: primary,
    confidence,
    signal: (evidence.get(primary) || ["low signal fallback"]).slice(0, 3).join(", "),
  };
}

function addScore(scores, evidence, block, weight, label) {
  scores.set(block, (scores.get(block) || 0) + weight);
  evidence.set(block, [...(evidence.get(block) || []), label]);
}

function renderRepoResults() {
  const counts = countBy(state.surfaces, (surface) => surface.block);
  const rows = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);
  drawBarChart($("repo-block-chart"), rows, { title: "Primary block count", suffix: " files" });
  $("block-list").innerHTML = rows
    .map(([block, count], index) => `<div class="block-pill" style="border-color:${COLORS[index % COLORS.length]}"><strong>${escapeHtml(block)}</strong><span>${count} file surfaces on the table</span></div>`)
    .join("");
  $("surface-table").innerHTML = state.surfaces
    .slice()
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 80)
    .map(
      (surface) => `<tr><td>${escapeHtml(surface.path)}</td><td>${escapeHtml(surface.block)}</td><td>${Math.round(surface.confidence * 100)}%</td><td>${escapeHtml(surface.signal)}</td></tr>`,
    )
    .join("");
}

async function loadBenchmark() {
  try {
    state.benchmark = await fetchJson("./evals/trending-top50-ec2-summary-2026-04-27.json");
    renderBenchmark();
  } catch (error) {
    $("bench-findings").innerHTML = `<div class="finding"><strong>Benchmark unavailable</strong><span>${escapeHtml(error.message)}</span></div>`;
  }
}

function renderBenchmark() {
  const benchmark = state.benchmark;
  const languageRows = Object.entries(benchmark.by_language || {});
  const totalNodes = languageRows.reduce((sum, [, value]) => sum + Number(value.node_count || 0), 0);
  const totalEdges = languageRows.reduce((sum, [, value]) => sum + Number(value.edge_count || 0), 0);
  $("vital-total").textContent = formatNumber(benchmark.total || 50);
  $("vital-ok").textContent = formatNumber(benchmark.by_status?.ok || 0);
  $("vital-nodes").textContent = compactNumber(totalNodes);
  $("vital-edges").textContent = compactNumber(totalEdges);

  drawStackedChart(
    $("language-chart"),
    languageRows.map(([language, value]) => [language, Number(value.ok || 0), Number(value.total || 0) - Number(value.ok || 0)]),
  );
  drawBarChart(
    $("node-chart"),
    languageRows.map(([language, value]) => [language, Number(value.node_count || 0)]),
    { title: "Code nodes by manifest language", suffix: " nodes" },
  );
  const largest = [...(benchmark.results || [])]
    .filter((item) => item.status === "ok")
    .sort((a, b) => Number(b.node_count || 0) - Number(a.node_count || 0))
    .slice(0, 10)
    .map((item) => [item.full_name, Number(item.node_count || 0)]);
  drawBarChart($("largest-chart"), largest, { title: "Largest successful artifacts", suffix: " nodes" });

  const failed = benchmark.by_status?.ingest_failed || 0;
  const zeroNode = languageRows.reduce((sum, [, value]) => sum + Number(value.zero_node || 0), 0);
  $("bench-findings").innerHTML = [
    ["Attempted", `${benchmark.total} repos across TypeScript, Rust, Go, C++, and Java trending.`],
    ["Successful", `${benchmark.by_status?.ok || 0} completed ingest and phase metrics.`],
    ["Complications", `${failed} first-run ingest failures preserved, bugs and all.`],
    ["Coverage smell", `${zeroNode} zero-node successes kept visible as quality gate pressure.`],
  ]
    .map(([title, body]) => `<div class="finding"><strong>${title}</strong><span>${body}</span></div>`)
    .join("");
}

function drawBarChart(canvas, rows, options = {}) {
  const ctx = canvas.getContext("2d");
  const { width, height } = canvas;
  ctx.clearRect(0, 0, width, height);
  const max = Math.max(1, ...rows.map(([, value]) => value));
  const left = 170;
  const top = 26;
  const rowHeight = Math.max(20, (height - top - 24) / Math.max(rows.length, 1));
  ctx.font = "20px Segoe UI, sans-serif";
  ctx.fillStyle = "#f7fbff";
  ctx.fillText(options.title || "", 12, 20);
  rows.forEach(([label, value], index) => {
    const y = top + index * rowHeight + 8;
    const barWidth = Math.max(2, ((width - left - 88) * value) / max);
    ctx.fillStyle = "#a9b8c7";
    ctx.font = "14px Segoe UI, sans-serif";
    ctx.fillText(truncate(label, 22), 12, y + 13);
    ctx.fillStyle = COLORS[index % COLORS.length];
    ctx.fillRect(left, y, barWidth, Math.max(10, rowHeight - 12));
    ctx.fillStyle = "#f7fbff";
    ctx.fillText(compactNumber(value), left + barWidth + 8, y + 13);
  });
}

function drawStackedChart(canvas, rows) {
  const ctx = canvas.getContext("2d");
  const { width, height } = canvas;
  ctx.clearRect(0, 0, width, height);
  const left = 120;
  const top = 34;
  const rowHeight = (height - 60) / rows.length;
  ctx.fillStyle = "#f7fbff";
  ctx.font = "20px Segoe UI, sans-serif";
  ctx.fillText("OK vs failed", 12, 22);
  rows.forEach(([language, ok, failed], index) => {
    const total = Math.max(ok + failed, 1);
    const y = top + index * rowHeight;
    const fullWidth = width - left - 48;
    ctx.fillStyle = "#a9b8c7";
    ctx.font = "14px Segoe UI, sans-serif";
    ctx.fillText(language, 12, y + 18);
    ctx.fillStyle = COLORS[index % COLORS.length];
    ctx.fillRect(left, y, (fullWidth * ok) / total, 22);
    ctx.fillStyle = "#de3d54";
    ctx.fillRect(left + (fullWidth * ok) / total, y, (fullWidth * failed) / total, 22);
    ctx.fillStyle = "#f7fbff";
    ctx.fillText(`${ok}/${total}`, width - 42, y + 17);
  });
}

function countBy(items, keyFn) {
  const out = new Map();
  for (const item of items) {
    const key = keyFn(item);
    out.set(key, (out.get(key) || 0) + 1);
  }
  return out;
}

function updateBackendCommand(repo) {
  const folder = repo.split("/").pop();
  $("backend-command").textContent = `git clone https://github.com/${repo}.git vendor/github-repos/${folder}
cd backend
.\\.venv-win\\Scripts\\python.exe -m heart_transplant.cli ingest-local ..\\vendor\\github-repos\\${folder} --repo-name ${repo}
.\\.venv-win\\Scripts\\python.exe -m heart_transplant.cli classify .heart-transplant\\artifacts\\<artifact-dir> --no-use-openai`;
}

function setStatus(message, isError = false) {
  const status = $("repo-status");
  status.textContent = message;
  status.style.color = isError ? "#ff8a65" : "#a9b8c7";
}

function compactNumber(value) {
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function formatNumber(value) {
  return Intl.NumberFormat("en").format(value);
}

function truncate(value, length) {
  return value.length > length ? `${value.slice(0, length - 1)}...` : value;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[char]);
}

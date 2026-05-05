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

const SOURCE_EXTENSIONS = /\.(ts|tsx|js|jsx|mjs|cjs|py|go|prisma|java|rs|cpp|cc|cxx|h|hpp)$/i;
const SKIP_PATHS = /(^|\/)(node_modules|\.git|dist|build|target|vendor|coverage|\.next|\.venv|\.venv-win|\.pytest_cache|\.pytest_tmp|\.heart-transplant)\//i;

const FEATURED_REPOS = [
  "immich-app/immich",
  "denoland/deno",
  "go-gitea/gitea",
  "zed-industries/zed",
  "openai/codex",
  "vercel/next.js",
  "withastro/astro",
  "elysiajs/elysia",
];

// Mirrors backend/src/heart_transplant/demo.py DEMO_QUESTIONS
const EVIDENCE_QUESTIONS = [
  { question: "Which files own authentication or access control?", block: "Access Control" },
  { question: "Where is database persistence handled?", block: "Data Persistence" },
  { question: "Where are routes or HTTP entry points handled?", block: "Network Edge" },
  { question: "Where are queue, worker, or background jobs handled?", block: "Background Processing" },
  { question: "Where is logging or telemetry handled?", block: "System Telemetry" },
  { question: "Where is environment or global configuration handled?", block: "Global Interface" },
  { question: "Which files render UI components?", block: "Core Rendering" },
];

// Mirrors backend/src/heart_transplant/regret/patterns.py
const REGRET_PATTERNS = [
  {
    id: "scattered_auth",
    title: "Scattered auth",
    description: "Auth logic spread across many files instead of one access-control layer.",
    block: "Access Control",
    keywords: ["auth", "session", "jwt", "bearer", "login"],
    fileSpreadFloor: 4,
  },
  {
    id: "database_sprawl",
    title: "Database sprawl",
    description: "Database calls scattered outside a small persistence layer.",
    block: "Data Persistence",
    keywords: ["prisma", "drizzle", "sql", "query", "database", "supabase"],
    fileSpreadFloor: 4,
  },
  {
    id: "fat_routes",
    title: "Fat routes",
    description: "A single route module concentrates many handlers — likely doing too much.",
    block: "Network Edge",
    keywords: ["routes", "router", "controller"],
    fileSpreadFloor: 1,
    concentration: true,
  },
  {
    id: "logging_inconsistency",
    title: "Inconsistent logging",
    description: "Multiple logging or telemetry styles in the same repo.",
    block: "System Telemetry",
    keywords: ["logger", "console.log", "pino", "winston", "telemetry"],
    fileSpreadFloor: 3,
  },
];

const state = {
  currentRepo: "",
  surfaces: [],
  files: [],
  contentMap: new Map(),
  isAnalyzing: false,
};

const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
  $("repo-form").addEventListener("submit", onRepoSubmit);
  renderRepoChips();
});

function renderRepoChips() {
  const host = $("repo-chips");
  host.innerHTML = FEATURED_REPOS
    .map(
      (repo) =>
        `<button type="button" class="repo-chip" data-repo="${escapeHtml(repo)}" role="listitem">${escapeHtml(repo)}</button>`,
    )
    .join("");
  host.addEventListener("click", (event) => {
    const target = event.target.closest("[data-repo]");
    if (!target) return;
    $("repo-input").value = target.dataset.repo;
    onRepoSubmit(new Event("submit"));
  });
}

async function onRepoSubmit(event) {
  if (event.preventDefault) event.preventDefault();
  const repo = normalizeRepo($("repo-input").value);
  if (!repo) {
    setStatus("Enter a GitHub URL or owner/name.", true);
    return;
  }
  if (state.isAnalyzing) {
    setStatus("Analysis is already running. Please wait.");
    return;
  }
  state.isAnalyzing = true;
  state.currentRepo = repo;
  const button = document.querySelector("button[type='submit']");
  button.classList.add("is-loading");
  button.disabled = true;
  button.textContent = "Analyzing";
  setStatus(`Fetching repository tree for ${repo}…`);

  try {
    await analyzeRepo(repo);
  } catch (error) {
    setStatus(`Analysis stopped: ${error.message}`, true);
    hideResultBands();
  } finally {
    state.isAnalyzing = false;
    button.classList.remove("is-loading");
    button.disabled = false;
    button.textContent = "Analyze";
  }
}

async function analyzeRepo(repo) {
  const meta = await fetchJson(`https://api.github.com/repos/${repo}`);
  const branch = meta.default_branch || "main";
  const tree = await fetchJson(`https://api.github.com/repos/${repo}/git/trees/${encodeURIComponent(branch)}?recursive=1`);
  const files = tree.tree
    .filter((item) => item.type === "blob" && SOURCE_EXTENSIONS.test(item.path) && !SKIP_PATHS.test(item.path))
    .slice(0, 280);
  if (files.length === 0) throw new Error("No source files found in this repo.");
  setStatus(`Classifying ${files.length} files from ${repo}; sampling content from the first 55…`);
  const contentMap = await fetchSampledContent(repo, branch, files.slice(0, 55));
  const surfaces = files.map((file) => classifySurface(file.path, contentMap.get(file.path) || ""));

  state.files = files;
  state.contentMap = contentMap;
  state.surfaces = surfaces;

  renderSummary(repo, meta, surfaces);
  renderEvidence(surfaces, contentMap);
  renderRegret(surfaces, contentMap);
  renderBlocks(surfaces);
  showResultBands();
  setStatus(
    `Analyzed ${files.length} files from ${repo} (sampled ${contentMap.size} for content). ${surfaces.length} surfaces classified.`,
  );
}

function normalizeRepo(value) {
  const trimmed = (value || "").trim();
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
          const url = `https://raw.githubusercontent.com/${repo}/${encodeURIComponent(branch)}/${file.path
            .split("/")
            .map(encodeURIComponent)
            .join("/")}`;
          const response = await fetch(url);
          if (response.ok) out.set(file.path, (await response.text()).slice(0, 4000));
        } catch {
          /* ignore */
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
  addScore(scores, evidence, "Search Architecture", 0.6, "file-level architecture surface");
  for (const [block, pattern, weight, label] of PATH_SIGNALS) {
    if (pattern.test(path)) addScore(scores, evidence, block, weight, label);
  }
  for (const [block, pattern, weight, label] of SIGNALS) {
    if (pattern.test(hay)) addScore(scores, evidence, block, weight, label);
  }
  const exportCount = (content.match(/\bexport\b/g) || []).length;
  const importCount = (content.match(/\bimport\b/g) || []).length;
  if (/\/?index\.(ts|tsx|js|jsx)$/i.test(path)) {
    addScore(scores, evidence, "Search Architecture", 1.6 + Math.min(exportCount, 4) * 0.25, "index/barrel surface");
  }
  if (/(^|\/)(config|env|settings|drizzle|prisma)(\/|\.)/i.test(path)) {
    addScore(scores, evidence, "Global Interface", 1.6, "configuration boundary");
  }
  if (importCount >= 2 && exportCount >= 1) {
    addScore(scores, evidence, "Connectivity Layer", 0.8, "bridges imports and exports");
  }
  const ranked = [...scores.entries()].sort((a, b) => b[1] - a[1]);
  const [primary, score] = ranked[0] || ["Connectivity Layer", 0.1];
  const runnerUp = ranked[1]?.[1] || 0;
  const confidence = Math.min(0.42 + 0.08 * score + 0.06 * Math.max(score - runnerUp, 0), 0.95);
  return {
    path,
    block: primary,
    confidence,
    signal: (evidence.get(primary) || ["low signal fallback"]).slice(0, 3).join(", "),
    sampled: Boolean(content),
  };
}

function addScore(scores, evidence, block, weight, label) {
  scores.set(block, (scores.get(block) || 0) + weight);
  evidence.set(block, [...(evidence.get(block) || []), label]);
}

function renderSummary(repo, meta, surfaces) {
  const counts = countBy(surfaces, (s) => s.block);
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4);
  const languages = [...countBy(surfaces, (s) => extensionLanguage(s.path)).entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);
  const stars = formatNumber(meta.stargazers_count || 0);
  $("summary-grid").innerHTML = [
    summaryCard("Repository", `${escapeHtml(repo)}`, `${stars} ★ · default branch ${escapeHtml(meta.default_branch || "main")}`),
    summaryCard("Files classified", `${formatNumber(surfaces.length)}`, "source files (max 280 sampled per repo)"),
    summaryCard("Top blocks", top.map(([b]) => escapeHtml(b)).join(", ") || "—", top.map(([, c]) => `${c}`).join(" · ")),
    summaryCard("Languages", languages.map(([l]) => escapeHtml(l)).join(", ") || "—", languages.map(([, c]) => `${c}`).join(" · ")),
  ].join("");
}

function summaryCard(label, value, footnote) {
  return `
    <article class="summary-card">
      <small>${escapeHtml(label)}</small>
      <strong>${value}</strong>
      <span>${escapeHtml(footnote)}</span>
    </article>`;
}

function renderEvidence(surfaces, contentMap) {
  const grid = $("evidence-grid");
  grid.innerHTML = EVIDENCE_QUESTIONS.map((q) => evidenceCard(q, surfaces, contentMap)).join("");
}

function evidenceCard(question, surfaces, contentMap) {
  const matches = surfaces.filter((s) => s.block === question.block);
  if (matches.length === 0) {
    return `
      <article class="evidence-card empty">
        <p class="evidence-block">${escapeHtml(question.block)}</p>
        <h3>${escapeHtml(question.question)}</h3>
        <p class="claim">No graph evidence matched.</p>
        <p class="confidence">confidence 0.25</p>
      </article>`;
  }
  matches.sort((a, b) => b.confidence - a.confidence);
  const topFiles = matches.slice(0, 5);
  const dirs = new Set(matches.map((s) => directoryOf(s.path)));
  const confidence = Math.min(0.95, 0.55 + 0.05 * Math.min(matches.length, 6) + 0.05 * Math.min(dirs.size, 4));
  return `
    <article class="evidence-card">
      <p class="evidence-block">${escapeHtml(question.block)}</p>
      <h3>${escapeHtml(question.question)}</h3>
      <p class="claim">Matched ${formatNumber(matches.length)} file surfaces across ${dirs.size} director${dirs.size === 1 ? "y" : "ies"}.</p>
      <ul>
        ${topFiles
          .map(
            (s) => `<li>
              <span class="file">${escapeHtml(s.path)}</span>
              <small>${Math.round(s.confidence * 100)}% · ${escapeHtml(s.signal)}</small>
            </li>`,
          )
          .join("")}
      </ul>
      <p class="confidence">confidence ${confidence.toFixed(2)}</p>
    </article>`;
}

function renderRegret(surfaces, contentMap) {
  const grid = $("regret-grid");
  const findings = REGRET_PATTERNS.map((pattern) => regretFinding(pattern, surfaces, contentMap)).filter(Boolean);
  if (findings.length === 0) {
    grid.innerHTML = `<p class="regret-empty">No regret patterns triggered above threshold.</p>`;
    return;
  }
  grid.innerHTML = findings.map(regretCard).join("");
}

function regretFinding(pattern, surfaces, contentMap) {
  const blockSurfaces = surfaces.filter((s) => s.block === pattern.block);
  const keywordHits = [];
  const dirs = new Set();
  for (const surface of blockSurfaces) {
    const content = (contentMap.get(surface.path) || "").toLowerCase();
    const haystack = `${surface.path.toLowerCase()} ${content}`;
    const matched = pattern.keywords.filter((k) => haystack.includes(k));
    if (matched.length === 0 && surface.sampled) continue;
    keywordHits.push({ path: surface.path, hits: matched.length || 1, matched });
    dirs.add(directoryOf(surface.path));
  }
  if (keywordHits.length < pattern.fileSpreadFloor) return null;
  if (pattern.concentration) {
    // Fat routes: a single file should have many handlers/keywords (use largest hits)
    keywordHits.sort((a, b) => b.hits - a.hits);
    if (keywordHits[0].hits < 2 && blockSurfaces.length < 6) return null;
  }
  const fileSpread = keywordHits.length;
  const dirSpread = dirs.size;
  const baseScore = pattern.concentration
    ? Math.min(0.95, 0.45 + 0.07 * keywordHits[0].hits + 0.04 * Math.max(0, fileSpread - 4))
    : Math.min(0.95, 0.4 + 0.05 * fileSpread + 0.06 * dirSpread);
  return {
    pattern,
    confidence: baseScore,
    fileSpread,
    dirSpread,
    samples: keywordHits.slice(0, 6),
  };
}

function regretCard(finding) {
  const { pattern, confidence, fileSpread, dirSpread, samples } = finding;
  const samplesHtml = samples
    .map(
      (s) =>
        `<li><span class="file">${escapeHtml(s.path)}</span>${
          s.matched.length ? `<small>${escapeHtml(s.matched.join(", "))}</small>` : ""
        }</li>`,
    )
    .join("");
  return `
    <article class="regret-card">
      <p class="regret-id">${escapeHtml(pattern.id)}</p>
      <h3>${escapeHtml(pattern.title)}</h3>
      <p class="claim">${escapeHtml(pattern.description)}</p>
      <p class="spread">${formatNumber(fileSpread)} file${fileSpread === 1 ? "" : "s"} · ${dirSpread} director${dirSpread === 1 ? "y" : "ies"} · block <strong>${escapeHtml(pattern.block)}</strong></p>
      <ul>${samplesHtml}</ul>
      <p class="confidence">confidence ${confidence.toFixed(2)}</p>
    </article>`;
}

function renderBlocks(surfaces) {
  const counts = countBy(surfaces, (s) => s.block);
  const rows = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);
  drawBarChart($("block-chart"), rows, { title: "Files per detected block", suffix: " files" });
  $("surface-table").innerHTML = surfaces
    .slice()
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 80)
    .map(
      (s) => `<tr>
        <td>${escapeHtml(s.path)}</td>
        <td>${escapeHtml(s.block)}</td>
        <td>${Math.round(s.confidence * 100)}%</td>
        <td>${escapeHtml(s.signal)}</td>
      </tr>`,
    )
    .join("");
}

function showResultBands() {
  for (const cls of ["summary-band", "evidence-band", "regret-band", "blocks-band"]) {
    const node = document.querySelector(`section.${cls}`);
    if (node) node.hidden = false;
  }
}

function hideResultBands() {
  for (const cls of ["summary-band", "evidence-band", "regret-band", "blocks-band"]) {
    const node = document.querySelector(`section.${cls}`);
    if (node) node.hidden = true;
  }
}

function setStatus(message, isError = false) {
  const status = $("repo-status");
  status.textContent = message;
  status.classList.toggle("is-error", Boolean(isError));
}

function countBy(items, projection) {
  const map = new Map();
  for (const item of items) {
    const key = projection(item);
    map.set(key, (map.get(key) || 0) + 1);
  }
  return map;
}

function directoryOf(path) {
  const parts = path.split("/");
  if (parts.length <= 1) return ".";
  return parts.slice(0, Math.min(parts.length - 1, 3)).join("/");
}

function extensionLanguage(path) {
  const ext = (path.match(/\.([^./]+)$/) || ["", ""])[1].toLowerCase();
  const map = {
    ts: "TypeScript",
    tsx: "TypeScript",
    js: "JavaScript",
    jsx: "JavaScript",
    mjs: "JavaScript",
    cjs: "JavaScript",
    py: "Python",
    go: "Go",
    rs: "Rust",
    java: "Java",
    cpp: "C++",
    cc: "C++",
    cxx: "C++",
    h: "C/C++",
    hpp: "C++",
    prisma: "Prisma",
  };
  return map[ext] || ext.toUpperCase() || "other";
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("en-US");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function drawBarChart(canvas, rows, options) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || canvas.width;
  const height = canvas.height;
  if (canvas.width !== width * dpr) {
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.height = `${height}px`;
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#0b0d12";
  ctx.fillRect(0, 0, width, height);
  if (rows.length === 0) {
    ctx.fillStyle = "rgba(255,255,255,0.45)";
    ctx.font = "14px system-ui, sans-serif";
    ctx.fillText(options?.title || "No data yet", 16, 28);
    return;
  }
  const max = Math.max(...rows.map(([, count]) => count));
  const padding = { top: 36, right: 20, bottom: 24, left: 200 };
  const innerH = height - padding.top - padding.bottom;
  const barH = innerH / rows.length - 6;
  ctx.fillStyle = "rgba(255,255,255,0.7)";
  ctx.font = "13px system-ui, sans-serif";
  ctx.fillText(options?.title || "", 16, 22);
  rows.forEach(([label, count], i) => {
    const y = padding.top + i * (barH + 6);
    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.font = "12px system-ui, sans-serif";
    ctx.textBaseline = "middle";
    ctx.fillText(label, 16, y + barH / 2);
    const barWidth = ((width - padding.left - padding.right) * count) / Math.max(max, 1);
    const grad = ctx.createLinearGradient(padding.left, 0, padding.left + barWidth, 0);
    grad.addColorStop(0, "#3aa0ff");
    grad.addColorStop(1, "#7ad0ff");
    ctx.fillStyle = grad;
    ctx.fillRect(padding.left, y, Math.max(barWidth, 1), barH);
    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.fillText(`${count}${options?.suffix || ""}`, padding.left + barWidth + 8, y + barH / 2);
  });
}

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
const SKIP_PATHS = /(^|\/)(node_modules|\.git|dist|build|target|vendor|coverage|\.next|\.venv|\.venv-win)\//i;
const REVIEW_LABELS = ["unreviewed", "correct", "wrong", "missing_important_context", "not_sure"];
const FIXTURE_TABS = {
  nodes: { label: "Nodes", key: "candidate_nodes" },
  edges: { label: "Edges", key: "candidate_reference_edges" },
  questions: { label: "Evidence Questions", key: "candidate_evidence_questions" },
  blast: { label: "Blast Radius", key: "candidate_blast_radius_scenarios" },
};
const FIXTURE_COMPAT_FILES = {
  candidate_nodes: ["review-nodes.json", "candidate_nodes.review.json"],
  candidate_reference_edges: ["review-edges.json", "candidate_reference_edges.review.json"],
  candidate_evidence_questions: ["review-evidence-questions.json", "review-questions.json", "candidate_evidence_questions.review.json"],
  candidate_blast_radius_scenarios: ["review-blast-radius-scenarios.json", "review-scenarios.json", "candidate_blast_radius_scenarios.review.json"],
};
const FEATURED_CASES = [
  "immich-app/immich",
  "denoland/deno",
  "tensorflow/tensorflow",
  "go-gitea/gitea",
  "zed-industries/zed",
  "apache/hadoop",
  "openai/codex",
  "CherryHQ/cherry-studio",
];
const LIVE_RUNS_KEY = "heart-transplant:beta-runs:v1";

const state = {
  currentRepo: "immich-app/immich",
  surfaces: [],
  benchmark: null,
  backendAvailable: false,
  isAnalyzing: false,
  latestReceipt: null,
  liveRuns: [],
  benchmarkAggregate: { total: 0, ok: 0, nodeCount: 0, edgeCount: 0 },
  fixture: {
    packet: null,
    canonicalGraph: null,
    activeTab: "nodes",
    filter: "all",
  },
};

const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
  $("repo-form").addEventListener("submit", onRepoSubmit);
  state.liveRuns = loadLiveRuns();
  loadBenchmark();
  renderCaseBoard();
  renderEmptyResults();
  startHeartbeat();
  setupFixtureReview();
  renderFixtureReview();
  detectBackend();
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
  if (state.isAnalyzing) {
    setStatus("Analysis is already running. Please wait for this repo to finish.");
    return;
  }
  state.currentRepo = repo;
  const button = document.querySelector("button[type='submit']");
  state.isAnalyzing = true;
  button.classList.add("is-loading");
  button.disabled = true;
  button.textContent = "Analyzing";
  setStatus(`Starting analysis for ${repo}...`);
  try {
    if (state.backendAvailable) {
      await ingestRepoHosted(repo);
    } else {
      await ingestRepoStaticPreview(repo);
    }
  } catch (error) {
    recordLiveRun({ repo, status: "failed", error: error.message, node_count: 0, edge_count: 0 });
    setStatus(`Analysis stopped: ${error.message}`, true);
  } finally {
    state.isAnalyzing = false;
    button.classList.remove("is-loading");
    button.disabled = false;
    button.textContent = "Start analysis";
  }
}

async function detectBackend() {
  try {
    const health = await fetchJson("./api/health");
    state.backendAvailable = Boolean(health.ok);
    $("runtime-mode").textContent = `hosted backend API; ${health.active_jobs}/${health.max_active_jobs} active jobs`;
    setStatus("Hosted analyzer ready for a public GitHub repository.");
  } catch {
    state.backendAvailable = false;
    $("runtime-mode").textContent = "static preview fallback";
    setStatus("Hosted analyzer is not available; using browser preview sampler.");
  }
}

async function ingestRepoHosted(repo) {
  setStatus(`Submitting hosted analysis for ${repo}.`);
  const response = await fetch("./api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo }),
  });
  const job = await response.json();
  if (!response.ok) throw new Error(job.error || `API returned ${response.status}`);
  setStatus(`Hosted job ${job.job_id} queued for ${repo}.`);
  const completed = await pollJob(job.job_id);
  if (completed.status !== "succeeded") throw new Error(completed.error || "Hosted analysis failed.");
  const result = completed.result;
  state.latestReceipt = result;
  state.surfaces = result.surfaces.map((surface) => ({
    path: surface.path,
    block: surface.block,
    confidence: surface.confidence,
    signal: surface.signal,
    language: surface.language,
    kind: surface.kind,
  }));
  renderRepoResults();
  renderRuntimeReceipt(result);
  recordLiveRun({
    repo,
    status: "ok",
    node_count: Number(result.summary.node_count || 0),
    edge_count: Number(result.summary.edge_count || 0),
    parser_backends: result.summary.parser_backends || [],
  });
  setStatus(`Analysis complete for ${repo}: ${formatNumber(result.summary.node_count)} nodes, ${formatNumber(result.summary.edge_count)} edges.`);
}

async function pollJob(jobId) {
  for (let attempt = 0; attempt < 240; attempt += 1) {
    const job = await fetchJson(`./api/jobs/${encodeURIComponent(jobId)}`);
    if (job.status === "succeeded" || job.status === "failed") return job;
    const detail = job.message || (job.status === "running" ? "Hosted analyzer is running." : "Hosted analyzer is queued.");
    setStatus(`Hosted job ${jobId}: ${detail}`);
    await sleep(attempt < 5 ? 900 : 1800);
  }
  throw new Error("Hosted analysis timed out in the browser.");
}

async function ingestRepoStaticPreview(repo) {
  setStatus(`Preparing browser preview for ${repo}...`);
  const meta = await fetchJson(`https://api.github.com/repos/${repo}`);
  const branch = meta.default_branch || "main";
  const tree = await fetchJson(`https://api.github.com/repos/${repo}/git/trees/${encodeURIComponent(branch)}?recursive=1`);
  const files = tree.tree
    .filter((item) => item.type === "blob" && SOURCE_EXTENSIONS.test(item.path) && !SKIP_PATHS.test(item.path))
    .slice(0, 280);
  setStatus(`Preview-classifying ${files.length} file surfaces from ${repo}; sampling content from the first 55.`);
  const contentMap = await fetchSampledContent(repo, branch, files.slice(0, 55));
  state.surfaces = files.map((file) => classifySurface(file.path, contentMap.get(file.path) || ""));
  state.latestReceipt = null;
  renderRepoResults();
  renderRuntimeReceipt(null);
  setStatus(`Preview analysis complete for ${repo}: ${state.surfaces.length} file surfaces classified.`);
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
  renderOperatorAnswers(state.latestReceipt);
  const counts = countBy(state.surfaces, (surface) => surface.block);
  const rows = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);
  drawBarChart($("repo-block-chart"), rows, { title: "Primary block count", suffix: " files" });
  $("block-list").innerHTML = rows
    .map(([block, count]) => `<div class="block-pill"><strong>${escapeHtml(block)}</strong><span>${count} file surfaces detected</span></div>`)
    .join("");
  $("surface-table").innerHTML = state.surfaces
    .slice()
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 80)
    .map(
      (surface) => `<tr><td>${escapeHtml(surface.path)}</td><td>${escapeHtml(surface.block)}</td><td>${Math.round(surface.confidence * 100)}%</td><td>${escapeHtml(surface.signal)}</td></tr>`,
    )
    .join("");
  renderBlockTree();
}

function renderEmptyResults() {
  drawBarChart($("repo-block-chart"), [], { title: "Primary block count", suffix: " nodes" });
  $("block-list").innerHTML = `<div class="block-pill"><strong>Waiting for analysis</strong><span>Submit a public GitHub repository to analyze it.</span></div>`;
  $("surface-table").innerHTML = `<tr><td colspan="4">No repo run yet.</td></tr>`;
  $("block-tree").innerHTML = `<div class="fixture-empty">No repository analyzed yet.</div>`;
  $("answer-grid").innerHTML = `
    <div class="answer-card">
      <strong>Analyze a repo to map its blocks.</strong>
      <p>Blocks are early labels for what files appear to do. Use them to find auth, persistence, background work, risky seams, and results that need closer review.</p>
    </div>`;
  renderRuntimeReceipt(null);
}

function renderOperatorAnswers(result) {
  const insights = result?.insights || [];
  if (!insights.length) {
    $("answer-grid").innerHTML = `
      <div class="answer-card">
        <strong>Static preview mode.</strong>
        <p>The hosted backend returns richer operator answers. The browser fallback keeps only block evidence.</p>
      </div>`;
    return;
  }
  $("answer-grid").innerHTML = insights
    .map((insight) => {
      const samples = insight.samples || [];
      const blocks = insight.dominant_blocks || [];
      return `
        <article class="answer-card">
          <strong>${escapeHtml(insight.title)}</strong>
          <p>${escapeHtml(insight.answer)}</p>
          ${
            samples.length
              ? `<ul>${samples
                  .map(
                    (sample) =>
                      `<li><span>${escapeHtml(sample.path)}</span><small>${escapeHtml(sample.block)} · ${Math.round(Number(sample.confidence || 0) * 100)}%</small></li>`,
                  )
                  .join("")}</ul>`
              : blocks.length
                ? `<ul>${blocks.map((block) => `<li><span>${escapeHtml(block.block)}</span><small>${formatNumber(block.count)} nodes</small></li>`).join("")}</ul>`
                : `<em>${escapeHtml(insight.empty_state || "No evidence returned.")}</em>`
          }
        </article>`;
    })
    .join("");
}

function renderRuntimeReceipt(result) {
  if (!result) {
    $("runtime-receipt").textContent = "No completed analysis yet.";
    return;
  }
  const integrity = result.summary.graph_integrity?.overall_status || "unknown";
  const manifest = result.summary.manifest?.required_artifacts_present ? "manifest complete" : "manifest incomplete";
  const artifactId = String(result.artifact_dir || "").split(/[\\/]/).filter(Boolean).pop() || "artifact saved";
  $("runtime-mode").textContent = `hosted backend API; ${result.runtime_capabilities.structural_ingest}`;
  $("runtime-receipt").textContent = `${manifest}; graph integrity ${integrity}; artifact ${artifactId}`;
}

function renderBlockTree() {
  const byDirectory = new Map();
  for (const surface of state.surfaces) {
    const parts = surface.path.split("/");
    const directory = parts.length > 1 ? parts[0] : ".";
    if (!byDirectory.has(directory)) byDirectory.set(directory, []);
    byDirectory.get(directory).push(surface);
  }
  const branches = [...byDirectory.entries()]
    .map(([directory, surfaces]) => {
      const blockCounts = [...countBy(surfaces, (surface) => surface.block).entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
      return { directory, total: surfaces.length, blockCounts };
    })
    .sort((a, b) => b.total - a.total)
    .slice(0, 8);
  renderBlockTreeFallback(branches);
}

function renderBlockTreeFallback(branches) {
  $("block-tree").innerHTML = `
    <div class="trees-root" role="tree" aria-label="Detected block tree" data-slot="file-tree" data-tree-library="smui-file-tree">
      <div class="trees-row repo-row" role="treeitem" aria-level="1" aria-expanded="true">
        <span class="trees-twist" aria-hidden="true">▾</span>
        <span class="trees-label">${escapeHtml(state.currentRepo)}</span>
      </div>
      ${branches
        .map(
          (branch, branchIndex) => `
            <div class="trees-branch" role="group">
              <div class="trees-row" role="treeitem" aria-level="2" aria-expanded="true">
                <span class="trees-indent" aria-hidden="true"></span>
                <span class="trees-twist" aria-hidden="true">▾</span>
                <span class="trees-label">${escapeHtml(branch.directory)}/</span>
                <span class="trees-count">${branch.total} file surfaces</span>
              </div>
              ${branch.blockCounts
                .map(
                  ([block, count]) => `
                    <div class="trees-row trees-leaf" role="treeitem" aria-level="3">
                      <span class="trees-indent" aria-hidden="true"></span>
                      <span class="trees-indent" aria-hidden="true"></span>
                      <span class="trees-twist" aria-hidden="true"></span>
                      <span class="trees-label">${escapeHtml(block)}</span>
                      <span class="trees-count">${count}</span>
                    </div>`,
                )
                .join("")}
            </div>`,
        )
        .join("")}
    </div>`;
}

function setupFixtureReview() {
  $("fixture-files").addEventListener("change", (event) => loadFixtureFiles(event.target.files));
  $("fixture-json").addEventListener("change", (event) => loadFixtureFiles(event.target.files));
  $("fixture-filter").addEventListener("change", (event) => {
    state.fixture.filter = event.target.value;
    renderFixtureReview();
  });
  $("fixture-export").addEventListener("click", exportFixtureReview);
  $("fixture-mark-correct").addEventListener("click", () => bulkReviewVisible("correct"));
  $("fixture-reset-visible").addEventListener("click", () => bulkReviewVisible("unreviewed"));
  document.querySelectorAll("[data-fixture-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      state.fixture.activeTab = button.dataset.fixtureTab;
      renderFixtureReview();
    });
  });
  $("fixture-list").addEventListener("click", onFixtureListClick);
  $("fixture-list").addEventListener("input", onFixtureListInput);
  $("fixture-list").addEventListener("change", onFixtureListInput);
  document.addEventListener("keydown", onFixtureShortcut);
}

async function loadFixtureFiles(fileList) {
  const files = [...fileList];
  if (!files.length) return;
  $("fixture-repo").textContent = "Loading packet";
  $("fixture-artifact").textContent = `${files.length} selected file${files.length === 1 ? "" : "s"}`;
  $("fixture-graph").innerHTML = "";
  $("fixture-stats").innerHTML = `<div class="fixture-stat"><strong>...</strong><span>loading</span></div>`;
  $("fixture-list").innerHTML = `<div class="fixture-empty">Reading packet JSON and preparing review cards...</div>`;
  const jsonByName = new Map();
  for (const file of files) {
    if (!file.name.endsWith(".json")) continue;
    try {
      jsonByName.set(file.name, JSON.parse(await file.text()));
    } catch (error) {
      $("fixture-list").innerHTML = `<div class="fixture-empty">Could not parse ${escapeHtml(file.name)}: ${escapeHtml(error.message)}</div>`;
      return;
    }
  }
  const packet = jsonByName.get("fixture-candidates.json") || synthesizeFixturePacket(jsonByName) || [...jsonByName.values()].find((item) => item?.report_type === "fixture_training_packet");
  if (!packet) {
    $("fixture-list").innerHTML = `<div class="fixture-empty">No fixture-candidates.json file found in that selection.</div>`;
    return;
  }
  state.fixture.packet = normalizeFixturePacket(packet, jsonByName);
  state.fixture.canonicalGraph = jsonByName.get("canonical-graph.snapshot.json") || null;
  state.fixture.activeTab = "nodes";
  state.fixture.filter = "all";
  $("fixture-filter").value = "all";
  renderFixtureReview();
}

function synthesizeFixturePacket(jsonByName) {
  const hasCompatibilityFiles = Object.values(FIXTURE_COMPAT_FILES).some((names) => names.some((name) => jsonByName.has(name)));
  if (!hasCompatibilityFiles) return null;
  const graph = jsonByName.get("canonical-graph.snapshot.json") || {};
  return {
    report_type: "fixture_training_packet",
    artifact_dir: graph.artifact_dir || "",
    repo_name: graph.repo_name || "review packet",
    review_protocol: {
      labels: REVIEW_LABELS,
      instruction: "Review generated candidates, mark status, and add notes or traces.",
    },
    candidate_nodes: [],
    candidate_reference_edges: [],
    candidate_evidence_questions: [],
    candidate_blast_radius_scenarios: [],
  };
}

function normalizeFixturePacket(packet, jsonByName = new Map()) {
  const next = structuredClone(packet);
  next.review_protocol = next.review_protocol || {
    labels: REVIEW_LABELS,
    instruction: "Review each generated fixture candidate.",
  };
  for (const [key, names] of Object.entries(FIXTURE_COMPAT_FILES)) {
    const override = names.map((name) => jsonByName.get(name)).find(Array.isArray);
    next[key] = normalizeReviewArray(override || next[key]);
  }
  return next;
}

function normalizeReviewArray(items) {
  return (items || []).map((item) => ({
    ...item,
    review: REVIEW_LABELS.includes(item.review) ? item.review : "unreviewed",
    human_notes: item.human_notes || "",
    human_traces: normalizeTraceArray(item.human_traces),
  }));
}

function normalizeTraceArray(value) {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === "string" && value.trim()) return splitLines(value);
  return [];
}

function renderFixtureReview() {
  const packet = state.fixture.packet;
  const summary = packet ? reviewSummary(packet) : null;
  $("fixture-export").disabled = !packet;
  $("fixture-mark-correct").disabled = !packet || state.fixture.activeTab === "summary";
  $("fixture-reset-visible").disabled = !packet || state.fixture.activeTab === "summary";
  document.querySelectorAll("[data-fixture-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.fixtureTab === state.fixture.activeTab);
  });
  $("fixture-repo").textContent = packet?.repo_name || "No packet loaded";
  $("fixture-artifact").textContent = packet?.artifact_dir || "Load fixture-candidates.json or the whole packet directory.";
  $("fixture-graph").innerHTML = packet ? renderFixtureGraphSummary() : "";
  $("fixture-stats").innerHTML = summary
    ? renderFixtureStats(summary, packet)
    : `<div class="fixture-stat"><strong>0</strong><span>candidates</span></div><div class="fixture-stat"><strong>0</strong><span>reviewed</span></div>`;

  if (!packet) {
    $("fixture-list").innerHTML = `<div class="fixture-empty">Load a packet to review candidate nodes, edges, evidence questions, and blast-radius scenarios.</div>`;
    return;
  }

  if (state.fixture.activeTab === "summary") {
    $("fixture-list").innerHTML = renderFixtureSummary(packet, summary);
    return;
  }

  const config = FIXTURE_TABS[state.fixture.activeTab];
  const visible = getVisibleFixtureItems();
  $("fixture-list").innerHTML = visible.length
    ? visible.map(({ item, index }) => renderFixtureCard(config.key, item, index)).join("")
    : `<div class="fixture-empty">No ${escapeHtml(config.label.toLowerCase())} match this filter.</div>`;
}

function renderFixtureStats(summary, packet) {
  const counts = [
    ["total", summary.total],
    ["reviewed", summary.reviewed],
    ["correct", summary.correct],
    ["wrong", summary.wrong],
    ["missing context", summary.missing_important_context],
    ["not sure", summary.not_sure],
  ];
  return counts.map(([label, value]) => `<div class="fixture-stat"><strong>${formatNumber(value)}</strong><span>${escapeHtml(label)}</span></div>`).join("");
}

function renderFixtureGraphSummary() {
  const graph = state.fixture.canonicalGraph;
  if (!graph?.summary) {
    return `<div class="fixture-graph-empty">Canonical graph snapshot not loaded. Candidate review still works, but source/target context will be limited.</div>`;
  }
  const layers = (graph.summary.layers || []).join(", ") || "none";
  return `
    <div class="fixture-graph-grid">
      <span><strong>${formatNumber(graph.summary.node_count || 0)}</strong> graph nodes</span>
      <span><strong>${formatNumber(graph.summary.edge_count || 0)}</strong> graph edges</span>
      <span><strong>${formatNumber(graph.summary.dangling_edge_count || 0)}</strong> dangling edges</span>
      <span><strong>${escapeHtml(layers)}</strong> layers</span>
    </div>`;
}

function renderFixtureSummary(packet, summary) {
  const graph = state.fixture.canonicalGraph;
  return `
    <div class="fixture-summary">
      <div>
        <h3>Review Summary</h3>
        <p>${formatNumber(summary.reviewed)} of ${formatNumber(summary.total)} candidates reviewed for ${escapeHtml(packet.repo_name || "this repo")}.</p>
      </div>
      <div class="tag-row">
        <span class="tag">nodes ${formatNumber((packet.candidate_nodes || []).length)}</span>
        <span class="tag">edges ${formatNumber((packet.candidate_reference_edges || []).length)}</span>
        <span class="tag">questions ${formatNumber((packet.candidate_evidence_questions || []).length)}</span>
        <span class="tag">blast ${formatNumber((packet.candidate_blast_radius_scenarios || []).length)}</span>
      </div>
      ${
        graph?.summary
          ? `<div class="tag-row">
              <span class="tag">graph nodes ${formatNumber(graph.summary.node_count || 0)}</span>
              <span class="tag">graph edges ${formatNumber(graph.summary.edge_count || 0)}</span>
              <span class="tag">dangling ${formatNumber(graph.summary.dangling_edge_count || 0)}</span>
              <span class="tag">layers ${(graph.summary.layers || []).map(escapeHtml).join(", ")}</span>
            </div>`
          : `<p class="fixture-meta">Canonical graph snapshot not loaded. Review still works without graph context.</p>`
      }
      <p class="fixture-meta">Export writes reviewed-fixture-packet.json plus review-nodes, review-edges, review-evidence-questions, and review-blast-radius-scenarios compatibility files.</p>
    </div>`;
}

function getVisibleFixtureItems() {
  const packet = state.fixture.packet;
  if (!packet || state.fixture.activeTab === "summary") return [];
  const config = FIXTURE_TABS[state.fixture.activeTab];
  const filter = state.fixture.filter;
  return (packet[config.key] || [])
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => filter === "all" || item.review === filter)
    .sort((a, b) => fixtureSortKey(a.item).localeCompare(fixtureSortKey(b.item)));
}

function fixtureSortKey(item) {
  const reviewPrefix = item.review === "unreviewed" ? "0" : "1";
  const blockPrefix = item.suggested_blocks?.length || item.expected_blocks?.length || item.expected_impacted_blocks?.length ? "0" : "1";
  return `${reviewPrefix}:${blockPrefix}:${item.file_path || item.source_file || item.target_file || item.id || item.node_id || ""}`;
}

function renderFixtureCard(key, item, index) {
  const body =
    key === "candidate_nodes"
      ? renderNodeCandidate(item)
      : key === "candidate_reference_edges"
        ? renderEdgeCandidate(item)
        : key === "candidate_evidence_questions"
          ? renderEvidenceCandidate(item)
          : renderBlastCandidate(item);
  return `
    <article class="fixture-card" data-key="${key}" data-index="${index}" tabindex="-1">
      <header>
        <div>${body.heading}</div>
        <span class="status-chip">${reviewLabel(item.review)}</span>
      </header>
      ${body.content}
      ${renderReviewControls(item)}
    </article>`;
}

function renderNodeCandidate(item) {
  return {
    heading: `<h3>${escapeHtml(item.file_path || item.label || item.node_id)}</h3><small>${escapeHtml(item.kind || "node")} ${item.label ? ` / ${escapeHtml(item.label)}` : ""}</small>`,
    content: `
      <div class="tag-row">${(item.suggested_blocks || []).map((block) => `<span class="tag">${escapeHtml(block)}</span>`).join("") || `<span class="tag">no suggested blocks</span>`}</div>
      ${renderNodeGraphContext(item)}
      <details><summary>node id</summary><pre>${escapeHtml(item.node_id || "")}</pre></details>`,
  };
}

function renderEdgeCandidate(item) {
  return {
    heading: `<h3>${escapeHtml(item.relationship || "reference edge")}</h3><small>${escapeHtml(item.source_file || item.source_label || item.source_id)} --> ${escapeHtml(item.target_file || item.target_label || item.target_id)}</small>`,
    content: `
      <div class="fixture-grid">
        <div class="field"><label>source</label><code>${escapeHtml(item.source_file || item.source_label || item.source_id)}</code></div>
        <div class="field"><label>target</label><code>${escapeHtml(item.target_file || item.target_label || item.target_id)}</code></div>
        <div class="field"><label for="edge-expectation-${item.source_id}-${item.target_id}">resolution expectation</label>${renderSelect("resolution_expectation", item.resolution_expectation || "not_sure", ["must", "nice", "fallback_ok", "not_sure"])}</div>
      </div>
      ${renderEdgeGraphContext(item)}`,
  };
}

function renderEvidenceCandidate(item) {
  return {
    heading: `<h3>${escapeHtml(item.question || item.id)}</h3><small>${escapeHtml(item.id || "evidence question")}</small>`,
    content: `
      <div class="fixture-grid">
        ${renderTextField("question", "question", item.question || "")}
        ${renderTextArea("expected_blocks", "expected blocks", joinLines(item.expected_blocks))}
        ${renderTextArea("expected_files", "expected files", joinLines(item.expected_files))}
        ${renderTextArea("expected_file_globs", "expected file globs", joinLines(item.expected_file_globs))}
        <label class="field"><span>unsupported</span><select data-field="unsupported"><option value="false"${!item.unsupported ? " selected" : ""}>no</option><option value="true"${item.unsupported ? " selected" : ""}>yes</option></select></label>
      </div>
      ${renderFilesGraphContext([...(item.expected_files || []), ...(item.expected_file_globs || [])])}`,
  };
}

function renderBlastCandidate(item) {
  return {
    heading: `<h3>${escapeHtml(item.change || item.id)}</h3><small>${escapeHtml(item.id || "blast-radius scenario")}</small>`,
    content: `
      <div class="fixture-grid">
        ${renderTextArea("expected_impacted_files", "expected impacted files", joinLines(item.expected_impacted_files))}
        ${renderTextArea("expected_impacted_blocks", "expected impacted blocks", joinLines(item.expected_impacted_blocks))}
        ${renderTextArea("should_not_impact", "should not impact", joinLines(item.should_not_impact))}
        <div class="field"><label>risk level</label>${renderSelect("risk_level", item.risk_level || "not_sure", ["low", "medium", "high", "not_sure"])}</div>
        ${renderTextField("validation_command", "validation command", item.validation_command || "")}
      </div>
      ${renderFilesGraphContext([...(item.expected_impacted_files || []), ...(item.should_not_impact || [])])}`,
  };
}

function renderNodeGraphContext(item) {
  const node = findGraphNode(item.node_id);
  const related = relatedNodesForFile(item.file_path || node?.file_path).filter((candidate) => candidate.node_id !== item.node_id).slice(0, 4);
  if (!node && !related.length) return "";
  return `
    <details class="graph-context">
      <summary>graph context</summary>
      ${node ? renderGraphNodeLine(node) : ""}
      ${related.length ? `<div class="context-list">${related.map(renderGraphNodeLine).join("")}</div>` : ""}
    </details>`;
}

function renderEdgeGraphContext(item) {
  const source = findGraphNode(item.source_id);
  const target = findGraphNode(item.target_id);
  if (!source && !target) return "";
  return `
    <details class="graph-context">
      <summary>source / target context</summary>
      ${source ? `<div class="context-pair"><strong>source</strong>${renderGraphNodeLine(source)}</div>` : ""}
      ${target ? `<div class="context-pair"><strong>target</strong>${renderGraphNodeLine(target)}</div>` : ""}
    </details>`;
}

function renderFilesGraphContext(files) {
  const related = [...new Map(files.flatMap((file) => relatedNodesForFile(file)).map((node) => [node.node_id, node])).values()].slice(0, 6);
  if (!related.length) return "";
  return `
    <details class="graph-context">
      <summary>related graph nodes</summary>
      <div class="context-list">${related.map(renderGraphNodeLine).join("")}</div>
    </details>`;
}

function findGraphNode(nodeId) {
  if (!nodeId || !state.fixture.canonicalGraph?.nodes) return null;
  return state.fixture.canonicalGraph.nodes.find((node) => String(node.node_id) === String(nodeId)) || null;
}

function relatedNodesForFile(filePath) {
  if (!filePath || !state.fixture.canonicalGraph?.nodes) return [];
  return state.fixture.canonicalGraph.nodes.filter((node) => node.file_path === filePath);
}

function renderGraphNodeLine(node) {
  const file = node.file_path || node.label || node.node_id;
  const range = formatRange(node.range);
  return `
    <div class="context-line">
      <code>${escapeHtml(file || "")}</code>
      <span>${escapeHtml([node.layer, node.kind, range].filter(Boolean).join(" / "))}</span>
    </div>`;
}

function formatRange(range) {
  if (!range) return "";
  const start = range.start_line ?? range.startLine;
  const end = range.end_line ?? range.endLine;
  if (!start && !end) return "";
  return start === end || !end ? `line ${start}` : `lines ${start}-${end}`;
}

function renderReviewControls(item) {
  return `
    <div class="review-controls">
      <div class="review-actions">
        ${REVIEW_LABELS.filter((label) => label !== "unreviewed")
          .map((label) => `<button type="button" data-review="${label}" class="${item.review === label ? "active" : ""}">${reviewLabel(label)}</button>`)
          .join("")}
      </div>
      <div class="field">
        <label>notes</label>
        <textarea data-field="human_notes" placeholder="Optional notes or traces">${escapeHtml(item.human_notes || "")}</textarea>
      </div>
      <div class="field">
        <label>traces</label>
        <textarea data-field="human_traces" placeholder="One trace, file path, or evidence hint per line">${escapeHtml(joinLines(item.human_traces))}</textarea>
      </div>
    </div>`;
}

function renderTextField(field, label, value) {
  return `<div class="field"><label>${escapeHtml(label)}</label><input data-field="${field}" value="${escapeAttribute(value)}" /></div>`;
}

function renderTextArea(field, label, value) {
  return `<div class="field"><label>${escapeHtml(label)}</label><textarea data-field="${field}">${escapeHtml(value)}</textarea></div>`;
}

function renderSelect(field, value, options) {
  return `<select data-field="${field}">${options.map((option) => `<option value="${option}"${option === value ? " selected" : ""}>${reviewLabel(option)}</option>`).join("")}</select>`;
}

function onFixtureListClick(event) {
  const review = event.target.closest("[data-review]")?.dataset.review;
  if (!review) return;
  const card = event.target.closest(".fixture-card");
  const item = getFixtureItem(card);
  item.review = review;
  renderFixtureReview();
}

function onFixtureListInput(event) {
  const field = event.target.dataset.field;
  if (!field) return;
  const card = event.target.closest(".fixture-card");
  const item = getFixtureItem(card);
  item[field] = parseFixtureField(field, event.target.value);
  renderFixtureStatsOnly();
}

function getFixtureItem(card) {
  return state.fixture.packet[card.dataset.key][Number(card.dataset.index)];
}

function parseFixtureField(field, value) {
  if (field === "unsupported") return value === "true";
  if (["expected_blocks", "expected_files", "expected_file_globs", "expected_impacted_files", "expected_impacted_blocks", "should_not_impact", "human_traces"].includes(field)) {
    return splitLines(value);
  }
  return value;
}

function renderFixtureStatsOnly() {
  if (!state.fixture.packet) return;
  $("fixture-stats").innerHTML = renderFixtureStats(reviewSummary(state.fixture.packet), state.fixture.packet);
}

function bulkReviewVisible(review) {
  for (const { item } of getVisibleFixtureItems()) item.review = review;
  renderFixtureReview();
}

function onFixtureShortcut(event) {
  if (!state.fixture.packet || ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
  const map = { 1: "correct", 2: "wrong", 3: "missing_important_context", 4: "not_sure" };
  if (event.key.toLowerCase() === "n") {
    event.preventDefault();
    focusNextFixtureCard();
    return;
  }
  if (map[event.key]) {
    const first = getVisibleFixtureItems()[0];
    if (first) {
      first.item.review = map[event.key];
      renderFixtureReview();
    }
  }
}

function focusNextFixtureCard() {
  const cards = [...document.querySelectorAll(".fixture-card")];
  if (!cards.length) return;
  const current = document.activeElement?.closest?.(".fixture-card");
  const currentIndex = current ? cards.indexOf(current) : -1;
  const next = cards[Math.min(currentIndex + 1, cards.length - 1)] || cards[0];
  next.focus({ preventScroll: true });
  next.scrollIntoView({ block: "center", behavior: "smooth" });
}

function exportFixtureReview() {
  const packet = state.fixture.packet;
  if (!packet) return;
  const reviewed = {
    ...packet,
    reviewed_at: new Date().toISOString(),
    reviewer: $("fixture-reviewer")?.value || undefined,
    summary: reviewSummary(packet),
  };
  downloadJson("reviewed-fixture-packet.json", reviewed);
  downloadJson("review-nodes.json", packet.candidate_nodes || []);
  downloadJson("review-edges.json", packet.candidate_reference_edges || []);
  downloadJson("review-evidence-questions.json", packet.candidate_evidence_questions || []);
  downloadJson("review-blast-radius-scenarios.json", packet.candidate_blast_radius_scenarios || []);
}

function reviewSummary(packet) {
  const items = [
    ...(packet.candidate_nodes || []),
    ...(packet.candidate_reference_edges || []),
    ...(packet.candidate_evidence_questions || []),
    ...(packet.candidate_blast_radius_scenarios || []),
  ];
  return {
    total: items.length,
    reviewed: items.filter((item) => item.review !== "unreviewed").length,
    correct: items.filter((item) => item.review === "correct").length,
    wrong: items.filter((item) => item.review === "wrong").length,
    missing_important_context: items.filter((item) => item.review === "missing_important_context").length,
    not_sure: items.filter((item) => item.review === "not_sure").length,
  };
}

function downloadJson(filename, data) {
  const blob = new Blob([`${JSON.stringify(data, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function reviewLabel(value) {
  return String(value || "unreviewed").replaceAll("_", " ");
}

function joinLines(values) {
  return (values || []).join("\n");
}

function splitLines(value) {
  return String(value)
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

async function loadBenchmark() {
  try {
    state.benchmark = await fetchJson("./evals/trending-top50-ec2-summary-2026-04-27.json");
    renderBenchmark();
    renderCaseBoard();
  } catch (error) {
    $("bench-findings").innerHTML = `<div class="finding"><strong>Benchmark unavailable</strong><span>${escapeHtml(error.message)}</span></div>`;
  }
}

function renderCaseBoard() {
  const resultByRepo = new Map((state.benchmark?.results || []).map((item) => [item.full_name, item]));
  $("case-grid").innerHTML = FEATURED_CASES.map((repo) => {
    const [owner, name] = repo.split("/");
    const result = resultByRepo.get(repo);
    const nodes = result?.node_count != null ? compactNumber(Number(result.node_count)) : "live";
    const status = result?.status === "ok" ? "reference ok" : result?.status === "ingest_failed" ? "needs review" : "try live";
    const language = result?.language || "repo";
    return `
      <button class="case-card" type="button" data-repo="${escapeHtml(repo)}">
        <span class="case-head">
          <img src="https://github.com/${escapeHtml(owner)}.png?size=96" alt="" loading="lazy" />
          <span>
            <strong>${escapeHtml(name)}</strong>
            <span>${escapeHtml(owner)}</span>
          </span>
        </span>
        <span class="case-meta">
          <span>${escapeHtml(language)}</span>
          <span>${escapeHtml(status)}</span>
          <span>${nodes} nodes</span>
        </span>
      </button>`;
  }).join("");
  document.querySelectorAll(".case-card").forEach((card) => {
    card.addEventListener("click", () => {
      const repo = card.getAttribute("data-repo");
      $("repo-input").value = repo;
      ingestRepo(repo);
    });
  });
}

function renderBenchmark() {
  const benchmark = state.benchmark;
  const languageRows = Object.entries(benchmark.by_language || {});
  const aggregate = buildBenchmarkAggregate();
  state.benchmarkAggregate = aggregate;
  startHeartbeat();

  drawBarChart(
    $("language-chart"),
    languageRows.map(([language, value]) => {
      const total = Number(value.total || 0);
      const ok = Number(value.ok || 0);
      return [language, total ? Math.round((ok / total) * 100) : 0, `${ok}/${total}`];
    }),
    { title: "Successful analyses by language", suffix: "%", left: 126, max: 100 },
  );
  drawBarChart(
    $("node-chart"),
    languageRows.map(([language, value]) => [language, Number(value.node_count || 0)]),
    { title: "Code nodes by language", suffix: " nodes" },
  );
  const largest = [...(benchmark.results || [])]
    .filter((item) => item.status === "ok")
    .sort((a, b) => Number(b.node_count || 0) - Number(a.node_count || 0))
    .slice(0, 10)
    .map((item) => [item.full_name, Number(item.node_count || 0)]);
  drawBarChart($("largest-chart"), largest, { title: "Code nodes found per repository", suffix: " nodes" });

  const failed = benchmark.by_status?.ingest_failed || 0;
  const zeroNode = languageRows.reduce((sum, [, value]) => sum + Number(value.zero_node || 0), 0);
  const failedLive = state.liveRuns.filter((run) => run.status === "failed").length;
  const liveOk = state.liveRuns.filter((run) => run.status === "ok").length;
  $("bench-findings").innerHTML = [
    ["Analyzed", `${aggregate.total} total runs: ${benchmark.total || 0} reference repos plus ${state.liveRuns.length} browser runs.`],
    ["Completed", `${aggregate.ok} successful analyses, including ${liveOk} from this browser.`],
    ["Needs review", `${failed + zeroNode + failedLive} runs need review: ${failed + failedLive} failures and ${zeroNode} zero-node reference runs.`],
    ["Current fixes", `Generated/vendor output is skipped for live analysis; source coverage includes Rust, Java, C, and C++.`],
  ]
    .map(([title, body]) => `<div class="finding"><strong>${title}</strong><span>${body}</span></div>`)
    .join("");
  renderComplications(benchmark);
}

function renderComplications(benchmark) {
  const failedRows = (benchmark.results || []).filter((item) => item.status === "ingest_failed");
  const zeroRows = (benchmark.results || []).filter((item) => item.status === "ok" && Number(item.node_count || 0) === 0);
  $("complication-panel").innerHTML = `
    <h3>Complications and fix status</h3>
    <div class="complication-summary">
      <div><strong>${failedRows.length}</strong><span>first-run ingest crashes. Root cause: recursive Tree-sitter traversal hit Python recursion depth on deep parse trees. Fix: iterative traversal in backend ingest.</span></div>
      <div><strong>${zeroRows.length}</strong><span>zero-node successes. Root cause: repos in Java/C++/Rust trending categories had unsupported first-class source languages. Fix: Rust, Java, C, and C++ parser coverage.</span></div>
      <div><strong>${failedRows.length + zeroRows.length}</strong><span>reference runs still tracked as quality-gate pressure.</span></div>
    </div>
    <div class="complication-table">
      <table>
        <thead>
          <tr>
            <th>Repo</th>
            <th>First-run issue</th>
            <th>What happened</th>
            <th>Current fix</th>
          </tr>
        </thead>
        <tbody>
          ${failedRows.map((row) => `
            <tr>
              <td>${escapeHtml(row.full_name)}</td>
              <td>ingest crash</td>
              <td>Deep parse tree triggered recursive visitor overflow.</td>
              <td>Tree-sitter walker is iterative now.</td>
            </tr>`).join("")}
          ${zeroRows.map((row) => `
            <tr>
              <td>${escapeHtml(row.full_name)}</td>
              <td>zero-node success</td>
              <td>Run completed, but no first-class source symbols were extracted.</td>
              <td>Added direct source coverage for Rust, Java, C, and C++.</td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
}

function buildBenchmarkAggregate() {
  const benchmark = state.benchmark || {};
  const languageRows = Object.entries(benchmark.by_language || {});
  const baselineNodes = languageRows.reduce((sum, [, value]) => sum + Number(value.node_count || 0), 0);
  const baselineEdges = languageRows.reduce((sum, [, value]) => sum + Number(value.edge_count || 0), 0);
  const liveOk = state.liveRuns.filter((run) => run.status === "ok");
  return {
    total: Number(benchmark.total || 0) + state.liveRuns.length,
    ok: Number(benchmark.by_status?.ok || 0) + liveOk.length,
    nodeCount: baselineNodes + liveOk.reduce((sum, run) => sum + Number(run.node_count || 0), 0),
    edgeCount: baselineEdges + liveOk.reduce((sum, run) => sum + Number(run.edge_count || 0), 0),
  };
}

function loadLiveRuns() {
  try {
    const raw = localStorage.getItem(LIVE_RUNS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.slice(-25) : [];
  } catch {
    return [];
  }
}

function recordLiveRun(run) {
  const stored = {
    repo: run.repo,
    status: run.status,
    node_count: Number(run.node_count || 0),
    edge_count: Number(run.edge_count || 0),
    error: run.error || null,
    parser_backends: run.parser_backends || [],
    at: new Date().toISOString(),
  };
  state.liveRuns = [...state.liveRuns, stored].slice(-25);
  try {
    localStorage.setItem(LIVE_RUNS_KEY, JSON.stringify(state.liveRuns));
  } catch {
    // The page can still update live counts during this session.
  }
  if (state.benchmark) renderBenchmark();
}

function cssHsl(name, alpha = null) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (!value) return alpha == null ? "#000000" : `rgba(0, 0, 0, ${alpha})`;
  return alpha == null ? `hsl(${value})` : `hsl(${value} / ${alpha})`;
}

function drawBarChart(canvas, rows, options = {}) {
  const ctx = canvas.getContext("2d");
  const { width, height } = canvas;
  const palette = [
    cssHsl("--primary"),
    cssHsl("--smui-frost-3"),
    cssHsl("--smui-frost-4"),
    cssHsl("--smui-teal"),
    cssHsl("--smui-indigo"),
  ];
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = cssHsl("--card");
  ctx.fillRect(0, 0, width, height);
  const max = options.max || Math.max(1, ...rows.map(([, value]) => value));
  const left = options.left || 176;
  const top = 42;
  const rightPad = 118;
  const rowHeight = Math.max(24, (height - top - 24) / Math.max(rows.length, 1));
  ctx.strokeStyle = cssHsl("--border", 0.48);
  ctx.lineWidth = 1;
  for (let x = left; x < width - rightPad; x += 92) {
    ctx.beginPath();
    ctx.moveTo(x, top - 8);
    ctx.lineTo(x, height - 18);
    ctx.stroke();
  }
  ctx.font = "18px Space Grotesk, Segoe UI, sans-serif";
  ctx.fillStyle = cssHsl("--foreground");
  ctx.fillText(options.title || "", 12, 24);
  rows.forEach(([label, value, detail], index) => {
    const y = top + index * rowHeight + 8;
    const fullWidth = Math.max(40, width - left - rightPad);
    const barWidth = Math.max(2, (fullWidth * value) / max);
    ctx.fillStyle = cssHsl("--muted-foreground");
    ctx.font = "13px JetBrains Mono, Consolas, monospace";
    ctx.fillText(truncate(label, 22), 12, y + 13);
    ctx.fillStyle = cssHsl("--background");
    ctx.fillRect(left, y, fullWidth, Math.max(10, rowHeight - 13));
    ctx.strokeStyle = cssHsl("--border", 0.72);
    ctx.strokeRect(left, y, fullWidth, Math.max(10, rowHeight - 13));
    ctx.fillStyle = palette[index % palette.length];
    ctx.fillRect(left, y, barWidth, Math.max(10, rowHeight - 12));
    ctx.fillStyle = cssHsl("--foreground");
    const displayValue = detail || `${compactNumber(value)}${options.suffix || ""}`;
    ctx.fillText(displayValue, Math.min(left + barWidth + 8, width - rightPad + 8), y + 13);
  });
}

function startHeartbeat() {
  if (state.heartbeatRunning) return;
  state.heartbeatRunning = true;
  const tick = (time) => {
    drawOscilloscope($("vitals-scope"), state.benchmarkAggregate, time);
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function drawOscilloscope(canvas, aggregate, time = 0) {
  const ctx = canvas.getContext("2d");
  const { width, height } = canvas;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = cssHsl("--card");
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = cssHsl("--border", 0.42);
  ctx.lineWidth = 1;
  for (let x = 40; x < width; x += 64) {
    ctx.beginPath();
    ctx.moveTo(x, 18);
    ctx.lineTo(x, height - 18);
    ctx.stroke();
  }
  for (let y = 28; y < height; y += 38) {
    ctx.beginPath();
    ctx.moveTo(22, y);
    ctx.lineTo(width - 22, y);
    ctx.stroke();
  }

  const okRatio = aggregate.total ? aggregate.ok / aggregate.total : 0.8;
  const density = Math.min(1, Math.log10(Math.max(aggregate.nodeCount, 1)) / 6);
  const trace = [];
  const phase = ((time || 0) / 1000) % 1.6;
  const beatCenter = phase / 1.6;
  for (let i = 0; i < 160; i += 1) {
    const t = i / 159;
    const drift = Math.sin((t + phase) * Math.PI * 6) * 7 + Math.sin((t + phase) * Math.PI * 18) * 2;
    const beatDistance = Math.abs(t - beatCenter);
    const wrapDistance = Math.min(beatDistance, Math.abs(t + 1 - beatCenter), Math.abs(t - 1 - beatCenter));
    const qrs = wrapDistance < 0.008 ? -44 * okRatio : wrapDistance < 0.018 ? 42 * density : wrapDistance < 0.035 ? -16 : 0;
    const pulse = drift + qrs;
    const spike = i % 53 === 0 ? 10 * density : 0;
    const y = height * 0.5 + pulse + spike;
    trace.push([24 + t * (width - 48), Math.max(20, Math.min(height - 20, y))]);
  }

  ctx.strokeStyle = cssHsl("--primary");
  ctx.shadowBlur = 0;
  ctx.lineWidth = 3;
  ctx.beginPath();
  trace.forEach(([x, y], index) => {
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.fillStyle = cssHsl("--foreground");
  ctx.font = "18px Space Grotesk, Segoe UI, sans-serif";
  ctx.fillText("analysis signal", 24, 30);
  ctx.fillStyle = cssHsl("--muted-foreground");
  ctx.font = "13px JetBrains Mono, Consolas, monospace";
  ctx.fillText(`${formatNumber(aggregate.total)} runs - ${formatNumber(aggregate.ok)} successful`, 24, height - 22);
}

function countBy(items, keyFn) {
  const out = new Map();
  for (const item of items) {
    const key = keyFn(item);
    out.set(key, (out.get(key) || 0) + 1);
  }
  return out;
}

function setStatus(message, isError = false) {
  const status = $("repo-status");
  status.textContent = message;
  status.style.color = isError ? cssHsl("--smui-red") : cssHsl("--muted-foreground");
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

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("\n", "&#10;");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

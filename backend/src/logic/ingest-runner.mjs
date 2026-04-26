import { Buffer } from 'node:buffer';
import { createArtifactWorkspace, writeArtifactJson } from './artifact-store.mjs';
import { buildArtifactSummary, extractFacts } from './fact-extractor.mjs';
import { createIgnorePolicy, shouldRetainArchivePath } from './ignore-catalog.mjs';
import { runRules } from './rule-engine.mjs';
import JSZip from 'jszip';

const ROOT_MANIFESTS = [
  'package.json',
  'go.mod',
  'pyproject.toml',
  'requirements.txt',
  'Cargo.toml',
  'composer.json',
];

const CATEGORY_ORDER = [
  'authentication',
  'database',
  'analytics',
  'payments',
  'ui',
  'observability',
  'cloud',
  'ai',
];

const STATIC_ALTERNATES = {
  authentication: ['better-auth', 'auth0', 'clerk', 'okta', 'supabase', 'stytch', 'supertokens'],
  database: ['postgresql', 'supabase', 'mongodb', 'mysql', 'redis', 'prisma'],
  analytics: ['posthog', 'segment', 'amplitude', 'mixpanel'],
  payments: ['stripe', 'paypal'],
  ui: ['tailwindcss', 'material-ui', 'ant-design', 'bootstrap', 'storybook'],
  observability: ['sentry', 'datadog'],
  cloud: ['cloudflare', 'vercel', 'netlify', 'aws', 'google-cloud'],
  ai: ['openai', 'anthropic', 'hugging-face'],
};

const VENDOR_LIBRARY = {
  'better-auth': { label: 'Better Auth', iconSlug: null, category: 'authentication' },
  auth0: { label: 'Auth0', iconSlug: 'auth0', category: 'authentication' },
  clerk: { label: 'Clerk', iconSlug: null, category: 'authentication' },
  okta: { label: 'Okta', iconSlug: 'okta', category: 'authentication' },
  stytch: { label: 'Stytch', iconSlug: 'stytch', category: 'authentication' },
  supertokens: { label: 'SuperTokens', iconSlug: 'supertokens', category: 'authentication' },
  supabase: { label: 'Supabase', iconSlug: 'supabase', category: 'database' },
  postgresql: { label: 'PostgreSQL', iconSlug: 'postgresql', category: 'database' },
  prisma: { label: 'Prisma', iconSlug: 'prisma', category: 'database' },
  mongodb: { label: 'MongoDB', iconSlug: 'mongodb', category: 'database' },
  mysql: { label: 'MySQL', iconSlug: 'mysql', category: 'database' },
  redis: { label: 'Redis', iconSlug: 'redis', category: 'database' },
  posthog: { label: 'PostHog', iconSlug: 'posthog', category: 'analytics' },
  segment: { label: 'Segment', iconSlug: 'segment', category: 'analytics' },
  amplitude: { label: 'Amplitude', iconSlug: 'amplitude', category: 'analytics' },
  mixpanel: { label: 'Mixpanel', iconSlug: 'mixpanel', category: 'analytics' },
  stripe: { label: 'Stripe', iconSlug: 'stripe', category: 'payments' },
  paypal: { label: 'PayPal', iconSlug: 'paypal', category: 'payments' },
  tailwindcss: { label: 'Tailwind CSS', iconSlug: 'tailwindcss', category: 'ui' },
  'material-ui': { label: 'Material UI', iconSlug: 'material-ui', category: 'ui' },
  'ant-design': { label: 'Ant Design', iconSlug: 'ant-design', category: 'ui' },
  bootstrap: { label: 'Bootstrap', iconSlug: 'bootstrap', category: 'ui' },
  storybook: { label: 'Storybook', iconSlug: 'storybook', category: 'ui' },
  sentry: { label: 'Sentry', iconSlug: 'sentry', category: 'observability' },
  datadog: { label: 'Datadog', iconSlug: 'datadog', category: 'observability' },
  cloudflare: { label: 'Cloudflare', iconSlug: 'cloudflare', category: 'cloud' },
  vercel: { label: 'Vercel', iconSlug: 'vercel', category: 'cloud' },
  netlify: { label: 'Netlify', iconSlug: 'netlify', category: 'cloud' },
  aws: { label: 'AWS', iconSlug: 'aws', category: 'cloud' },
  'google-cloud': { label: 'Google Cloud', iconSlug: 'google-cloud', category: 'cloud' },
  openai: { label: 'OpenAI', iconSlug: 'openai', category: 'ai' },
  anthropic: { label: 'Anthropic', iconSlug: 'anthropic', category: 'ai' },
  'hugging-face': { label: 'Hugging Face', iconSlug: 'hugging-face', category: 'ai' },
};

const VENDOR_RULES = [
  { test: (pkg) => /better-auth/.test(pkg), id: 'better-auth', label: 'Better Auth', category: 'authentication', iconSlug: null, confidence: 'high' },
  { test: (pkg) => /auth0/.test(pkg), id: 'auth0', label: 'Auth0', category: 'authentication', iconSlug: 'auth0', confidence: 'high' },
  { test: (pkg) => /(^|\/)clerk|@clerk/.test(pkg), id: 'clerk', label: 'Clerk', category: 'authentication', iconSlug: null, confidence: 'high' },
  { test: (pkg) => /okta/.test(pkg), id: 'okta', label: 'Okta', category: 'authentication', iconSlug: 'okta', confidence: 'high' },
  { test: (pkg) => /stytch/.test(pkg), id: 'stytch', label: 'Stytch', category: 'authentication', iconSlug: 'stytch', confidence: 'high' },
  { test: (pkg) => /supertokens/.test(pkg), id: 'supertokens', label: 'SuperTokens', category: 'authentication', iconSlug: 'supertokens', confidence: 'high' },
  { test: (pkg) => /^@auth\/|next-auth|authjs|passport/.test(pkg), id: 'better-auth', label: 'Better Auth', category: 'authentication', iconSlug: null, confidence: 'medium' },
  { test: (pkg) => /^@supabase\/auth-|gotrue/.test(pkg), id: 'supabase', label: 'Supabase', category: 'authentication', iconSlug: 'supabase', confidence: 'medium' },
  { test: (pkg) => /^@supabase\/supabase-js$|supabase-go|supabase/.test(pkg), id: 'supabase', label: 'Supabase', category: 'database', iconSlug: 'supabase', confidence: 'high' },
  { test: (pkg) => /^pg$|postgresql|postgres$/.test(pkg), id: 'postgresql', label: 'PostgreSQL', category: 'database', iconSlug: 'postgresql', confidence: 'high' },
  { test: (pkg) => /prisma/.test(pkg), id: 'prisma', label: 'Prisma', category: 'database', iconSlug: 'prisma', confidence: 'medium' },
  { test: (pkg) => /mongodb|mongoose/.test(pkg), id: 'mongodb', label: 'MongoDB', category: 'database', iconSlug: 'mongodb', confidence: 'high' },
  { test: (pkg) => /^mysql2?$/.test(pkg), id: 'mysql', label: 'MySQL', category: 'database', iconSlug: 'mysql', confidence: 'high' },
  { test: (pkg) => /redis|ioredis/.test(pkg), id: 'redis', label: 'Redis', category: 'database', iconSlug: 'redis', confidence: 'high' },
  { test: (pkg) => /posthog/.test(pkg), id: 'posthog', label: 'PostHog', category: 'analytics', iconSlug: 'posthog', confidence: 'high' },
  { test: (pkg) => /segment/.test(pkg), id: 'segment', label: 'Segment', category: 'analytics', iconSlug: 'segment', confidence: 'high' },
  { test: (pkg) => /amplitude/.test(pkg), id: 'amplitude', label: 'Amplitude', category: 'analytics', iconSlug: 'amplitude', confidence: 'high' },
  { test: (pkg) => /mixpanel/.test(pkg), id: 'mixpanel', label: 'Mixpanel', category: 'analytics', iconSlug: 'mixpanel', confidence: 'high' },
  { test: (pkg) => /stripe/.test(pkg), id: 'stripe', label: 'Stripe', category: 'payments', iconSlug: 'stripe', confidence: 'high' },
  { test: (pkg) => /paypal|braintree/.test(pkg), id: 'paypal', label: 'PayPal', category: 'payments', iconSlug: 'paypal', confidence: 'medium' },
  { test: (pkg) => /tailwind/.test(pkg), id: 'tailwindcss', label: 'Tailwind CSS', category: 'ui', iconSlug: 'tailwindcss', confidence: 'high' },
  { test: (pkg) => /@mui|material-ui/.test(pkg), id: 'material-ui', label: 'Material UI', category: 'ui', iconSlug: 'material-ui', confidence: 'high' },
  { test: (pkg) => /antd|ant-design/.test(pkg), id: 'ant-design', label: 'Ant Design', category: 'ui', iconSlug: 'ant-design', confidence: 'high' },
  { test: (pkg) => /bootstrap/.test(pkg), id: 'bootstrap', label: 'Bootstrap', category: 'ui', iconSlug: 'bootstrap', confidence: 'high' },
  { test: (pkg) => /storybook/.test(pkg), id: 'storybook', label: 'Storybook', category: 'ui', iconSlug: 'storybook', confidence: 'high' },
  { test: (pkg) => /sentry/.test(pkg), id: 'sentry', label: 'Sentry', category: 'observability', iconSlug: 'sentry', confidence: 'high' },
  { test: (pkg) => /datadog/.test(pkg), id: 'datadog', label: 'Datadog', category: 'observability', iconSlug: 'datadog', confidence: 'high' },
  { test: (pkg) => /cloudflare/.test(pkg), id: 'cloudflare', label: 'Cloudflare', category: 'cloud', iconSlug: 'cloudflare', confidence: 'high' },
  { test: (pkg) => /@vercel|vercel/.test(pkg), id: 'vercel', label: 'Vercel', category: 'cloud', iconSlug: 'vercel', confidence: 'high' },
  { test: (pkg) => /netlify/.test(pkg), id: 'netlify', label: 'Netlify', category: 'cloud', iconSlug: 'netlify', confidence: 'high' },
  { test: (pkg) => /^aws|@aws|amazonaws/.test(pkg), id: 'aws', label: 'AWS', category: 'cloud', iconSlug: 'aws', confidence: 'high' },
  { test: (pkg) => /google-cloud|gcloud/.test(pkg), id: 'google-cloud', label: 'Google Cloud', category: 'cloud', iconSlug: 'google-cloud', confidence: 'high' },
  { test: (pkg) => /^openai$|openai-/.test(pkg), id: 'openai', label: 'OpenAI', category: 'ai', iconSlug: 'openai', confidence: 'high' },
  { test: (pkg) => /anthropic/.test(pkg), id: 'anthropic', label: 'Anthropic', category: 'ai', iconSlug: 'anthropic', confidence: 'high' },
  { test: (pkg) => /huggingface|hugging-face/.test(pkg), id: 'hugging-face', label: 'Hugging Face', category: 'ai', iconSlug: 'hugging-face', confidence: 'high' },
];

const RULES = [
  {
    name: 'depends-on-direct',
    head: { predicate: 'depends_on', args: ['?file', '?dep'] },
    body: [{ predicate: 'import_edge', args: ['?file', '?dep'] }],
  },
  {
    name: 'depends-on-transitive',
    head: { predicate: 'depends_on', args: ['?file', '?dep'] },
    body: [
      { predicate: 'import_edge', args: ['?file', '?mid'] },
      { predicate: 'depends_on', args: ['?mid', '?dep'] },
    ],
  },
  {
    name: 'taint-root',
    head: { predicate: 'taint_root', args: ['?vendor', '?file'] },
    body: [{ predicate: 'source_match', args: ['?vendor', '?file', '?line', '?pattern', '?zone', '?excerpt'] }],
  },
  {
    name: 'tainted-direct',
    head: { predicate: 'tainted_file', args: ['?vendor', '?file'] },
    body: [{ predicate: 'taint_root', args: ['?vendor', '?file'] }],
  },
  {
    name: 'tainted-via-dependency',
    head: { predicate: 'tainted_file', args: ['?vendor', '?file'] },
    body: [
      { predicate: 'depends_on', args: ['?file', '?dep'] },
      { predicate: 'tainted_file', args: ['?vendor', '?dep'] },
    ],
  },
  {
    name: 'sink-file',
    head: { predicate: 'sink_file', args: ['?vendor', '?file'] },
    body: [{ predicate: 'sink_match', args: ['?vendor', '?file', '?line', '?pattern', '?zone', '?excerpt'] }],
  },
  {
    name: 'blocked-ui',
    head: { predicate: 'blocked_file', args: ['?vendor', '?file'] },
    body: [
      { predicate: 'tainted_file', args: ['?vendor', '?file'] },
      { predicate: 'zone', args: ['?file', 'ui'] },
    ],
  },
  {
    name: 'candidate-file',
    head: { predicate: 'candidate_file', args: ['?vendor', '?file'] },
    body: [
      { predicate: 'tainted_file', args: ['?vendor', '?file'] },
      { type: 'not', atom: { predicate: 'blocked_file', args: ['?vendor', '?file'] } },
    ],
  },
  {
    name: 'evidence-file-source',
    head: { predicate: 'evidence_file', args: ['?vendor', '?file'] },
    body: [{ predicate: 'source_match', args: ['?vendor', '?file', '?line', '?pattern', '?zone', '?excerpt'] }],
  },
  {
    name: 'evidence-file-sink',
    head: { predicate: 'evidence_file', args: ['?vendor', '?file'] },
    body: [{ predicate: 'sink_match', args: ['?vendor', '?file', '?line', '?pattern', '?zone', '?excerpt'] }],
  },
];

const RULE_INPUT_PREDICATES = new Set([
  'import_edge',
  'source_match',
  'sink_match',
  'zone',
]);

export async function ingestRepository(input, onPhaseDetail) {
  const parsed = parseGitHubRepoInput(input);
  onPhaseDetail?.(`Resolving repo metadata for ${parsed.owner}/${parsed.repo}`);
  const repoMeta = await fetchRepoMeta(parsed.owner, parsed.repo);
  const archive = await loadRepoArchive(parsed.owner, parsed.repo, repoMeta.default_branch, onPhaseDetail);

  onPhaseDetail?.(`Extracting root manifests on ${repoMeta.default_branch}`);
  const manifests = ROOT_MANIFESTS.filter((filePath) => archive.files.has(filePath));
  const modules = dedupeModules(parseManifestModules(manifests.map((path) => ({ path, content: archive.files.get(path) }))));
  const vendorSignals = detectVendorSignals(modules);

  const workspace = await createArtifactWorkspace(
    {
      fullName: repoMeta.full_name,
      defaultBranch: repoMeta.default_branch,
    },
    archive.buffer,
    archive.files,
  );

  const repoRecord = {
    input,
    owner: parsed.owner,
    repo: parsed.repo,
    fullName: repoMeta.full_name,
    description: repoMeta.description ?? '',
    defaultBranch: repoMeta.default_branch,
    language: repoMeta.language ?? null,
    stars: repoMeta.stargazers_count ?? 0,
    forks: repoMeta.forks_count ?? 0,
    openIssues: repoMeta.open_issues_count ?? 0,
    updatedAt: repoMeta.updated_at,
    manifests,
    packageSystems: manifests,
    modules,
    vendorSignals,
    artifact: {
      id: workspace.artifactId,
      dir: workspace.relativeDir,
    },
    ingestPolicy: archive.ignorePolicy.summary,
  };

  const facts = extractFacts({
    repoMeta: repoRecord,
    files: archive.files,
    modules,
    vendorSignals,
  });

  const summary = buildArtifactSummary({
    repoMeta: repoRecord,
    files: archive.files,
    facts,
  });

  await writeArtifactJson(workspace.dir, 'repo.json', repoRecord);
  await writeArtifactJson(workspace.dir, 'facts.json', facts);
  await writeArtifactJson(workspace.dir, 'summary.json', summary);

  return {
    repo: {
      ...repoRecord,
      __artifactDir: workspace.dir,
      __files: archive.files,
      __facts: facts,
    },
    artifact: {
      id: workspace.artifactId,
      dir: workspace.relativeDir,
      factCount: facts.length,
      ingestedFiles: archive.files.size,
    },
  };
}

export async function runLogicLensSymbolica(repoContext, onPhaseDetail) {
  const scopedFacts = selectRuleInputFacts(repoContext.__facts);
  onPhaseDetail?.(`Running local rule engine over ${scopedFacts.length} evidence-scoped facts`);
  const ruleFacts = runRules(scopedFacts, RULES);
  const seedFactKeys = new Set(scopedFacts.map(factKey));
  const derivedFacts = ruleFacts.filter((fact) => !seedFactKeys.has(factKey(fact)));
  const reports = buildTaintReports(repoContext, derivedFacts);

  await writeArtifactJson(repoContext.__artifactDir, 'rules.json', RULES);
  await writeArtifactJson(repoContext.__artifactDir, 'rule-input-facts.json', scopedFacts);
  await writeArtifactJson(repoContext.__artifactDir, 'derived-facts.json', derivedFacts);
  await writeArtifactJson(repoContext.__artifactDir, 'taint-reports.json', reports);

  repoContext.taintReports = reports;
  repoContext.logicRun = {
    ruleCount: RULES.length,
    derivedFactCount: derivedFacts.length,
  };

  return {
    reports,
    scopedFactCount: scopedFacts.length,
    derivedFactCount: derivedFacts.length,
    ruleCount: RULES.length,
  };
}

export function buildSuggestionSet(primary, secondary) {
  if (!primary) return [];

  return primary.vendorSignals.map((signal) => {
    const target = findSuggestedVendor(signal, secondary?.vendorSignals ?? []);
    const taint = primary.taintReports?.find((report) => report.vendorId === signal.id) ?? null;
    return {
      category: signal.category,
      source: signal,
      target,
      reason:
        secondary && secondary.vendorSignals.some((candidate) => candidate.category === signal.category)
          ? `Mapped from ${secondary.fullName}`
          : 'Mapped from curated alternates',
      taint,
    };
  });
}

function buildTaintReports(repoContext, derivedFacts) {
  const byPredicate = groupFactsByPredicate([...repoContext.__facts, ...derivedFacts]);
  const reports = [];

  for (const signal of repoContext.vendorSignals) {
    const sourceMatches = filterMatches(byPredicate.source_match, signal.id);
    const sinkMatches = filterMatches(byPredicate.sink_match, signal.id);
    const taintedFiles = uniqueFacts(filterFacts(byPredicate.tainted_file, signal.id, 1));
    const candidateFiles = uniqueFacts(filterFacts(byPredicate.candidate_file, signal.id, 1));
    const blockedFiles = uniqueFacts(filterFacts(byPredicate.blocked_file, signal.id, 1));
    const evidenceFiles = uniqueFacts(filterFacts(byPredicate.evidence_file, signal.id, 1));
    const evidencePaths = connectEvidencePaths(sourceMatches, sinkMatches, byPredicate.depends_on ?? []);

    if (!sourceMatches.length && !sinkMatches.length && !taintedFiles.length) {
      continue;
    }

    reports.push({
      vendorId: signal.id,
      category: signal.category,
      sourceMatches: sourceMatches.slice(0, 20),
      sinkMatches: sinkMatches.slice(0, 20),
      evidencePaths: evidencePaths.slice(0, 10),
      taintedFiles: taintedFiles.slice(0, 40),
      candidateFiles: candidateFiles.slice(0, 40),
      blockedFiles: blockedFiles.slice(0, 20),
      evidenceFiles: evidenceFiles.slice(0, 20),
      prunedFiles: blockedFiles.slice(0, 20),
      confidence: scoreTaintConfidence(sourceMatches, sinkMatches, evidencePaths),
    });
  }

  return reports;
}

function groupFactsByPredicate(facts) {
  const grouped = {};
  for (const fact of facts) {
    grouped[fact.predicate] ??= [];
    grouped[fact.predicate].push(fact);
  }
  return grouped;
}

function filterMatches(facts = [], vendorId) {
  return facts
    .filter((fact) => fact.args[0] === vendorId)
    .map((fact) => ({
      vendorId: fact.args[0],
      filePath: fact.args[1],
      line: fact.args[2],
      kind: fact.predicate === 'source_match' ? 'source' : 'sink',
      pattern: fact.args[3],
      role: fact.args[4],
      excerpt: fact.args[5],
    }));
}

function filterFacts(facts = [], vendorId, index) {
  return facts.filter((fact) => fact.args[0] === vendorId).map((fact) => fact.args[index]);
}

function uniqueFacts(values) {
  return [...new Set(values)].sort();
}

function factKey(fact) {
  return `${fact.predicate}::${fact.args.map((arg) => JSON.stringify(arg)).join('|')}`;
}

function selectRuleInputFacts(facts) {
  const inputFacts = capEvidenceFacts(facts.filter((fact) => RULE_INPUT_PREDICATES.has(fact.predicate)));
  const sourceFiles = new Set(
    inputFacts
      .filter((fact) => fact.predicate === 'source_match')
      .map((fact) => fact.args[1]),
  );

  if (!sourceFiles.size) {
    return inputFacts.filter((fact) => fact.predicate !== 'import_edge');
  }

  const importFacts = inputFacts.filter((fact) => fact.predicate === 'import_edge');
  const reverseImports = new Map();
  for (const fact of importFacts) {
    const [from, to] = fact.args;
    reverseImports.set(to, [...(reverseImports.get(to) ?? []), { from, fact }]);
  }

  const retainedImportKeys = new Set();
  const queue = [...sourceFiles].map((file) => ({ file, depth: 0 }));
  const seen = new Set(sourceFiles);
  const maxDepth = 3;
  const maxRetainedImports = 750;

  while (queue.length && retainedImportKeys.size < maxRetainedImports) {
    const { file, depth } = queue.shift();
    if (depth >= maxDepth) continue;

    for (const edge of reverseImports.get(file) ?? []) {
      retainedImportKeys.add(factKey(edge.fact));
      if (seen.has(edge.from)) continue;
      seen.add(edge.from);
      queue.push({ file: edge.from, depth: depth + 1 });
      if (retainedImportKeys.size >= maxRetainedImports) break;
    }
  }

  return inputFacts.filter((fact) => fact.predicate !== 'import_edge' || retainedImportKeys.has(factKey(fact)));
}

function capEvidenceFacts(facts) {
  const evidenceLimits = {
    source_match: 750,
    sink_match: 750,
  };
  const counts = {};

  return facts.filter((fact) => {
    const limit = evidenceLimits[fact.predicate];
    if (!limit) return true;
    counts[fact.predicate] = (counts[fact.predicate] ?? 0) + 1;
    return counts[fact.predicate] <= limit;
  });
}

function connectEvidencePaths(sourceMatches, sinkMatches, dependsOnFacts) {
  const importersByDependency = new Map();
  for (const fact of dependsOnFacts) {
    const [from, to] = fact.args;
    importersByDependency.set(to, [...(importersByDependency.get(to) ?? []), from]);
  }

  const sinkSet = new Set(sinkMatches.map((match) => match.filePath));
  const paths = [];

  for (const source of [...new Set(sourceMatches.map((match) => match.filePath))]) {
    const queue = [[source]];
    const seen = new Set([source]);

    while (queue.length) {
      const path = queue.shift();
      const node = path[path.length - 1];
      if (path.length > 6) continue;
      if (path.length > 1 && sinkSet.has(node)) {
        paths.push(path);
        break;
      }

      for (const next of importersByDependency.get(node) ?? []) {
        if (seen.has(next)) continue;
        seen.add(next);
        queue.push([...path, next]);
      }
    }
  }

  return dedupePaths(paths);
}

function dedupePaths(paths) {
  const seen = new Set();
  return paths.filter((path) => {
    const key = path.join('>');
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function scoreTaintConfidence(sourceMatches, sinkMatches, evidencePaths) {
  if (sourceMatches.length && sinkMatches.length && evidencePaths.length) return 'high';
  if (sourceMatches.length && (sinkMatches.length || evidencePaths.length)) return 'medium';
  return 'low';
}

function findSuggestedVendor(signal, secondarySignals) {
  const fromSecondary = secondarySignals.find(
    (candidate) => candidate.category === signal.category && candidate.id !== signal.id,
  );
  if (fromSecondary) return fromSecondary;

  const options = STATIC_ALTERNATES[signal.category];
  const picked = options.find((option) => option !== signal.id) ?? signal.id;
  const library = VENDOR_LIBRARY[picked] ?? {
    label: humanizeSlug(picked),
    iconSlug: picked,
    category: signal.category,
  };

  return {
    id: picked,
    label: library.label,
    category: signal.category,
    packages: [],
    iconSlug: library.iconSlug,
    confidence: 'medium',
  };
}

function detectVendorSignals(modules) {
  const signals = new Map();

  for (const module of modules) {
    const normalized = normalizeName(module.name);
    const rule = VENDOR_RULES.find((candidate) => candidate.test(normalized));
    if (!rule) continue;

    const key = `${rule.category}:${rule.id}`;
    const existing = signals.get(key);
    if (existing) {
      if (!existing.packages.includes(module.name)) {
        existing.packages.push(module.name);
      }
      continue;
    }

    signals.set(key, {
      id: rule.id,
      label: rule.label,
      category: rule.category,
      packages: [module.name],
      iconSlug: rule.iconSlug,
      confidence: rule.confidence,
    });
  }

  return [...signals.values()].sort((left, right) => {
    const categoryDelta = CATEGORY_ORDER.indexOf(left.category) - CATEGORY_ORDER.indexOf(right.category);
    if (categoryDelta !== 0) return categoryDelta;
    return left.label.localeCompare(right.label);
  });
}

function parseManifestModules(manifests) {
  const modules = [];

  for (const manifest of manifests) {
    if (manifest.path === 'package.json') {
      const pkg = JSON.parse(manifest.content);
      addEntries(modules, pkg.dependencies, 'npm');
      addEntries(modules, pkg.devDependencies, 'npm');
    }

    if (manifest.path === 'composer.json') {
      const pkg = JSON.parse(manifest.content);
      addEntries(modules, pkg.require, 'composer');
      addEntries(modules, pkg['require-dev'], 'composer');
    }

    if (manifest.path === 'go.mod') {
      const requireLines = manifest.content.match(/^require\s+.+$/gm) ?? [];
      const blockMatch = manifest.content.match(/require\s*\(([\s\S]*?)\)/m);
      for (const line of requireLines) {
        const match = line.replace(/^require\s+/, '').trim().match(/^([^\s]+)\s+([^\s]+)/);
        if (match) modules.push({ name: match[1], version: match[2], ecosystem: 'go' });
      }
      if (blockMatch) {
        for (const row of blockMatch[1].split('\n')) {
          const trimmed = row.trim();
          if (!trimmed || trimmed.startsWith('//')) continue;
          const match = trimmed.match(/^([^\s]+)\s+([^\s]+)/);
          if (match) modules.push({ name: match[1], version: match[2], ecosystem: 'go' });
        }
      }
    }

    if (manifest.path === 'requirements.txt') {
      for (const line of manifest.content.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;
        const [name, version] = trimmed.split(/==|>=|<=|~=|!=/);
        modules.push({ name: name.trim(), version: version?.trim(), ecosystem: 'python' });
      }
    }

    if (manifest.path === 'pyproject.toml') {
      const dependencyLines = [
        ...extractTomlArray(manifest.content, 'dependencies'),
        ...extractTomlTable(manifest.content, 'tool.poetry.dependencies'),
      ];
      for (const dependency of dependencyLines) {
        const [name, version] = dependency.split(/==|>=|<=|~=|!=|=/);
        if (!name || name === 'python') continue;
        modules.push({
          name: name.trim().replace(/^["']|["']$/g, ''),
          version: version?.trim(),
          ecosystem: 'python',
        });
      }
    }

    if (manifest.path === 'Cargo.toml') {
      const dependencyLines = extractTomlTable(manifest.content, 'dependencies');
      for (const dependency of dependencyLines) {
        const [name, version] = dependency.split('=');
        if (!name) continue;
        modules.push({
          name: name.trim(),
          version: version?.trim().replace(/^["']|["']$/g, ''),
          ecosystem: 'rust',
        });
      }
    }
  }

  return modules;
}

function addEntries(modules, entries, ecosystem) {
  if (!entries) return;
  for (const [name, version] of Object.entries(entries)) {
    modules.push({ name, version, ecosystem });
  }
}

function extractTomlArray(content, key) {
  const match = content.match(new RegExp(`${escapeRegExp(key)}\\s*=\\s*\\[([\\s\\S]*?)\\]`, 'm'));
  if (!match) return [];
  return match[1]
    .split('\n')
    .map((line) => line.trim().replace(/,$/, '').replace(/^["']|["']$/g, ''))
    .filter(Boolean);
}

function extractTomlTable(content, table) {
  const escaped = escapeRegExp(table);
  const match = content.match(new RegExp(`\\[${escaped}\\]([\\s\\S]*?)(\\n\\[|$)`, 'm'));
  if (!match) return [];
  return match[1]
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'));
}

function dedupeModules(modules) {
  const seen = new Map();
  for (const module of modules) {
    const key = `${module.ecosystem}:${normalizeName(module.name)}`;
    if (!seen.has(key)) {
      seen.set(key, module);
    }
  }
  return [...seen.values()];
}

function normalizeName(name) {
  return name.trim().toLowerCase();
}

function humanizeSlug(value) {
  return value
    .split(/[-/]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function parseGitHubRepoInput(input) {
  const trimmed = input.trim();
  const shorthand = /^([\w.-]+)\/([\w.-]+)$/;
  const shorthandMatch = trimmed.match(shorthand);
  if (shorthandMatch) {
    return { owner: shorthandMatch[1], repo: shorthandMatch[2].replace(/\.git$/, '') };
  }

  const normalized = trimmed.startsWith('http') ? trimmed : `https://${trimmed}`;
  const url = new URL(normalized);
  if (url.hostname !== 'github.com') {
    throw new Error('Only public GitHub repositories are supported');
  }
  const parts = url.pathname.split('/').filter(Boolean);
  if (parts.length < 2) {
    throw new Error('Enter a GitHub repo URL like https://github.com/owner/repo');
  }

  return {
    owner: parts[0],
    repo: parts[1].replace(/\.git$/, ''),
  };
}

async function fetchRepoMeta(owner, repo) {
  try {
    return await fetchJson(`https://api.github.com/repos/${owner}/${repo}`);
  } catch (error) {
    return fetchRepoMetaFromHtml(owner, repo);
  }
}

async function fetchRepoMetaFromHtml(owner, repo) {
  const response = await fetch(`https://github.com/${owner}/${repo}`, {
    headers: { 'User-Agent': 'repocity-local-scan-server' },
  });
  if (!response.ok) {
    throw new Error(`GitHub repo page fetch failed: ${response.status}`);
  }

  const html = await response.text();
  const defaultBranch =
    html.match(/"defaultBranch":"([^"]+)"/)?.[1] ??
    html.match(/branch=([^"&]+)"/)?.[1] ??
    'main';
  const description = html.match(/<meta name="description" content="([^"]+)"/i)?.[1] ?? '';

  return {
    full_name: `${owner}/${repo}`,
    description,
    default_branch: defaultBranch,
    language: null,
    stargazers_count: 0,
    forks_count: 0,
    open_issues_count: 0,
    updated_at: new Date().toISOString(),
  };
}

async function fetchJson(url) {
  const response = await fetch(url, {
    headers: {
      Accept: 'application/vnd.github+json',
      'User-Agent': 'repocity-local-scan-server',
    },
  });
  if (!response.ok) {
    throw new Error(`GitHub request failed: ${response.status}`);
  }
  return response.json();
}

async function loadRepoArchive(owner, repo, branch, onPhaseDetail) {
  onPhaseDetail?.(`Downloading ${branch} archive bundle`);
  const response = await fetch(`https://codeload.github.com/${owner}/${repo}/zip/refs/heads/${branch}`, {
    headers: { 'User-Agent': 'repocity-local-scan-server' },
  });
  if (!response.ok) {
    throw new Error(`GitHub archive fetch failed: ${response.status}`);
  }

  const buffer = Buffer.from(await response.arrayBuffer());
  const zip = await JSZip.loadAsync(buffer);
  const entries = Object.values(zip.files).filter((entry) => !entry.dir);
  const entryNames = entries
    .map((entry) => stripArchiveRoot(entry.name))
    .filter(Boolean);
  const gitignoreEntry = entries.find((entry) => stripArchiveRoot(entry.name) === '.gitignore');
  const gitignoreContent = gitignoreEntry ? await gitignoreEntry.async('string') : '';
  const ignorePolicy = createIgnorePolicy({ entryNames, gitignoreContent });
  const files = new Map();

  onPhaseDetail?.(
    `Applying ignore policy for ${ignorePolicy.summary.projectKinds.join(', ') || 'generic'} repositories`,
  );

  for (const entry of entries) {
    const normalizedPath = stripArchiveRoot(entry.name);
    if (!normalizedPath) continue;
    if (!shouldRetainArchivePath(normalizedPath, ignorePolicy)) continue;

    try {
      const content = await entry.async('string');
      files.set(normalizedPath, content);
    } catch (error) {
      continue;
    }
  }

  return { buffer, files, ignorePolicy };
}

function stripArchiveRoot(value) {
  const parts = value.split('/').filter(Boolean);
  if (parts.length <= 1) return '';
  return parts.slice(1).join('/');
}

import JSZip from 'jszip';

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
  { test: (pkg) => /better-auth/.test(pkg), id: 'better-auth', label: 'Better Auth', category: 'authentication', iconSlug: null },
  { test: (pkg) => /auth0/.test(pkg), id: 'auth0', label: 'Auth0', category: 'authentication' },
  { test: (pkg) => /(^|\/)clerk|@clerk/.test(pkg), id: 'clerk', label: 'Clerk', category: 'authentication', iconSlug: null },
  { test: (pkg) => /okta/.test(pkg), id: 'okta', label: 'Okta', category: 'authentication' },
  { test: (pkg) => /stytch/.test(pkg), id: 'stytch', label: 'Stytch', category: 'authentication' },
  { test: (pkg) => /supertokens/.test(pkg), id: 'supertokens', label: 'SuperTokens', category: 'authentication' },
  { test: (pkg) => /^@auth\/|next-auth|authjs|passport/.test(pkg), id: 'better-auth', label: 'Better Auth', category: 'authentication', iconSlug: null, confidence: 'medium' },
  { test: (pkg) => /^@supabase\/auth-|gotrue/.test(pkg), id: 'supabase', label: 'Supabase', category: 'authentication', confidence: 'medium' },
  { test: (pkg) => /^@supabase\/supabase-js$|supabase-go|supabase/.test(pkg), id: 'supabase', label: 'Supabase', category: 'database' },
  { test: (pkg) => /^pg$|postgresql|postgres$/.test(pkg), id: 'postgresql', label: 'PostgreSQL', category: 'database' },
  { test: (pkg) => /prisma/.test(pkg), id: 'prisma', label: 'Prisma', category: 'database', confidence: 'medium' },
  { test: (pkg) => /mongodb|mongoose/.test(pkg), id: 'mongodb', label: 'MongoDB', category: 'database' },
  { test: (pkg) => /^mysql2?$/.test(pkg), id: 'mysql', label: 'MySQL', category: 'database' },
  { test: (pkg) => /redis|ioredis/.test(pkg), id: 'redis', label: 'Redis', category: 'database' },
  { test: (pkg) => /posthog/.test(pkg), id: 'posthog', label: 'PostHog', category: 'analytics' },
  { test: (pkg) => /segment/.test(pkg), id: 'segment', label: 'Segment', category: 'analytics' },
  { test: (pkg) => /amplitude/.test(pkg), id: 'amplitude', label: 'Amplitude', category: 'analytics' },
  { test: (pkg) => /mixpanel/.test(pkg), id: 'mixpanel', label: 'Mixpanel', category: 'analytics' },
  { test: (pkg) => /stripe/.test(pkg), id: 'stripe', label: 'Stripe', category: 'payments' },
  { test: (pkg) => /paypal|braintree/.test(pkg), id: 'paypal', label: 'PayPal', category: 'payments', confidence: 'medium' },
  { test: (pkg) => /tailwind/.test(pkg), id: 'tailwindcss', label: 'Tailwind CSS', category: 'ui' },
  { test: (pkg) => /@mui|material-ui/.test(pkg), id: 'material-ui', label: 'Material UI', category: 'ui' },
  { test: (pkg) => /antd|ant-design/.test(pkg), id: 'ant-design', label: 'Ant Design', category: 'ui' },
  { test: (pkg) => /bootstrap/.test(pkg), id: 'bootstrap', label: 'Bootstrap', category: 'ui' },
  { test: (pkg) => /storybook/.test(pkg), id: 'storybook', label: 'Storybook', category: 'ui' },
  { test: (pkg) => /sentry/.test(pkg), id: 'sentry', label: 'Sentry', category: 'observability' },
  { test: (pkg) => /datadog/.test(pkg), id: 'datadog', label: 'Datadog', category: 'observability' },
  { test: (pkg) => /cloudflare/.test(pkg), id: 'cloudflare', label: 'Cloudflare', category: 'cloud' },
  { test: (pkg) => /@vercel|vercel/.test(pkg), id: 'vercel', label: 'Vercel', category: 'cloud' },
  { test: (pkg) => /netlify/.test(pkg), id: 'netlify', label: 'Netlify', category: 'cloud' },
  { test: (pkg) => /^aws|@aws|amazonaws/.test(pkg), id: 'aws', label: 'AWS', category: 'cloud' },
  { test: (pkg) => /google-cloud|gcloud/.test(pkg), id: 'google-cloud', label: 'Google Cloud', category: 'cloud' },
  { test: (pkg) => /^openai$|openai-/.test(pkg), id: 'openai', label: 'OpenAI', category: 'ai' },
  { test: (pkg) => /anthropic/.test(pkg), id: 'anthropic', label: 'Anthropic', category: 'ai' },
  { test: (pkg) => /huggingface|hugging-face/.test(pkg), id: 'hugging-face', label: 'Hugging Face', category: 'ai' },
];

const ROOT_MANIFESTS = [
  'package.json',
  'go.mod',
  'pyproject.toml',
  'requirements.txt',
  'Cargo.toml',
  'composer.json',
];

export async function scanRepoIntel(input, onPhaseDetail) {
  const parsed = parseGitHubRepoInput(input);
  onPhaseDetail?.(`Fetching repo metadata for ${parsed.owner}/${parsed.repo}`);
  const repoMeta = await fetchRepoMeta(parsed.owner, parsed.repo);
  const branch = repoMeta.default_branch;
  const archive = await loadRepoArchive(parsed.owner, parsed.repo, branch, onPhaseDetail);

  onPhaseDetail?.(`Inspecting root manifests on ${branch}`);
  const manifests = [];
  for (const filePath of ROOT_MANIFESTS) {
    const content = archive.files.get(filePath) ?? null;
    if (content) manifests.push({ path: filePath, content });
  }

  const modules = dedupeModules(parseManifestModules(manifests));
  const vendorSignals = detectVendorSignals(modules);

  return {
    input,
    owner: parsed.owner,
    repo: parsed.repo,
    fullName: repoMeta.full_name,
    description: repoMeta.description ?? '',
    defaultBranch: branch,
    language: repoMeta.language ?? null,
    stars: repoMeta.stargazers_count ?? 0,
    forks: repoMeta.forks_count ?? 0,
    openIssues: repoMeta.open_issues_count ?? 0,
    updatedAt: repoMeta.updated_at,
    manifests: manifests.map((manifest) => manifest.path),
    packageSystems: manifests.map((manifest) => manifest.path),
    modules,
    vendorSignals,
    __archive: archive,
  };
}

export async function analyzeRepoTaint(repoIntel, onPhaseDetail) {
  const files = await fetchCandidateFiles(repoIntel, onPhaseDetail);
  const importGraph = buildImportGraph(files);
  const reports = [];

  for (const signal of repoIntel.vendorSignals) {
    const patterns = patternsForSignal(signal);
    const sourceMatches = [];
    const sinkMatches = [];
    const prunedFiles = [];

    for (const file of files) {
      const role = classifyFileRole(file.path);
      if (isPrunedRole(role)) {
        if (matchesAny(file.content, patterns.sources) || matchesAny(file.content, patterns.sinks)) {
          prunedFiles.push(file.path);
        }
        continue;
      }

      sourceMatches.push(...findMatches(file, patterns.sources, 'source', role));
      sinkMatches.push(...findMatches(file, patterns.sinks, 'sink', role));
    }

    const evidencePaths = connectEvidencePaths(
      [...new Set(sourceMatches.map((match) => match.filePath))],
      [...new Set(sinkMatches.map((match) => match.filePath))],
      importGraph,
    );

    const taintedFiles = [...new Set([
      ...sourceMatches.map((match) => match.filePath),
      ...sinkMatches.map((match) => match.filePath),
      ...evidencePaths.flat(),
    ])].sort();

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
      prunedFiles: [...new Set(prunedFiles)].sort().slice(0, 20),
      confidence: scoreTaintConfidence(sourceMatches, sinkMatches, evidencePaths),
    });
  }

  return reports;
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

export function parseGitHubRepoInput(input) {
  const trimmed = input.trim();
  const shorthand = /^([\w.-]+)\/([\w.-]+)$/;
  const shorthandMatch = trimmed.match(shorthand);
  if (shorthandMatch) {
    return { owner: shorthandMatch[1], repo: shorthandMatch[2].replace(/\.git$/, '') };
  }

  const normalized = trimmed.startsWith('http') ? trimmed : `https://${trimmed}`;
  const url = new URL(normalized);
  const parts = url.pathname.split('/').filter(Boolean);
  if (parts.length < 2) {
    throw new Error('Enter a GitHub repo URL like https://github.com/owner/repo');
  }

  return {
    owner: parts[0],
    repo: parts[1].replace(/\.git$/, ''),
  };
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
      iconSlug: rule.iconSlug === undefined ? rule.id : rule.iconSlug,
      confidence: rule.confidence ?? 'high',
    });
  }

  return [...signals.values()].sort((left, right) => {
    const categoryDelta =
      CATEGORY_ORDER.indexOf(left.category) - CATEGORY_ORDER.indexOf(right.category);
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

function matchesAny(content, patterns) {
  return patterns.some((pattern) => pattern.regex.test(content));
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

async function fetchCandidateFiles(repoIntel, onPhaseDetail) {
  const archive =
    repoIntel.__archive ??
    (await loadRepoArchive(repoIntel.owner, repoIntel.repo, repoIntel.defaultBranch, onPhaseDetail));

  onPhaseDetail?.(`Walking archive contents on ${repoIntel.defaultBranch}`);
  const candidates = [...archive.files.keys()]
    .filter((filePath) => isAllowedCodePath(filePath))
    .slice(0, 90);

  onPhaseDetail?.(`Pulling ${candidates.length} code candidates for taint pass`);

  return candidates
    .map((filePath) => {
      const content = archive.files.get(filePath) ?? null;
      return typeof content === 'string' ? { path: filePath, content } : null;
    })
    .filter(Boolean);
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
  const files = new Map();

  for (const entry of Object.values(zip.files)) {
    if (entry.dir) continue;
    const normalizedPath = stripArchiveRoot(entry.name);
    if (!normalizedPath) continue;
    if (!isInterestingArchivePath(normalizedPath)) continue;

    try {
      const content = await entry.async('string');
      files.set(normalizedPath, content);
    } catch (error) {
      continue;
    }
  }

  return { branch, files };
}

function stripArchiveRoot(value) {
  const parts = value.split('/').filter(Boolean);
  if (parts.length <= 1) return '';
  return parts.slice(1).join('/');
}

function isInterestingArchivePath(filePath) {
  return isAllowedCodePath(filePath) || ROOT_MANIFESTS.includes(filePath);
}

function isAllowedCodePath(filePath) {
  if (!/\.(ts|tsx|js|jsx|mjs|cjs|go|py|rs|php|rb|java|kt|swift)$/i.test(filePath)) {
    return false;
  }
  if (/^node_modules\//.test(filePath)) return false;
  if (/(^|\/)(dist|build|coverage|vendor|public|docs)\//i.test(filePath)) return false;
  if (/(^|\/)(test|tests|spec|__tests__|fixtures)\//i.test(filePath)) return false;
  return true;
}

function classifyFileRole(filePath) {
  const normalized = filePath.toLowerCase();
  if (/(^|\/)(components|ui|views|pages)\//.test(normalized)) return 'ui';
  if (/(^|\/)(routes|api|controllers)\//.test(normalized)) return 'route';
  if (/(^|\/)(middleware|guards)\//.test(normalized)) return 'middleware';
  if (/(^|\/)(db|database|models|prisma|schema)\//.test(normalized)) return 'data';
  if (/(^|\/)(auth|identity|session)\//.test(normalized)) return 'auth';
  if (/(^|\/)(test|tests|spec|__tests__)\//.test(normalized)) return 'test';
  return 'logic';
}

function isPrunedRole(role) {
  return role === 'ui' || role === 'test';
}

function patternsForSignal(signal) {
  const vendorNames = [...new Set([signal.id, ...signal.packages])].filter(Boolean);
  const sources = vendorNames.map((name) => ({
    label: name,
    regex: new RegExp(escapeRegExp(name.replace(/^@/, '')), 'i'),
  }));

  const sinkTokensByCategory = {
    authentication: ['session', 'cookie', 'token', 'jwt', 'login', 'signup', 'authorize', 'setcookie', 'redirect'],
    database: ['insert', 'update', 'save', 'upsert', 'query', 'from(', 'select', 'rpc', 'database', 'db.'],
    analytics: ['track', 'capture', 'identify', 'page', 'event'],
    payments: ['checkout', 'payment', 'invoice', 'billing', 'subscription'],
    ui: ['render', 'component', 'view'],
    observability: ['captureException', 'logger', 'trace', 'span', 'report'],
    cloud: ['deploy', 'edge', 'worker', 'function', 'storage'],
    ai: ['completion', 'embedding', 'chat', 'generate', 'inference'],
  };

  const sinks = (sinkTokensByCategory[signal.category] ?? ['handler']).map((token) => ({
    label: token,
    regex: new RegExp(escapeRegExp(token), 'i'),
  }));

  return { sources, sinks };
}

function findMatches(file, patterns, kind, role) {
  const lines = file.content.split('\n');
  const matches = [];

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    if (/^(\/\/|\*|\*\/|\/\*|#)/.test(trimmed)) return;

    for (const pattern of patterns) {
      if (pattern.regex.test(trimmed)) {
        matches.push({
          filePath: file.path,
          line: index + 1,
          kind,
          excerpt: trimmed.slice(0, 180),
          pattern: pattern.label,
          role,
        });
        break;
      }
    }
  });

  return matches;
}

function buildImportGraph(files) {
  const pathSet = new Set(files.map((file) => file.path));
  const adjacency = new Map(files.map((file) => [file.path, []]));

  for (const file of files) {
    const imports = extractImports(file.content);
    for (const specifier of imports) {
      const resolved = resolveImport(file.path, specifier, pathSet);
      if (resolved) {
        adjacency.get(file.path).push(resolved);
        if (!adjacency.has(resolved)) adjacency.set(resolved, []);
        adjacency.get(resolved).push(file.path);
      }
    }
  }

  return adjacency;
}

function extractImports(content) {
  const results = [];
  const patterns = [
    /import\s+(?:.+?\s+from\s+)?['"]([^'"]+)['"]/g,
    /require\(\s*['"]([^'"]+)['"]\s*\)/g,
    /from\s+['"]([^'"]+)['"]/g,
  ];

  for (const pattern of patterns) {
    for (const match of content.matchAll(pattern)) {
      results.push(match[1]);
    }
  }

  return results.filter((value) => value.startsWith('.'));
}

function resolveImport(fromPath, specifier, pathSet) {
  const base = fromPath.split('/').slice(0, -1).join('/');
  const raw = normalizeRepoPath(joinRepoPath(base, specifier));
  const candidates = [
    raw,
    `${raw}.ts`,
    `${raw}.tsx`,
    `${raw}.js`,
    `${raw}.jsx`,
    `${raw}.mjs`,
    `${raw}.cjs`,
    `${raw}/index.ts`,
    `${raw}/index.tsx`,
    `${raw}/index.js`,
    `${raw}/index.jsx`,
  ];
  return candidates.find((candidate) => pathSet.has(candidate)) ?? null;
}

function joinRepoPath(base, relative) {
  return `${base}/${relative}`;
}

function normalizeRepoPath(value) {
  const segments = [];
  for (const part of value.split('/')) {
    if (!part || part === '.') continue;
    if (part === '..') {
      segments.pop();
      continue;
    }
    segments.push(part);
  }
  return segments.join('/');
}

function connectEvidencePaths(sourceFiles, sinkFiles, graph) {
  const sinkSet = new Set(sinkFiles);
  const paths = [];

  for (const source of sourceFiles) {
    const queue = [[source]];
    const seen = new Set([source]);

    while (queue.length) {
      const path = queue.shift();
      const node = path[path.length - 1];
      if (path.length > 5) continue;
      if (path.length > 1 && sinkSet.has(node)) {
        paths.push(path);
        break;
      }

      for (const next of graph.get(node) ?? []) {
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
  const unique = [];
  for (const path of paths) {
    const key = path.join('>');
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(path);
  }
  return unique;
}

function scoreTaintConfidence(sourceMatches, sinkMatches, evidencePaths) {
  if (sourceMatches.length && sinkMatches.length && evidencePaths.length) return 'high';
  if (sourceMatches.length && (sinkMatches.length || evidencePaths.length)) return 'medium';
  return 'low';
}

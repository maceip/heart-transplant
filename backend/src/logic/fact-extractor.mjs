const ROOT_MANIFESTS = [
  'package.json',
  'go.mod',
  'pyproject.toml',
  'requirements.txt',
  'Cargo.toml',
  'composer.json',
];

const SYMBOL_PATTERNS = {
  javascript: [
    { kind: 'function', regex: /\bfunction\s+([A-Za-z_$][\w$]*)/g },
    { kind: 'function', regex: /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(/g },
    { kind: 'class', regex: /\bclass\s+([A-Za-z_$][\w$]*)/g },
  ],
  python: [
    { kind: 'function', regex: /^\s*def\s+([A-Za-z_]\w*)/gm },
    { kind: 'class', regex: /^\s*class\s+([A-Za-z_]\w*)/gm },
  ],
  go: [
    { kind: 'function', regex: /^\s*func\s+(?:\([^)]+\)\s*)?([A-Za-z_]\w*)/gm },
    { kind: 'type', regex: /^\s*type\s+([A-Za-z_]\w*)\s+/gm },
  ],
  rust: [
    { kind: 'function', regex: /\bfn\s+([A-Za-z_]\w*)/g },
    { kind: 'struct', regex: /\bstruct\s+([A-Za-z_]\w*)/g },
    { kind: 'enum', regex: /\benum\s+([A-Za-z_]\w*)/g },
  ],
};

const KEYWORDS = new Set([
  'const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 'switch', 'case',
  'break', 'continue', 'class', 'import', 'export', 'default', 'from', 'new', 'await', 'async',
  'true', 'false', 'null', 'undefined', 'try', 'catch', 'finally', 'throw', 'def', 'class',
  'pass', 'raise', 'func', 'package', 'type', 'struct', 'enum', 'impl', 'match', 'pub', 'use',
]);

const MAX_IDENTIFIER_USE_FACTS = 20000;
const MAX_IDENTIFIER_USES_PER_FILE = 200;

export function extractFacts({ repoMeta, files, modules, vendorSignals }) {
  const facts = [];
  let identifierUseFactCount = 0;

  fact(facts, 'repo', [repoMeta.fullName, repoMeta.defaultBranch]);

  for (const manifest of ROOT_MANIFESTS) {
    if (files.has(manifest)) {
      fact(facts, 'manifest_file', [manifest]);
    }
  }

  for (const module of modules) {
    fact(facts, 'module_dep', [module.name, module.ecosystem, module.version ?? '']);
  }

  for (const signal of vendorSignals) {
    fact(facts, 'vendor_signal', [signal.id, signal.category, signal.label, signal.confidence]);
    for (const pkg of signal.packages) {
      fact(facts, 'vendor_package', [signal.id, pkg]);
    }
  }

  for (const [filePath, content] of files.entries()) {
    const language = detectLanguage(filePath);
    const zone = classifyZone(filePath);
    const metadataOnly = ROOT_MANIFESTS.includes(filePath) || filePath === '.gitignore';
    fact(facts, 'file', [filePath]);
    fact(facts, 'file_language', [filePath, language]);
    fact(facts, 'zone', [filePath, zone]);
    fact(facts, 'file_line_count', [filePath, content.split('\n').length]);

    if (metadataOnly) {
      continue;
    }

    const imports = extractImports(filePath, content, files);
    for (const edge of imports.internal) {
      fact(facts, 'import_edge', [filePath, edge]);
      fact(facts, 'uses_file', [filePath, edge]);
    }
    for (const dep of imports.external) {
      fact(facts, 'external_import', [filePath, dep]);
    }

    for (const symbol of extractSymbols(filePath, content, language)) {
      fact(facts, 'symbol_decl', [symbol.id, filePath, symbol.name, symbol.kind, symbol.line]);
    }

    for (const usage of extractIdentifierUses(filePath, content).slice(0, MAX_IDENTIFIER_USES_PER_FILE)) {
      if (identifierUseFactCount >= MAX_IDENTIFIER_USE_FACTS) {
        break;
      }
      fact(facts, 'identifier_use', [filePath, usage.name, usage.line]);
      identifierUseFactCount += 1;
    }

    for (const signal of vendorSignals) {
      const patterns = vendorPatterns(signal);
      for (const match of findMatches(filePath, content, patterns.sources, 'source')) {
        fact(facts, 'source_match', [
          signal.id,
          match.filePath,
          match.line,
          match.pattern,
          zone,
          match.excerpt,
        ]);
      }
      for (const match of findMatches(filePath, content, patterns.sinks, 'sink')) {
        fact(facts, 'sink_match', [
          signal.id,
          match.filePath,
          match.line,
          match.pattern,
          zone,
          match.excerpt,
        ]);
      }
    }
  }

  return facts;
}

export function buildArtifactSummary({ repoMeta, files, facts }) {
  const predicateCounts = {};
  for (const fact of facts) {
    predicateCounts[fact.predicate] = (predicateCounts[fact.predicate] ?? 0) + 1;
  }

  return {
    repo: repoMeta.fullName,
    branch: repoMeta.defaultBranch,
    ingestedFiles: files.size,
    factCount: facts.length,
    predicateCounts,
    generatedAt: new Date().toISOString(),
  };
}

function fact(target, predicate, args) {
  target.push({ predicate, args });
}

function detectLanguage(filePath) {
  if (/\.(ts|tsx|js|jsx|mjs|cjs)$/i.test(filePath)) return 'javascript';
  if (/\.py$/i.test(filePath)) return 'python';
  if (/\.go$/i.test(filePath)) return 'go';
  if (/\.rs$/i.test(filePath)) return 'rust';
  return 'text';
}

function classifyZone(filePath) {
  const normalized = filePath.toLowerCase();
  if (/(^|\/)(components|ui|views|pages)\//.test(normalized)) return 'ui';
  if (/(^|\/)(routes|api|controllers)\//.test(normalized)) return 'route';
  if (/(^|\/)(middleware|guards)\//.test(normalized)) return 'middleware';
  if (/(^|\/)(db|database|models|schema|migrations|prisma)\//.test(normalized)) return 'data';
  if (/(^|\/)(auth|identity|session)\//.test(normalized)) return 'auth';
  if (/(^|\/)(test|tests|spec|__tests__)\//.test(normalized)) return 'test';
  return 'logic';
}

function extractImports(filePath, content, files) {
  const internal = [];
  const external = [];
  const patterns = [
    /import\s+(?:.+?\s+from\s+)?['"]([^'"]+)['"]/g,
    /require\(\s*['"]([^'"]+)['"]\s*\)/g,
    /from\s+['"]([^'"]+)['"]/g,
  ];

  for (const pattern of patterns) {
    for (const match of content.matchAll(pattern)) {
      const specifier = match[1];
      if (specifier.startsWith('.')) {
        const resolved = resolveImport(filePath, specifier, files);
        if (resolved) internal.push(resolved);
      } else {
        external.push(specifier);
      }
    }
  }

  return {
    internal: [...new Set(internal)],
    external: [...new Set(external)],
  };
}

function resolveImport(fromPath, specifier, files) {
  const base = fromPath.split('/').slice(0, -1).join('/');
  const raw = normalizeRepoPath(`${base}/${specifier}`);
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
  return candidates.find((candidate) => files.has(candidate)) ?? null;
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

function extractSymbols(filePath, content, language) {
  const patterns = SYMBOL_PATTERNS[language] ?? [];
  const symbols = [];

  for (const pattern of patterns) {
    for (const match of content.matchAll(pattern.regex)) {
      const index = match.index ?? 0;
      const line = content.slice(0, index).split('\n').length;
      const name = match[1];
      symbols.push({
        id: `${filePath}::${name}::${pattern.kind}::${line}`,
        filePath,
        name,
        kind: pattern.kind,
        line,
      });
    }
  }

  return symbols;
}

function extractIdentifierUses(filePath, content) {
  const uses = [];
  const lines = content.split('\n');
  lines.forEach((line, index) => {
    const trimmed = line.trim();
    if (!trimmed || /^(\/\/|\*|\*\/|\/\*|#)/.test(trimmed)) return;
    const identifiers = trimmed.match(/[A-Za-z_$][\w$]*/g) ?? [];
    for (const name of identifiers) {
      if (KEYWORDS.has(name)) continue;
      uses.push({ filePath, name, line: index + 1 });
    }
  });
  return uses;
}

function vendorPatterns(signal) {
  const vendorNames = [...new Set([signal.id, ...signal.packages])].filter(Boolean);
  const sources = vendorNames.map((name) => ({
    label: name,
    regex: new RegExp(escapeRegExp(name.replace(/^@/, '')), 'i'),
  }));

  const sinkTokens = {
    authentication: ['session', 'cookie', 'token', 'jwt', 'login', 'signup', 'authorize', 'redirect'],
    database: ['insert', 'update', 'save', 'upsert', 'query', 'select', 'rpc', 'database', 'db.'],
    analytics: ['track', 'capture', 'identify', 'page', 'event'],
    payments: ['checkout', 'payment', 'invoice', 'billing', 'subscription'],
    ui: ['render', 'component', 'view'],
    observability: ['captureException', 'logger', 'trace', 'span', 'report'],
    cloud: ['deploy', 'edge', 'worker', 'function', 'storage'],
    ai: ['completion', 'embedding', 'chat', 'generate', 'inference'],
  };

  const sinks = (sinkTokens[signal.category] ?? ['handler']).map((token) => ({
    label: token,
    regex: new RegExp(escapeRegExp(token), 'i'),
  }));

  return { sources, sinks };
}

function findMatches(filePath, content, patterns, kind) {
  const lines = content.split('\n');
  const matches = [];

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    if (!trimmed || /^(\/\/|\*|\*\/|\/\*|#)/.test(trimmed)) return;

    for (const pattern of patterns) {
      if (pattern.regex.test(trimmed)) {
        matches.push({
          filePath,
          line: index + 1,
          kind,
          pattern: pattern.label,
          excerpt: trimmed.slice(0, 180),
        });
        break;
      }
    }
  });

  return matches;
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

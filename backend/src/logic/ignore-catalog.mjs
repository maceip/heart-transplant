const ROOT_METADATA_FILES = new Set([
  'package.json',
  'go.mod',
  'pyproject.toml',
  'requirements.txt',
  'Cargo.toml',
  'composer.json',
  '.gitignore',
]);

const CODE_PATH_PATTERN = /\.(ts|tsx|js|jsx|mjs|cjs|go|py|rs|php|rb|java|kt|swift)$/i;

export const NODEJS_IGNORE_PATTERNS = [
  'node_modules/',
  '.pnpm-store/',
  '.npm/',
  '.yarn/',
  '.yarn/cache/',
  '.yarn/unplugged/',
  '.yarn/build-state.yml',
  '.yarn/install-state.gz',
  '.parcel-cache/',
  '.next/',
  '.nuxt/',
  '.svelte-kit/',
  '.turbo/',
  '.cache/',
  '.eslintcache',
  'dist/',
  'build/',
  'coverage/',
  '.nyc_output/',
  '.rpt2_cache/',
  '.rts2_cache_cjs/',
  '.rts2_cache_es/',
  '.rts2_cache_umd/',
  '.storybook-out/',
  'storybook-static/',
  'out/',
  'release/',
  'tmp/',
  'temp/',
  '.tmp/',
  '.temp/',
  'logs/',
  '*.log',
  'pids/',
  '*.pid',
  '*.seed',
  '*.pid.lock',
  'lib-cov/',
  'jspm_packages/',
  'web_modules/',
  'bower_components/',
  '.grunt/',
  '.sass-cache/',
  '.fusebox/',
  '.dynamodb/',
  '.serverless/',
  '.aws-sam/',
  '.vercel/',
  '.netlify/',
  '.firebase/',
  '.expo/',
  '.expo-shared/',
  '.angular/',
  '.nx/cache/',
  '.vite/',
  '.vitest/',
  '.rollup.cache/',
  '.swc/',
  '.tsbuildinfo',
  '*.tsbuildinfo',
  '.DS_Store',
  'Thumbs.db',
  '.idea/',
  '.vscode/',
  '.history/',
  '.env',
  '.env.local',
  '.env.development.local',
  '.env.test.local',
  '.env.production.local',
  '.env.*',
  '*.local',
  '.pnp.*',
  '.pnp.js',
  '.pnpmfile.cjs',
  '.npmrc',
  '.yarnrc',
  '.yarnrc.yml',
  '.node_repl_history',
  'npm-packages-offline-cache/',
  '.stylelintcache',
  '.cache-loader/',
  '.jest/',
  'junit.xml',
  'playwright-report/',
  'test-results/',
  '.playwright/',
  'cypress/videos/',
  'cypress/screenshots/',
  '.webpack-cache/',
  '.meteor/',
  '.node-gyp/',
  '.yalc/',
  '.yalc.lock',
  '.wireit/',
  '.rush/temp/',
  'commitlint.config.js',
  'eslint.config.js',
  'vite.config.js',
  'vite.config.ts',
  'webpack.config.js',
  'rollup.config.js',
  'jest.config.js',
];

export const PYTHON_IGNORE_PATTERNS = [
  '__pycache__/',
  '*.py[cod]',
  '*.pyo',
  '*.pyd',
  '*$py.class',
  '.Python',
  'build/',
  'dist/',
  'develop-eggs/',
  'downloads/',
  'eggs/',
  '.eggs/',
  'lib/',
  'lib64/',
  'parts/',
  'sdist/',
  'var/',
  'wheels/',
  'share/python-wheels/',
  '*.egg-info/',
  '.installed.cfg',
  '*.egg',
  'MANIFEST',
  'pip-wheel-metadata/',
  'htmlcov/',
  '.tox/',
  '.nox/',
  '.coverage',
  '.coverage.*',
  '.cache/',
  'nosetests.xml',
  'coverage.xml',
  '*.cover',
  '*.py,cover',
  '.hypothesis/',
  '.pytest_cache/',
  'cover/',
  '.mypy_cache/',
  '.dmypy.json',
  'dmypy.json',
  '.pyre/',
  '.pytype/',
  '.ruff_cache/',
  '.benchmarks/',
  '.ipynb_checkpoints/',
  'profile_default/',
  'ipython_config.py',
  '.venv/',
  'venv/',
  'env/',
  'ENV/',
  'env.bak/',
  'venv.bak/',
  '.env',
  '.env.*',
  '*.local',
  '.python-version',
  '.pdm.toml',
  '.pdm-python',
  '.pdm-build/',
  '__pypackages__/',
  'celerybeat-schedule',
  'celerybeat.pid',
  '*.sage.py',
  '.spyderproject',
  '.spyproject',
  '.ropeproject/',
  'site/',
  '.maturin/',
  'target/',
  '.scrapy/',
  'docs/_build/',
  '.jupyter/',
  'instance/',
  '.webassets-cache',
  'db.sqlite3',
  'db.sqlite3-journal',
  'local_settings.py',
  '*.mo',
  '*.pot',
  '*.manifest',
  '*.spec',
  'pip-log.txt',
  'pip-delete-this-directory.txt',
  'poetry.toml',
  'poetry.lock',
  'Pipfile.lock',
  '.venv*/',
  '.uv/',
  '.pixi/',
  '.marimo/',
  '.streamlit/secrets.toml',
  '.dvc/',
  '.mlruns/',
  'wandb/',
  'mlartifacts/',
  '.kedro/',
  '.dagster/',
  'airflow-webserver.pid',
  'gunicorn.pid',
];

export const TYPESCRIPT_IGNORE_PATTERNS = [
  'node_modules/',
  'dist/',
  'build/',
  'coverage/',
  '.turbo/',
  '.next/',
  '.nuxt/',
  '.svelte-kit/',
  '.angular/',
  '.vite/',
  '.vitest/',
  '.rollup.cache/',
  '.swc/',
  '.tsbuildinfo',
  '*.tsbuildinfo',
  '*.d.ts.map',
  '*.js.map',
  '*.mjs.map',
  '*.cjs.map',
  '*.generated.ts',
  '*.generated.tsx',
  '*.gen.ts',
  '*.gen.tsx',
  '*.mock.ts',
  '*.mock.tsx',
  '*.stories.ts',
  '*.stories.tsx',
  '*.story.ts',
  '*.story.tsx',
  '*.spec.ts',
  '*.spec.tsx',
  '*.test.ts',
  '*.test.tsx',
  '*.bench.ts',
  '*.bench.tsx',
  '*.snap',
  'tsconfig.tsbuildinfo',
  'api-extractor.json',
  'typedoc.json',
  'tsup.config.ts',
  'tsup.config.mts',
  'tsdown.config.ts',
  'tsdown.config.mts',
  'vite.config.ts',
  'vite.config.mts',
  'vitest.config.ts',
  'vitest.config.mts',
  'jest.config.ts',
  'jest.config.mts',
  'playwright.config.ts',
  'cypress.config.ts',
  'rollup.config.ts',
  'rollup.config.mts',
  'webpack.config.ts',
  'webpack.config.mts',
  'esbuild.config.ts',
  'esbuild.config.mts',
  'babel.config.ts',
  'postcss.config.ts',
  'tailwind.config.ts',
  'storybook-static/',
  '.storybook/',
  'playwright-report/',
  'test-results/',
  '.playwright/',
  'cypress/videos/',
  'cypress/screenshots/',
  'docs/',
  'examples/',
  'fixtures/',
  '__fixtures__/',
  '__mocks__/',
  'mockData/',
  'generated/',
  'codegen/',
  'openapi/',
  'graphql/generated/',
  'prisma/generated/',
  '.yalc/',
  '.yalc.lock',
  '.rush/temp/',
  '.cache/',
  '.eslintcache',
  '.prettier-cache/',
  '.parcel-cache/',
  'tmp/',
  'temp/',
  '.tmp/',
  '.temp/',
  '.history/',
  '.idea/',
  '.vscode/',
  '.DS_Store',
  'Thumbs.db',
  'commitlint.config.ts',
  'eslint.config.ts',
  'prettier.config.ts',
  'tsconfig.node.json',
  'tsconfig.app.json',
  'tsconfig.build.json',
];

const PROJECT_IGNORE_CATALOGS = {
  nodejs: NODEJS_IGNORE_PATTERNS,
  python: PYTHON_IGNORE_PATTERNS,
  typescript: TYPESCRIPT_IGNORE_PATTERNS,
};

export function createIgnorePolicy({ entryNames, gitignoreContent = '' }) {
  const projectKinds = detectProjectKinds(entryNames);
  const gitignoreRules = parseGitignore(gitignoreContent);
  const staticRules = projectKinds.flatMap((kind) =>
    PROJECT_IGNORE_CATALOGS[kind].map((pattern) => compileIgnoreRule(pattern, `catalog:${kind}`)),
  );
  const orderedRules = [...gitignoreRules, ...staticRules];

  return {
    projectKinds,
    gitignoreRuleCount: gitignoreRules.length,
    staticRuleCount: staticRules.length,
    summary: {
      projectKinds,
      gitignoreRuleCount: gitignoreRules.length,
      staticRuleCount: staticRules.length,
    },
    shouldIgnore(filePath) {
      if (isRootMetadataPath(filePath)) {
        return false;
      }

      let ignored = false;
      for (const rule of orderedRules) {
        if (!rule.regex.test(filePath)) continue;
        ignored = !rule.negated;
      }
      return ignored;
    },
  };
}

export function shouldRetainArchivePath(filePath, policy) {
  if (isRootMetadataPath(filePath)) {
    return true;
  }

  if (!CODE_PATH_PATTERN.test(filePath)) {
    return false;
  }

  return !policy.shouldIgnore(filePath);
}

export function isRootMetadataPath(filePath) {
  return ROOT_METADATA_FILES.has(filePath);
}

function detectProjectKinds(entryNames) {
  const normalized = entryNames.map((entry) => entry.replace(/\\/g, '/').toLowerCase());
  const projectKinds = new Set();

  if (normalized.includes('package.json')) {
    projectKinds.add('nodejs');
  }

  if (
    normalized.includes('pyproject.toml') ||
    normalized.includes('requirements.txt') ||
    normalized.includes('setup.py') ||
    normalized.some((entry) => entry.endsWith('.py'))
  ) {
    projectKinds.add('python');
  }

  if (
    normalized.some((entry) => entry.endsWith('.ts') || entry.endsWith('.tsx')) ||
    normalized.some((entry) => /^tsconfig(\..+)?\.json$/.test(entry.split('/').pop()))
  ) {
    projectKinds.add('typescript');
  }

  return [...projectKinds];
}

function parseGitignore(content) {
  return content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'))
    .map((pattern) => compileIgnoreRule(pattern, 'gitignore'))
    .filter(Boolean);
}

function compileIgnoreRule(rawPattern, source) {
  let pattern = rawPattern.trim();
  if (!pattern) return null;

  let negated = false;
  if (pattern.startsWith('!')) {
    negated = true;
    pattern = pattern.slice(1);
  }

  if (!pattern) return null;

  pattern = pattern.replace(/^\.\/+/, '').replace(/\\/g, '/');

  const anchored = pattern.startsWith('/');
  if (anchored) {
    pattern = pattern.slice(1);
  }

  const directoryOnly = pattern.endsWith('/');
  if (directoryOnly) {
    pattern = pattern.slice(0, -1);
  }

  if (!pattern) return null;

  const hasSlash = pattern.includes('/');
  const translated = translateGlob(pattern);
  let regexSource = '';

  if (directoryOnly) {
    regexSource = hasSlash || anchored
      ? `^${translated}(?:/|$)`
      : `(?:^|/)${translated}(?:/|$)`;
  } else if (hasSlash || anchored) {
    regexSource = anchored ? `^${translated}$` : `(?:^|/)${translated}$`;
  } else {
    regexSource = `(?:^|/)${translated}$`;
  }

  return {
    source,
    negated,
    pattern: rawPattern,
    regex: new RegExp(regexSource),
  };
}

function translateGlob(pattern) {
  let output = '';

  for (let index = 0; index < pattern.length; index += 1) {
    const char = pattern[index];
    const next = pattern[index + 1];

    if (char === '*') {
      if (next === '*') {
        output += '.*';
        index += 1;
      } else {
        output += '[^/]*';
      }
      continue;
    }

    if (char === '?') {
      output += '[^/]';
      continue;
    }

    output += escapeRegExp(char);
  }

  return output;
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

assertCatalogSize('nodejs', NODEJS_IGNORE_PATTERNS);
assertCatalogSize('python', PYTHON_IGNORE_PATTERNS);
assertCatalogSize('typescript', TYPESCRIPT_IGNORE_PATTERNS);

function assertCatalogSize(name, values) {
  if (values.length !== 100) {
    throw new Error(`Ignore catalog ${name} must contain exactly 100 patterns, received ${values.length}`);
  }
}

import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { buildSuggestionSet, ingestRepository, runLogicLensSymbolica } from './logic/ingest-runner.mjs';
import { writeArtifactJson } from './logic/artifact-store.mjs';
import { buildMigrationPlan, renderMigrationReport } from './logic/migration-planner.mjs';
import { buildValidationReport } from './logic/scan-validator.mjs';

const port = 3001;
const jobs = new Map();

const PHASE_TEMPLATES = [
  { key: 'validate', label: 'Normalize request', detail: 'Validating repository coordinates' },
  { key: 'source', label: 'Ingest source repo', detail: 'Fetching archive, extracting facts, and persisting artifact' },
  { key: 'taint', label: 'Run LogicLens + Symbolica', detail: 'Evaluating local rules over extracted facts' },
  { key: 'reference', label: 'Ingest reference repo', detail: 'Reference repo skipped' },
  { key: 'map', label: 'Build swap map', detail: 'Bucketing vendors and matching alternates' },
];

const server = http.createServer(async (request, response) => {
  applyCors(response);

  if (request.method === 'OPTIONS') {
    response.writeHead(204);
    response.end();
    return;
  }

  try {
    const url = new URL(request.url ?? '/', `http://${request.headers.host ?? `localhost:${port}`}`);

    if (request.method === 'GET' && url.pathname === '/health') {
      sendJson(response, 200, { ok: true });
      return;
    }

    if (request.method === 'POST' && url.pathname === '/scan') {
      const body = await readJsonBody(request);
      const sourceRepo = `${body.sourceRepo ?? ''}`.trim();
      const referenceRepo = `${body.referenceRepo ?? ''}`.trim();

      if (!sourceRepo) {
        sendJson(response, 400, { error: 'sourceRepo is required' });
        return;
      }

      const job = createJob(sourceRepo, referenceRepo || undefined);
      jobs.set(job.id, job);
      runJob(job).catch((error) => {
        failJob(job, error instanceof Error ? error.message : 'Scan failed');
      });

      sendJson(response, 202, { id: job.id });
      return;
    }

    if (request.method === 'GET' && url.pathname.startsWith('/scan/')) {
      const id = url.pathname.split('/').pop();
      const job = jobs.get(id);
      if (!job) {
        sendJson(response, 404, { error: 'Scan job not found' });
        return;
      }

      sendJson(response, 200, serializeJob(job));
      return;
    }

    sendJson(response, 404, { error: 'Not found' });
  } catch (error) {
    sendJson(response, 500, {
      error: error instanceof Error ? error.message : 'Unexpected server error',
    });
  }
});

server.listen(port, () => {
  console.log(`[scan-server] listening on http://localhost:${port}`);
});

function createJob(sourceRepo, referenceRepo) {
  return {
    id: randomUUID(),
    status: 'running',
    createdAt: new Date().toISOString(),
    sourceRepo,
    referenceRepo,
    phases: PHASE_TEMPLATES.map((phase, index) => ({
      ...phase,
      status: index === 0 ? 'running' : 'pending',
    })),
    primaryRepo: null,
    secondaryRepo: null,
    suggestions: [],
    taintReports: [],
    migrationPlan: null,
    validationReport: null,
    artifacts: {},
    error: undefined,
  };
}

async function runJob(job) {
  setPhase(job, 'validate', 'running', 'Repository coordinates received');
  await pause(120);
  setPhase(job, 'validate', 'completed', 'Ready to scan public GitHub repositories');

  setPhase(job, 'source', 'running', 'Creating durable ingest artifact');
  const sourceIngest = await ingestRepository(job.sourceRepo, (detail) => {
    setPhase(job, 'source', 'running', detail);
  });
  job.primaryRepo = sourceIngest.repo;
  job.artifacts.source = sourceIngest.artifact;
  setPhase(
    job,
    'source',
    'completed',
    `Persisted ${sourceIngest.artifact.factCount} facts from ${sourceIngest.artifact.ingestedFiles} files`,
  );

  setPhase(job, 'taint', 'running', 'Running rule engine over extracted facts');
  const logicRun = await runLogicLensSymbolica(job.primaryRepo, (detail) => {
    setPhase(job, 'taint', 'running', detail);
  });
  job.taintReports = logicRun.reports;
  setPhase(
    job,
    'taint',
    'completed',
    `Derived ${logicRun.derivedFactCount} facts across ${logicRun.ruleCount} rules and ${job.taintReports.length} taint reports`,
  );

  if (job.referenceRepo) {
    setPhase(job, 'reference', 'running', 'Creating durable reference ingest artifact');
    const referenceIngest = await ingestRepository(job.referenceRepo, (detail) => {
      setPhase(job, 'reference', 'running', detail);
    });
    job.secondaryRepo = referenceIngest.repo;
    job.artifacts.reference = referenceIngest.artifact;
    setPhase(
      job,
      'reference',
      'completed',
      `Persisted ${referenceIngest.artifact.factCount} facts from ${referenceIngest.artifact.ingestedFiles} files`,
    );
  } else {
    setPhase(job, 'reference', 'completed', 'Optional reference repo not provided');
  }

  setPhase(job, 'map', 'running', 'Building category lanes and alternate mappings');
  await pause(120);
  job.suggestions = buildSuggestionSet(job.primaryRepo, job.secondaryRepo);
  const scanSnapshot = buildScanSnapshot(job, logicRun);
  job.migrationPlan = buildMigrationPlan(scanSnapshot);
  job.validationReport = buildValidationReport(scanSnapshot, job.migrationPlan);
  await writeArtifactJson(job.primaryRepo.__artifactDir, 'migration-plan.json', job.migrationPlan);
  await writeArtifactJson(job.primaryRepo.__artifactDir, 'validation-report.json', job.validationReport);
  await writeArtifactJson(
    job.primaryRepo.__artifactDir,
    'migration-report.md',
    renderMigrationReport(job.migrationPlan, job.validationReport),
  );
  setPhase(job, 'map', 'completed', `Mapped ${job.suggestions.length} vendor lanes and wrote migration plan`);

  job.status = 'completed';
}

function failJob(job, message) {
  job.status = 'error';
  job.error = message;
  const activePhase = job.phases.find((phase) => phase.status === 'running');
  if (activePhase) {
    activePhase.status = 'error';
    activePhase.detail = message;
  }
}

function setPhase(job, key, status, detail) {
  const phase = job.phases.find((item) => item.key === key);
  if (!phase) return;
  phase.status = status;
  phase.detail = detail;
}

function serializeJob(job) {
  return {
    id: job.id,
    status: job.status,
    createdAt: job.createdAt,
    sourceRepo: job.sourceRepo,
    referenceRepo: job.referenceRepo,
    phases: job.phases,
    primaryRepo: sanitizeRepo(job.primaryRepo),
    secondaryRepo: sanitizeRepo(job.secondaryRepo),
    suggestions: job.suggestions,
    taintReports: job.taintReports,
    migrationPlan: job.migrationPlan,
    validationReport: job.validationReport,
    artifacts: job.artifacts,
    error: job.error,
  };
}

function buildScanSnapshot(job, logicRun) {
  return {
    sourceRepo: sanitizeRepo(job.primaryRepo),
    referenceRepo: sanitizeRepo(job.secondaryRepo),
    suggestions: job.suggestions,
    taintReports: job.taintReports,
    artifacts: job.artifacts,
    logicRun: {
      scopedFactCount: logicRun.scopedFactCount,
      derivedFactCount: logicRun.derivedFactCount,
      ruleCount: logicRun.ruleCount,
    },
  };
}

function sanitizeRepo(repo) {
  if (!repo) return null;
  const { __archive, __artifactDir, __files, __facts, ...rest } = repo;
  return rest;
}

function sendJson(response, statusCode, body) {
  response.writeHead(statusCode, { 'Content-Type': 'application/json; charset=utf-8' });
  response.end(JSON.stringify(body));
}

function applyCors(response) {
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  response.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

async function readJsonBody(request) {
  const chunks = [];
  for await (const chunk of request) {
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

function pause(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

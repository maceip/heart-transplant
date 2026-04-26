#!/usr/bin/env node

import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { buildSuggestionSet, ingestRepository, runLogicLensSymbolica } from '../../backend/src/logic/ingest-runner.mjs';
import { buildMigrationPlan, buildValidationReport, renderMigrationReport } from '../../backend/src/logic/migration-planner.mjs';

const args = process.argv.slice(2);

main().catch((error) => {
  console.error(error instanceof Error ? error.message : 'Unexpected CLI failure');
  process.exitCode = 1;
});

async function main() {
  const [command, ...commandArgs] = args;

  if (!command || args.includes('--help') || args.includes('-h')) {
    printHelp();
    return;
  }

  if (command === 'ingest') {
    await runIngest(commandArgs);
    return;
  }

  if (command === 'scan') {
    await runScan(commandArgs);
    return;
  }

  if (command === 'plan') {
    await runPlan(commandArgs);
    return;
  }

  throw new Error(`Unknown command: ${command}`);
}

async function runIngest(args) {
  const options = parseOptions(args);
  const repo = readRequiredRepo(options);
  const ingest = await ingestRepository(repo, createLogger(options));
  writeJson({
    repo: sanitizeRepo(ingest.repo),
    artifact: ingest.artifact,
  });
}

async function runScan(args) {
  const options = parseOptions(args);
  const scan = await executeScan(options);
  scan.migrationPlan = buildMigrationPlan(scan);
  scan.validationReport = buildValidationReport(scan, scan.migrationPlan);
  await writeScanOutputs(scan, options);
  writeJson(scan);
}

async function runPlan(args) {
  const options = parseOptions(args);
  const scan = await executeScan(options);
  const plan = buildMigrationPlan(scan);
  const validationReport = buildValidationReport(scan, plan);
  await writePlanOutputs(plan, validationReport, options);

  if (options.format === 'markdown') {
    process.stdout.write(renderMigrationReport(plan, validationReport));
    return;
  }

  writeJson({
    migrationPlan: plan,
    validationReport,
  });
}

async function executeScan(options) {
  const sourceRepo = readRequiredRepo(options);
  const referenceRepo = options.reference ?? options.ref;
  const log = createLogger(options);

  log(`Ingesting source repo ${sourceRepo}`);
  const sourceIngest = await ingestRepository(sourceRepo, log);
  const logicRun = await runLogicLensSymbolica(sourceIngest.repo, log);

  let referenceIngest = null;
  if (referenceRepo) {
    log(`Ingesting reference repo ${referenceRepo}`);
    referenceIngest = await ingestRepository(referenceRepo, log);
  }

  const suggestions = buildSuggestionSet(sourceIngest.repo, referenceIngest?.repo ?? null);
  return {
    sourceRepo: sanitizeRepo(sourceIngest.repo),
    referenceRepo: referenceIngest ? sanitizeRepo(referenceIngest.repo) : null,
    suggestions,
    taintReports: logicRun.reports,
    artifacts: {
      source: sourceIngest.artifact,
      reference: referenceIngest?.artifact,
    },
    logicRun: {
      scopedFactCount: logicRun.scopedFactCount,
      derivedFactCount: logicRun.derivedFactCount,
      ruleCount: logicRun.ruleCount,
    },
  };
}

function parseOptions(args) {
  const options = { _: [] };

  for (let index = 0; index < args.length; index += 1) {
    const value = args[index];
    if (!value.startsWith('--')) {
      options._.push(value);
      continue;
    }

    const [rawKey, inlineValue] = value.slice(2).split('=', 2);
    const key = normalizeOptionKey(rawKey.trim());
    if (!key) continue;

    if (inlineValue !== undefined) {
      options[key] = inlineValue;
      continue;
    }

    const next = args[index + 1];
    if (next && !next.startsWith('--')) {
      options[key] = next;
      index += 1;
      continue;
    }

    options[key] = true;
  }

  return options;
}

function readRequiredRepo(options) {
  const repo = options._[0];
  if (!repo) {
    throw new Error('A GitHub repo is required, e.g. heart-transplant scan owner/repo');
  }
  return repo;
}

function normalizeOptionKey(key) {
  return key.replace(/-([a-z])/g, (_match, letter) => letter.toUpperCase());
}

function createLogger(options) {
  if (options.quiet) {
    return () => {};
  }

  return (message) => {
    console.error(`[heart-transplant] ${message}`);
  };
}

async function writeScanOutputs(scan, options) {
  const outputDir = options.outputDir ?? options.out;
  if (!outputDir) return;

  await mkdir(outputDir, { recursive: true });
  await writeJsonFile(path.join(outputDir, 'scan.json'), scan);
  await writeJsonFile(path.join(outputDir, 'migration-plan.json'), scan.migrationPlan);
  await writeJsonFile(path.join(outputDir, 'validation-report.json'), scan.validationReport);
  await writeFile(path.join(outputDir, 'migration-report.md'), renderMigrationReport(scan.migrationPlan, scan.validationReport), 'utf8');
}

async function writePlanOutputs(plan, validationReport, options) {
  const outputDir = options.outputDir ?? options.out;
  if (!outputDir) return;

  await mkdir(outputDir, { recursive: true });
  await writeJsonFile(path.join(outputDir, 'migration-plan.json'), plan);
  await writeJsonFile(path.join(outputDir, 'validation-report.json'), validationReport);
  await writeFile(path.join(outputDir, 'migration-report.md'), renderMigrationReport(plan, validationReport), 'utf8');
}

function sanitizeRepo(repo) {
  const { __archive, __artifactDir, __files, __facts, ...publicRepo } = repo;
  return publicRepo;
}

function writeJson(payload) {
  console.log(JSON.stringify(payload, null, 2));
}

async function writeJsonFile(filePath, payload) {
  await writeFile(filePath, JSON.stringify(payload, null, 2), 'utf8');
}

function printHelp() {
  console.log('heart-transplant CLI');
  console.log('');
  console.log('Commands:');
  console.log('  ingest <repo>                 Ingest a public GitHub repo and print artifact metadata');
  console.log('  scan <repo> [--reference r]   Run ingest, rules, taint reporting, and swap suggestions');
  console.log('  plan <repo> [--reference r]   Generate migration plan and validation gates');
  console.log('');
  console.log('Options:');
  console.log('  --reference, --ref <repo>     Optional reference repo for scan target mapping');
  console.log('  --output-dir, --out <dir>     Persist scan/plan report files');
  console.log('  --format markdown             Print plan command as Markdown');
  console.log('  --quiet                       Suppress progress logs on stderr');
  console.log('  --help                        Show this help');
}

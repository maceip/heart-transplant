const SCHEMA_VERSION = 'phase-13.migration-plan.v1';

export function buildMigrationPlan(scan) {
  const lanes = (scan.suggestions ?? []).map((lane, index) => buildLanePlan(lane, index));
  const riskCounts = lanes.reduce(
    (counts, lane) => {
      counts[lane.risk.level] += 1;
      return counts;
    },
    { low: 0, medium: 0, high: 0 },
  );

  return {
    schemaVersion: SCHEMA_VERSION,
    generatedAt: new Date().toISOString(),
    sourceRepo: scan.sourceRepo?.fullName ?? null,
    referenceRepo: scan.referenceRepo?.fullName ?? null,
    artifact: scan.artifacts?.source ?? scan.sourceRepo?.artifact ?? null,
    summary: {
      laneCount: lanes.length,
      highRiskLaneCount: riskCounts.high,
      mediumRiskLaneCount: riskCounts.medium,
      lowRiskLaneCount: riskCounts.low,
      sourceVendorCount: scan.sourceRepo?.vendorSignals?.length ?? 0,
      taintReportCount: scan.taintReports?.length ?? 0,
    },
    lanes,
    validationGates: buildValidationGates(scan, lanes),
  };
}

export function buildValidationReport(scan, plan = buildMigrationPlan(scan)) {
  const gates = plan.validationGates.map((gate) => ({
    ...gate,
    status: gate.required && gate.state === 'failed' ? 'failed' : gate.state,
  }));

  const failedRequired = gates.filter((gate) => gate.required && gate.status === 'failed');
  return {
    schemaVersion: `${SCHEMA_VERSION}.validation`,
    generatedAt: new Date().toISOString(),
    status: failedRequired.length ? 'failed' : 'passed',
    gates,
  };
}

export function renderMigrationReport(plan, validationReport = buildValidationReport({}, plan)) {
  const lines = [
    `# Migration plan for ${plan.sourceRepo ?? 'unknown repo'}`,
    '',
    `Generated: ${plan.generatedAt}`,
    `Schema: ${plan.schemaVersion}`,
    '',
    '## Summary',
    '',
    `- Suggested lanes: ${plan.summary.laneCount}`,
    `- Source vendors: ${plan.summary.sourceVendorCount}`,
    `- Taint reports: ${plan.summary.taintReportCount}`,
    `- Risk split: ${plan.summary.highRiskLaneCount} high / ${plan.summary.mediumRiskLaneCount} medium / ${plan.summary.lowRiskLaneCount} low`,
    '',
    '## Validation gates',
    '',
    ...validationReport.gates.map((gate) => `- [${gate.status === 'passed' ? 'x' : ' '}] ${gate.name}: ${gate.detail}`),
    '',
    '## Lanes',
    '',
  ];

  for (const lane of plan.lanes) {
    lines.push(
      `### ${lane.sourceVendor.label} -> ${lane.targetVendor.label}`,
      '',
      `- Category: ${lane.category}`,
      `- Risk: ${lane.risk.level} (${lane.risk.reason})`,
      `- Remove packages: ${lane.packageChanges.remove.join(', ') || 'none recorded'}`,
      `- Add packages: ${lane.packageChanges.add.join(', ') || lane.targetVendor.id}`,
      `- Candidate files: ${lane.evidence.candidateFiles.length}`,
      `- Blocked files: ${lane.evidence.blockedFiles.length}`,
      '',
      'Steps:',
      ...lane.steps.map((step, index) => `${index + 1}. ${step}`),
      '',
    );
  }

  if (!plan.lanes.length) {
    lines.push('No vendor swap lanes were detected for this scan.', '');
  }

  return `${lines.join('\n')}\n`;
}

function buildLanePlan(lane, index) {
  const taint = lane.taint ?? null;
  const risk = scoreLaneRisk(taint);
  const sourcePackages = lane.source.packages ?? [];
  const targetPackages = lane.target.packages?.length ? lane.target.packages : [lane.target.id];

  return {
    id: `${lane.category}:${lane.source.id}:${lane.target.id}:${index}`,
    category: lane.category,
    reason: lane.reason,
    sourceVendor: summarizeVendor(lane.source),
    targetVendor: summarizeVendor(lane.target),
    packageChanges: {
      remove: sourcePackages,
      add: targetPackages,
    },
    evidence: {
      confidence: taint?.confidence ?? 'low',
      sourceMatches: taint?.sourceMatches?.length ?? 0,
      sinkMatches: taint?.sinkMatches?.length ?? 0,
      evidencePaths: taint?.evidencePaths ?? [],
      candidateFiles: taint?.candidateFiles ?? [],
      blockedFiles: taint?.blockedFiles ?? [],
      taintedFiles: taint?.taintedFiles ?? [],
    },
    risk,
    steps: buildLaneSteps(lane, taint, risk),
  };
}

function summarizeVendor(vendor) {
  return {
    id: vendor.id,
    label: vendor.label,
    category: vendor.category,
    packages: vendor.packages ?? [],
    confidence: vendor.confidence,
  };
}

function buildLaneSteps(lane, taint, risk) {
  const steps = [
    `Inventory current ${lane.source.label} usage from detected packages and source matches.`,
    `Replace package dependency ${formatPackageList(lane.source.packages)} with ${formatPackageList(lane.target.packages?.length ? lane.target.packages : [lane.target.id])}.`,
    `Update imports, initialization code, and configuration from ${lane.source.label} to ${lane.target.label}.`,
  ];

  if (taint?.candidateFiles?.length) {
    steps.push(`Prioritize candidate files: ${taint.candidateFiles.slice(0, 5).join(', ')}.`);
  }

  if (taint?.blockedFiles?.length) {
    steps.push(`Review blocked files before automated edits: ${taint.blockedFiles.slice(0, 5).join(', ')}.`);
  }

  steps.push(
    risk.level === 'high'
      ? 'Run focused integration tests before broad replacement because source and sink evidence are connected.'
      : 'Run package install, type checks, and unit tests after the replacement.',
  );

  return steps;
}

function buildValidationGates(scan, lanes) {
  return [
    {
      id: 'source-artifact',
      name: 'Source artifact persisted',
      required: true,
      state: scan.artifacts?.source?.id ? 'passed' : 'failed',
      detail: scan.artifacts?.source?.id ?? 'missing source artifact id',
    },
    {
      id: 'fact-extraction',
      name: 'Fact extraction completed',
      required: true,
      state: (scan.artifacts?.source?.factCount ?? 0) > 0 ? 'passed' : 'failed',
      detail: `${scan.artifacts?.source?.factCount ?? 0} facts extracted`,
    },
    {
      id: 'rule-scope',
      name: 'Rule input stayed bounded',
      required: true,
      state: (scan.logicRun?.scopedFactCount ?? 0) <= 2000 ? 'passed' : 'failed',
      detail: `${scan.logicRun?.scopedFactCount ?? 0} scoped facts`,
    },
    {
      id: 'migration-plan',
      name: 'Migration plan generated',
      required: false,
      state: lanes.length ? 'passed' : 'skipped',
      detail: lanes.length ? `${lanes.length} lanes planned` : 'no vendor lanes detected',
    },
    {
      id: 'manual-review',
      name: 'Manual review needed for risky lanes',
      required: false,
      state: lanes.some((lane) => lane.risk.level === 'high') ? 'warning' : 'passed',
      detail: `${lanes.filter((lane) => lane.risk.level === 'high').length} high-risk lanes`,
    },
  ];
}

function scoreLaneRisk(taint) {
  if (!taint) {
    return { level: 'low', reason: 'No taint evidence was detected for this lane.' };
  }

  if (taint.confidence === 'high' || taint.evidencePaths?.length) {
    return { level: 'high', reason: 'Source and sink evidence are connected by dependency paths.' };
  }

  if (taint.sinkMatches?.length || taint.blockedFiles?.length) {
    return { level: 'medium', reason: 'Sink or blocked-file evidence requires targeted review.' };
  }

  return { level: 'low', reason: 'Only source-level evidence was detected.' };
}

function formatPackageList(packages = []) {
  return packages.length ? packages.join(', ') : 'the detected vendor package';
}

const SCHEMA_VERSION = 'phase-13.scan-validation.v2';

export function buildValidationReport(scan, plan) {
  const metrics = collectMetrics(scan, plan);
  const gates = [
    gate({
      id: 'artifact.source.present',
      name: 'Source artifact exists',
      severity: 'error',
      passed: Boolean(scan.artifacts?.source?.id && scan.artifacts?.source?.dir),
      detail: scan.artifacts?.source?.id
        ? `source artifact ${scan.artifacts.source.id}`
        : 'source artifact metadata is missing',
      metrics: {
        artifactId: scan.artifacts?.source?.id ?? null,
        artifactDir: scan.artifacts?.source?.dir ?? null,
      },
    }),
    gate({
      id: 'artifact.source.non_empty',
      name: 'Source artifact contains extracted files and facts',
      severity: 'error',
      passed: metrics.ingestedFiles > 0 && metrics.factCount > 0,
      detail: `${metrics.ingestedFiles} files and ${metrics.factCount} facts extracted`,
      metrics: {
        ingestedFiles: metrics.ingestedFiles,
        factCount: metrics.factCount,
      },
    }),
    gate({
      id: 'logic.rules.executed',
      name: 'Logic rule pass executed',
      severity: metrics.sourceVendorCount ? 'error' : 'info',
      passed: metrics.sourceVendorCount ? metrics.ruleCount > 0 && metrics.scopedFactCount > 0 : false,
      status: metrics.sourceVendorCount ? undefined : 'skipped',
      detail: metrics.sourceVendorCount
        ? `${metrics.ruleCount} rules evaluated over ${metrics.scopedFactCount} scoped facts`
        : 'no supported source vendors were detected, so no evidence-scoped rule input was expected',
      metrics: {
        ruleCount: metrics.ruleCount,
        scopedFactCount: metrics.scopedFactCount,
        derivedFactCount: metrics.derivedFactCount,
      },
    }),
    gate({
      id: 'logic.budget.complete',
      name: 'Rule input budget was not truncated',
      severity: 'warning',
      passed: !metrics.truncatedRuleInput,
      detail: metrics.truncatedRuleInput
        ? describeBudgetTruncation(metrics.budget)
        : 'all detected source, sink, and retained import facts fit within rule budgets',
      metrics: metrics.budget,
    }),
    gate({
      id: 'plan.coverage',
      name: 'Plan covers every suggested lane',
      severity: 'error',
      passed: metrics.suggestionCount === metrics.planLaneCount,
      detail: `${metrics.planLaneCount} planned lanes for ${metrics.suggestionCount} suggestions`,
      metrics: {
        suggestionCount: metrics.suggestionCount,
        planLaneCount: metrics.planLaneCount,
      },
    }),
    gate({
      id: 'plan.vendor_detection',
      name: 'Vendor detection produced migration candidates',
      severity: 'info',
      passed: metrics.sourceVendorCount > 0,
      detail: metrics.sourceVendorCount
        ? `${metrics.sourceVendorCount} source vendors detected`
        : 'no supported source vendors were detected',
      metrics: {
        sourceVendorCount: metrics.sourceVendorCount,
      },
    }),
    gate({
      id: 'review.high_risk_lanes',
      name: 'High-risk lanes require review',
      severity: 'warning',
      passed: metrics.highRiskLaneCount === 0,
      detail: metrics.highRiskLaneCount
        ? `${metrics.highRiskLaneCount} high-risk lanes require manual review`
        : 'no high-risk lanes detected',
      metrics: {
        highRiskLaneCount: metrics.highRiskLaneCount,
      },
    }),
  ];

  const summary = summarizeGates(gates);
  return {
    schemaVersion: SCHEMA_VERSION,
    generatedAt: new Date().toISOString(),
    status: summary.errorCount ? 'failed' : summary.warningCount ? 'warning' : 'passed',
    summary,
    gates,
  };
}

function collectMetrics(scan, plan) {
  const budget = scan.logicRun?.budget ?? {};
  return {
    ingestedFiles: scan.artifacts?.source?.ingestedFiles ?? 0,
    factCount: scan.artifacts?.source?.factCount ?? 0,
    ruleCount: scan.logicRun?.ruleCount ?? 0,
    scopedFactCount: scan.logicRun?.scopedFactCount ?? 0,
    derivedFactCount: scan.logicRun?.derivedFactCount ?? 0,
    sourceVendorCount: scan.sourceRepo?.vendorSignals?.length ?? 0,
    suggestionCount: scan.suggestions?.length ?? 0,
    planLaneCount: plan?.lanes?.length ?? 0,
    highRiskLaneCount: plan?.summary?.highRiskLaneCount ?? 0,
    truncatedRuleInput: Boolean(
      budget.truncatedImportEdges ||
        budget.truncatedSourceMatches ||
        budget.truncatedSinkMatches,
    ),
    budget,
  };
}

function gate({ id, name, severity, passed, status, detail, metrics }) {
  const resolvedStatus = status ?? (passed ? 'passed' : severity === 'error' ? 'failed' : severity);
  return {
    id,
    name,
    severity,
    status: resolvedStatus,
    passed,
    detail,
    metrics,
  };
}

function summarizeGates(gates) {
  return gates.reduce(
    (summary, item) => {
      summary.total += 1;
      summary[item.status] += 1;
      if (item.status === 'failed') summary.errorCount += 1;
      if (item.status === 'warning') summary.warningCount += 1;
      return summary;
    },
    {
      total: 0,
      passed: 0,
      failed: 0,
      warning: 0,
      info: 0,
      skipped: 0,
      errorCount: 0,
      warningCount: 0,
    },
  );
}

function describeBudgetTruncation(budget) {
  const parts = [];
  if (budget.truncatedSourceMatches) {
    parts.push(`source matches ${budget.sourceMatchLimit}/${budget.sourceMatchesSeen}`);
  }
  if (budget.truncatedSinkMatches) {
    parts.push(`sink matches ${budget.sinkMatchLimit}/${budget.sinkMatchesSeen}`);
  }
  if (budget.truncatedImportEdges) {
    parts.push(`import edges ${budget.importEdgeLimit}+ retained at depth ${budget.importDepth}`);
  }
  return `rule input was truncated: ${parts.join(', ')}`;
}

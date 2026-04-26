export type VendorCategory =
  | 'authentication'
  | 'database'
  | 'analytics'
  | 'payments'
  | 'ui'
  | 'observability'
  | 'cloud'
  | 'ai';

export interface RepoModule {
  name: string;
  version?: string;
  ecosystem: string;
}

export interface VendorSignal {
  id: string;
  label: string;
  category: VendorCategory;
  packages: string[];
  iconSlug: string | null;
  confidence: 'high' | 'medium';
}

export interface TaintMatch {
  filePath: string;
  line: number;
  kind: 'source' | 'sink';
  excerpt: string;
  pattern: string;
  role: string;
}

export interface TaintEdge {
  from: string;
  to: string;
}

export interface TaintReport {
  vendorId: string;
  category: VendorCategory;
  sourceMatches: TaintMatch[];
  sinkMatches: TaintMatch[];
  evidencePaths: string[][];
  taintedFiles: string[];
  candidateFiles: string[];
  blockedFiles: string[];
  evidenceFiles: string[];
  prunedFiles: string[];
  confidence: 'high' | 'medium' | 'low';
}

export interface RepoArtifact {
  id: string;
  dir: string;
  factCount: number;
  ingestedFiles: number;
}

export interface LogicRunSummary {
  ruleCount: number;
  derivedFactCount: number;
  scopedFactCount?: number;
  budget?: {
    sourceMatchesSeen?: number;
    sourceMatchLimit?: number;
    truncatedSourceMatches?: boolean;
    sinkMatchesSeen?: number;
    sinkMatchLimit?: number;
    truncatedSinkMatches?: boolean;
    importEdgesRetained?: number;
    importEdgeLimit?: number;
    importDepth?: number;
    truncatedImportEdges?: boolean;
  };
}

export interface IngestPolicySummary {
  projectKinds: string[];
  gitignoreRuleCount: number;
  staticRuleCount: number;
}

export interface RepoIntel {
  input: string;
  owner: string;
  repo: string;
  fullName: string;
  description: string;
  defaultBranch: string;
  language: string | null;
  stars: number;
  forks: number;
  openIssues: number;
  updatedAt: string;
  packageSystems: string[];
  manifests: string[];
  modules: RepoModule[];
  vendorSignals: VendorSignal[];
  artifact?: Pick<RepoArtifact, 'id' | 'dir'>;
  ingestPolicy?: IngestPolicySummary;
  logicRun?: LogicRunSummary;
}

export interface SuggestionLane {
  category: VendorCategory;
  source: VendorSignal;
  target: VendorSignal;
  reason: string;
  taint?: TaintReport | null;
}

export interface MigrationPlanLane {
  id: string;
  category: VendorCategory;
  sourceVendor: Pick<VendorSignal, 'id' | 'label' | 'category' | 'packages' | 'confidence'>;
  targetVendor: Pick<VendorSignal, 'id' | 'label' | 'category' | 'packages' | 'confidence'>;
  risk: {
    level: 'low' | 'medium' | 'high';
    reason: string;
  };
  steps: string[];
}

export interface ValidationGate {
  id: string;
  name: string;
  severity: 'error' | 'warning' | 'info';
  status: 'passed' | 'failed' | 'warning' | 'info' | 'skipped';
  passed: boolean;
  detail: string;
  metrics?: Record<string, unknown>;
}

export interface MigrationPlan {
  schemaVersion: string;
  generatedAt: string;
  sourceRepo: string | null;
  referenceRepo: string | null;
  summary: {
    laneCount: number;
    highRiskLaneCount: number;
    mediumRiskLaneCount: number;
    lowRiskLaneCount: number;
    sourceVendorCount: number;
    taintReportCount: number;
  };
  lanes: MigrationPlanLane[];
}

export interface ValidationReport {
  schemaVersion: string;
  generatedAt: string;
  status: 'passed' | 'warning' | 'failed';
  summary: {
    total: number;
    passed: number;
    failed: number;
    warning: number;
    info: number;
    skipped: number;
    errorCount: number;
    warningCount: number;
  };
  gates: ValidationGate[];
}

export interface ScanPhase {
  key: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  detail: string;
}

export interface ScanJobResponse {
  id: string;
  status: 'running' | 'completed' | 'error';
  createdAt: string;
  sourceRepo: string;
  referenceRepo?: string;
  phases: ScanPhase[];
  primaryRepo: RepoIntel | null;
  secondaryRepo: RepoIntel | null;
  suggestions: SuggestionLane[];
  taintReports: TaintReport[];
  migrationPlan?: MigrationPlan | null;
  validationReport?: ValidationReport | null;
  artifacts?: {
    source?: RepoArtifact;
    reference?: RepoArtifact;
  };
  error?: string;
}

export const CATEGORY_LABELS: Record<VendorCategory, string> = {
  authentication: 'Identity / Auth',
  database: 'Database',
  analytics: 'Analytics',
  payments: 'Payments',
  ui: 'UI Surface',
  observability: 'Observability',
  cloud: 'Cloud Runtime',
  ai: 'AI Layer',
};

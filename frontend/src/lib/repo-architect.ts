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

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowRight,
  Binary,
  Boxes,
  Github,
  Loader2,
  Radar,
  Settings2,
  Sparkles,
} from 'lucide-react';
import {
  CATEGORY_LABELS,
  type RepoIntel,
  type ScanJobResponse,
  type ScanPhase,
  type SuggestionLane,
  type TaintReport,
  type VendorSignal,
} from './lib/repo-architect';
import { VendorGlyph } from './components/VendorGlyph';

const App: React.FC = () => {
  const [primaryInput, setPrimaryInput] = useState('');
  const [secondaryInput, setSecondaryInput] = useState('');
  const [primaryRepo, setPrimaryRepo] = useState<RepoIntel | null>(null);
  const [secondaryRepo, setSecondaryRepo] = useState<RepoIntel | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestionLane[]>([]);
  const [taintReports, setTaintReports] = useState<TaintReport[]>([]);
  const [phases, setPhases] = useState<ScanPhase[]>(defaultPhases());
  const [scanJobId, setScanJobId] = useState<string | null>(null);
  const [iconCount, setIconCount] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedLaneId, setSelectedLaneId] = useState<string | null>(null);
  const pollTimer = useRef<number | null>(null);

  useEffect(() => {
    fetch('/vendor-icons/logos/manifest.json')
      .then((response) => response.json())
      .then((payload) => setIconCount(payload.totalVisibleIcons ?? 0))
      .catch(() => setIconCount(0));

    return () => {
      if (pollTimer.current) {
        window.clearTimeout(pollTimer.current);
      }
    };
  }, []);

  const selectedLane = useMemo(
    () => suggestions.find((lane, index) => getLaneId(lane, index) === selectedLaneId) ?? null,
    [selectedLaneId, suggestions],
  );

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!primaryInput.trim()) {
      setError('Enter a source repo before scanning.');
      return;
    }

    if (pollTimer.current) {
      window.clearTimeout(pollTimer.current);
    }

    setLoading(true);
    setError(null);
    setPrimaryRepo(null);
    setSecondaryRepo(null);
    setSuggestions([]);
    setTaintReports([]);
    setSelectedLaneId(null);
    setPhases(defaultPhases('Queued for backend scan'));

    try {
      const response = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sourceRepo: primaryInput.trim(),
          referenceRepo: secondaryInput.trim() || undefined,
        }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error ?? 'Unable to start scan.');
      }

      const payload = (await response.json()) as { id: string };
      setScanJobId(payload.id);
      pollScan(payload.id);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to scan those repositories.';
      setLoading(false);
      setError(message);
      setPhases(defaultPhases(message, 'error'));
    }
  }

  async function pollScan(jobId: string) {
    try {
      const response = await fetch(`/api/scan/${jobId}`);
      if (!response.ok) {
        throw new Error('Unable to read scan status.');
      }

      const payload = (await response.json()) as ScanJobResponse;
      hydrateJob(payload);

      if (payload.status === 'running') {
        pollTimer.current = window.setTimeout(() => pollScan(jobId), 500);
        return;
      }

      if (payload.status === 'completed') {
        setLoading(false);
        setScanJobId(null);
        if (payload.suggestions.length) {
          setSelectedLaneId(getLaneId(payload.suggestions[0], 0));
        }
        return;
      }

      setLoading(false);
      setScanJobId(null);
      setError(payload.error ?? 'Scan failed.');
    } catch (caught) {
      setLoading(false);
      setScanJobId(null);
      setError(caught instanceof Error ? caught.message : 'Scan polling failed.');
    }
  }

  function hydrateJob(payload: ScanJobResponse) {
    setPhases(payload.phases);
    setPrimaryRepo(payload.primaryRepo);
    setSecondaryRepo(payload.secondaryRepo);
    setSuggestions(payload.suggestions);
    setTaintReports(payload.taintReports);
  }

  const statusLine = activeStatusLine(phases, loading);

  return (
    <div className="architect-page">
      <header className="architect-topbar">
        <div className="architect-brand">
          <div className="architect-brand__mark">REPOCITY_v2.1</div>
          <nav className="architect-nav">
            <span className="is-active">Map View</span>
            <span>Metric Districts</span>
            <span>Schema</span>
          </nav>
        </div>

        <div className="architect-actions">
          <button className="architect-icon-button" aria-label="GitHub">
            <Github size={16} />
          </button>
          <button className="architect-icon-button" aria-label="Settings">
            <Settings2 size={16} />
          </button>
          <div className="architect-avatar">R</div>
        </div>
      </header>

      <main className="architect-main">
        <section className="architect-intake">
          <div className="architect-intake__meta">
            <span>System Map</span>
            <span>{scanJobId ? `Job ${scanJobId.slice(0, 8)}` : 'Public GitHub ingress only'}</span>
          </div>

          <form className="architect-dock" onSubmit={handleSubmit}>
            <label className="architect-dock__field">
              <span className="architect-dock__label">Source repo</span>
              <input
                value={primaryInput}
                onChange={(event) => setPrimaryInput(event.target.value)}
                placeholder="https://github.com/owner/repo"
              />
            </label>

            <label className="architect-dock__field">
              <span className="architect-dock__label">Reference repo (optional)</span>
              <input
                value={secondaryInput}
                onChange={(event) => setSecondaryInput(event.target.value)}
                placeholder="https://github.com/owner/repo"
              />
            </label>

            <button className="architect-dock__button" type="submit" disabled={loading}>
              {loading ? <Loader2 size={16} className="spin" /> : <Radar size={16} />}
              {loading ? 'Scanning' : 'Go'}
            </button>
          </form>

          <div className="architect-intake__caption">
            {statusLine}
          </div>

          <div className="phase-strip">
            {phases.map((phase) => (
              <div className={`phase-pill phase-pill--${phase.status}`} key={phase.key}>
                <span>{phase.label}</span>
                <small>{phase.detail}</small>
              </div>
            ))}
          </div>

          {error ? <div className="architect-error">{error}</div> : null}
        </section>

        <section className="architect-board">
          <div className="architect-grid">
            <RepoDistrict
              zoneLabel="ZONE_01"
              title={primaryRepo ? primaryRepo.repo : 'SOURCE_CONTROL_A'}
              subtitle={primaryRepo ? primaryRepo.fullName : 'Awaiting source coordinates'}
              repo={primaryRepo}
              loading={loading}
            />

            <div className={`architect-spine ${loading ? 'is-loading' : ''}`}>
              <MetricTower
                value={phaseValue(phases, 'source', primaryRepo?.vendorSignals.length)}
                label="source scan"
                hint={phaseHint(phases, 'source', primaryRepo ? `${primaryRepo.modules.length} modules parsed` : 'waiting for scan')}
              />
              <MetricTower
                value={phaseValue(phases, 'taint', taintReports.length)}
                label="taint trace"
                hint={phaseHint(phases, 'taint', 'source / sink evidence pending')}
              />
              <MetricTower
                value={phaseValue(phases, 'reference', secondaryRepo?.vendorSignals.length, suggestions.length)}
                label={secondaryRepo ? 'reference scan' : 'alternate atlas'}
                hint={phaseHint(
                  phases,
                  'reference',
                  secondaryRepo ? `${secondaryRepo.modules.length} modules parsed` : 'optional repo or static map',
                )}
              />
              <MetricTower
                value={phaseValue(phases, 'map', suggestions.length)}
                label="swap lanes"
                hint={phaseHint(phases, 'map', 'identity / db / analytics / ui')}
              />
              <div className="architect-spine__annotation">
                <span>SYSTEM_INTERSECT</span>
                <span>{loading ? 'backend scan in progress' : 'backend scan seam active'}</span>
              </div>
            </div>

            <RepoDistrict
              zoneLabel="ZONE_02"
              title={
                secondaryRepo
                  ? secondaryRepo.repo
                  : suggestions.length
                    ? 'ALTERNATE_ATLAS'
                    : 'REFERENCE_OPTIONAL'
              }
              subtitle={
                secondaryRepo
                  ? secondaryRepo.fullName
                  : suggestions.length
                    ? 'Curated category suggestions'
                    : 'Optional second repo can steer the targets'
              }
              repo={secondaryRepo}
              loading={loading}
              fallbackSignals={suggestions.map((lane) => lane.target)}
            />
          </div>
        </section>

        <section className="architect-schema">
          <div className="architect-schema__header">
            <div>
              <div className="architect-kicker">Schema lanes</div>
              <h2>Suggested module swaps</h2>
            </div>
            <div className="architect-schema__meta">
              <span>{iconCount ? `${iconCount} local SVGs indexed` : 'Loading icon manifest'}</span>
              <span>{secondaryRepo ? 'repo-to-repo mapping' : 'static alternate mapping'}</span>
            </div>
          </div>

          {!primaryRepo && !loading ? (
            <div className="architect-empty">
              <Sparkles size={18} />
              <p>Enter one repo to see categories, modules, and suggested alternates.</p>
            </div>
          ) : null}

          <div className="architect-lanes">
            {suggestions.map((lane, index) => {
              const laneId = getLaneId(lane, index);
              return (
                <button
                  className={`swap-lane ${selectedLaneId === laneId ? 'is-selected' : ''}`}
                  key={laneId}
                  type="button"
                  onClick={() => setSelectedLaneId(laneId)}
                >
                  <div className="swap-lane__zone">
                    <div className="swap-lane__zone-label">{CATEGORY_LABELS[lane.category]}</div>
                    <div className="swap-node">
                      <div className="swap-node__top">
                        <VendorGlyph label={lane.source.label} iconSlug={lane.source.iconSlug} />
                        <div>
                          <h3>{lane.source.label}</h3>
                          <p>{lane.source.packages[0] ?? 'package detected'}</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="swap-lane__bridge">
                    <div className="swap-lane__line" />
                    <div className="swap-lane__reason">
                      <Binary size={12} />
                      {lane.reason}
                    </div>
                    <ArrowRight size={18} />
                  </div>

                  <div className="swap-lane__zone">
                    <div className="swap-lane__zone-label">Suggested target</div>
                    <div className="swap-node swap-node--target">
                      <div className="swap-node__top">
                        <VendorGlyph label={lane.target.label} iconSlug={lane.target.iconSlug} />
                        <div>
                          <h3>{lane.target.label}</h3>
                          <p>{secondaryRepo ? 'present in reference repo' : 'from curated catalog'}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {selectedLane ? (
            <div className="lane-detail">
              <div className="lane-detail__header">
                <div>
                  <div className="architect-kicker">Lane detail</div>
                  <h3>
                    {selectedLane.source.label} <ArrowRight size={16} /> {selectedLane.target.label}
                  </h3>
                </div>
                <div className="lane-detail__chips">
                  <span>{CATEGORY_LABELS[selectedLane.category]}</span>
                  <span>{selectedLane.source.confidence} confidence</span>
                </div>
              </div>

              <div className="lane-detail__grid">
                <DetailCard
                  title="Detected packages"
                  lines={selectedLane.source.packages.length ? selectedLane.source.packages : ['No package names recorded']}
                />
                <DetailCard
                  title="Why this target"
                  lines={[
                    selectedLane.reason,
                    secondaryRepo
                      ? 'Reference repo supplied a category-matching vendor.'
                      : 'Curated alternates filled the target slot.',
                  ]}
                />
                <DetailCard
                  title="Scan evidence"
                  lines={[
                    `Source repo manifests: ${primaryRepo?.manifests.join(', ') || 'none found'}`,
                    `Source repo modules parsed: ${primaryRepo?.modules.length ?? 0}`,
                    `Tainted files: ${selectedLane.taint?.taintedFiles.length ?? 0}`,
                    secondaryRepo
                      ? `Reference repo manifests: ${secondaryRepo.manifests.join(', ')}`
                      : 'Reference repo not provided',
                  ]}
                />
                <DetailCard
                  title="Taint evidence"
                  lines={
                    selectedLane.taint
                      ? [
                          `Source matches: ${selectedLane.taint.sourceMatches.length}`,
                          `Sink matches: ${selectedLane.taint.sinkMatches.length}`,
                          `Evidence paths: ${selectedLane.taint.evidencePaths.length}`,
                          `Pruned files: ${selectedLane.taint.prunedFiles.length}`,
                        ]
                      : ['No taint evidence for this lane yet']
                  }
                />
                <DetailCard
                  title="Tainted files"
                  lines={
                    selectedLane.taint?.taintedFiles.length
                      ? selectedLane.taint.taintedFiles.slice(0, 6)
                      : ['No tainted files identified']
                  }
                />
              </div>
            </div>
          ) : null}
        </section>

        <footer className="architect-footer">
          <div>
            <span className="architect-kicker">System manifest</span>
            <p>
              The landing page now runs through a backend scan job with real phases, then renders
              the architectural board from the returned manifests, modules, vendor signals, and
              mapped alternatives.
            </p>
          </div>

          <div className="architect-stamp">
            <span>Rendering mode</span>
            <strong>ISOMETRIC_COMPARE</strong>
            <span>{new Date().toLocaleDateString()}</span>
          </div>
        </footer>
      </main>
    </div>
  );
};

function RepoDistrict({
  zoneLabel,
  title,
  subtitle,
  repo,
  loading,
  fallbackSignals = [],
}: {
  zoneLabel: string;
  title: string;
  subtitle: string;
  repo: RepoIntel | null;
  loading: boolean;
  fallbackSignals?: Array<{ id: string; label: string; iconSlug: string | null }>;
}) {
  const signals = repo?.vendorSignals.length ? repo.vendorSignals : fallbackSignals.slice(0, 6);

  return (
    <div className={`district-card ${loading ? 'is-breathing' : ''}`}>
      <div className="district-card__label">{zoneLabel}</div>

      <div className="iso-panel">
        <div className="iso-panel__face">
          <div className="district-card__header">
            <div>
              <h2>{title}</h2>
              <p>{subtitle}</p>
            </div>
            <Boxes size={18} />
          </div>

          <div className="district-card__metrics">
            <MetricRow label="Modules" value={repo ? `${repo.modules.length}` : '--'} />
            <MetricRow label="Categories" value={repo ? `${repo.vendorSignals.length}` : '--'} />
            <MetricRow label="Stars" value={repo ? `${repo.stars}` : '--'} />
            <MetricRow label="Branch" value={repo ? repo.defaultBranch : '--'} />
          </div>

          <div className="district-card__stack">
            <span>// STACK_RESOURCES</span>
            <div className="district-card__tiles">
              {signals.length ? (
                signals.slice(0, 6).map((signal, index) => (
                  <div className="stack-tile" key={`${signal.id}-${index}`}>
                    <VendorGlyph
                      label={signal.label}
                      iconSlug={signal.iconSlug}
                      className="stack-tile__glyph"
                    />
                    <small>{signal.label}</small>
                  </div>
                ))
              ) : (
                <div className="district-card__placeholder">
                  {loading ? 'Resolving manifests...' : 'No repo scanned yet'}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricTower({
  value,
  label,
  hint,
}: {
  value: string;
  label: string;
  hint: string;
}) {
  return (
    <div className="metric-tower">
      <div className="metric-tower__value">{value}</div>
      <div className="metric-tower__label">{label}</div>
      <div className="metric-tower__hint">{hint}</div>
    </div>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DetailCard({ title, lines }: { title: string; lines: string[] }) {
  return (
    <div className="detail-card">
      <div className="architect-kicker">{title}</div>
      <div className="detail-card__lines">
        {lines.map((line, index) => (
          <p key={`${title}-${index}`}>{line}</p>
        ))}
      </div>
    </div>
  );
}

function defaultPhases(message = 'Waiting for scan', terminalStatus: ScanPhase['status'] = 'pending') {
  return [
    { key: 'validate', label: 'Normalize request', status: terminalStatus, detail: message },
    { key: 'source', label: 'Scan source repo', status: 'pending', detail: 'Waiting for source repo' },
    { key: 'taint', label: 'Trace taint surface', status: 'pending', detail: 'Waiting for code evidence' },
    { key: 'reference', label: 'Scan reference repo', status: 'pending', detail: 'Optional second repo' },
    { key: 'map', label: 'Build swap map', status: 'pending', detail: 'Waiting for vendor signals' },
  ] satisfies ScanPhase[];
}

function phaseValue(phases: ScanPhase[], key: string, completedValue?: number, fallbackValue?: number) {
  const phase = phases.find((item) => item.key === key);
  if (!phase) return '--';
  if (phase.status === 'completed') {
    return `${completedValue ?? fallbackValue ?? '--'}`;
  }
  if (phase.status === 'running') return '...';
  if (phase.status === 'error') return 'ERR';
  return '--';
}

function phaseHint(phases: ScanPhase[], key: string, fallback: string) {
  const phase = phases.find((item) => item.key === key);
  return phase?.detail ?? fallback;
}

function activeStatusLine(phases: ScanPhase[], loading: boolean) {
  const running = phases.find((phase) => phase.status === 'running');
  if (running) return `${running.label}: ${running.detail}`;
  if (loading) return 'Backend scan started.';
  const completed = phases.filter((phase) => phase.status === 'completed');
  if (completed.length) {
    return completed[completed.length - 1].detail;
  }
  return 'Submit one public GitHub repo to start the backend scan.';
}

function getLaneId(lane: SuggestionLane, index: number) {
  return `${lane.category}:${lane.source.id}:${lane.target.id}:${index}`;
}

export default App;

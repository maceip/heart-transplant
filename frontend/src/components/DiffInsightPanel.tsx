import React, { useEffect, useState } from 'react';
import { GitCompareArrows, Minus, Plus, RefreshCcw, Rows } from 'lucide-react';
import { wasmEngineService, type DiffStats } from '../services/wasm-engine.service';

interface DiffInsightPanelProps {
  original: string;
  modified: string;
}

export const DiffInsightPanel: React.FC<DiffInsightPanelProps> = ({
  original,
  modified,
}) => {
  const [html, setHtml] = useState<string>('');
  const [stats, setStats] = useState<DiffStats | null>(null);

  useEffect(() => {
    let active = true;

    Promise.all([
      wasmEngineService.renderDiff(original, modified),
      wasmEngineService.renderDiffStats(original, modified),
    ]).then(([nextHtml, nextStats]) => {
      if (!active) return;
      setHtml(nextHtml);
      setStats(nextStats);
    }).catch((error) => {
      console.error('WASM diff render failed', error);
    });

    return () => {
      active = false;
    };
  }, [modified, original]);

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-cyan-200/60 bg-white/80 shadow-[0_20px_60px_-28px_rgba(14,116,144,0.45)] backdrop-blur">
      <div className="flex items-center justify-between border-b border-cyan-100 bg-linear-to-r from-cyan-50 via-white to-amber-50 px-4 py-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-cyan-700">
            Wasm diff engine
          </p>
          <h3 className="mt-1 flex items-center gap-2 text-sm font-semibold text-slate-900">
            <GitCompareArrows className="h-4 w-4 text-cyan-600" />
            Structural patch preview
          </h3>
        </div>
        <div className="rounded-full border border-cyan-200 bg-white px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-700">
          emscripten
        </div>
      </div>

      {stats ? (
        <div className="grid grid-cols-4 gap-2 border-b border-cyan-100 px-4 py-3">
          <Metric icon={<Plus className="h-3.5 w-3.5" />} label="Added" value={stats.added} tone="emerald" />
          <Metric icon={<Minus className="h-3.5 w-3.5" />} label="Removed" value={stats.removed} tone="rose" />
          <Metric icon={<RefreshCcw className="h-3.5 w-3.5" />} label="Changed" value={stats.changed} tone="amber" />
          <Metric icon={<Rows className="h-3.5 w-3.5" />} label="Shared" value={stats.shared} tone="slate" />
        </div>
      ) : null}

      <div className="flex-1 overflow-auto px-4 py-4">
        <div
          className="g3mark-diff-root"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </div>
    </div>
  );
};

const toneClass: Record<string, string> = {
  emerald: 'bg-emerald-50 text-emerald-700',
  rose: 'bg-rose-50 text-rose-700',
  amber: 'bg-amber-50 text-amber-700',
  slate: 'bg-slate-100 text-slate-700',
};

const Metric: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: number;
  tone: keyof typeof toneClass;
}> = ({ icon, label, value, tone }) => (
  <div className={`rounded-xl px-3 py-2 ${toneClass[tone]}`}>
    <div className="flex items-center gap-1.5 text-[11px] font-semibold">
      {icon}
      {label}
    </div>
    <div className="mt-1 text-lg font-bold">{value}</div>
  </div>
);

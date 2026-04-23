import React from 'react';
import { Binary, Braces, Cpu, Layers3 } from 'lucide-react';

export const WasmRuntimeCard: React.FC = () => {
  return (
    <div className="rounded-2xl border border-slate-800 bg-[#111827] p-4 text-slate-100 shadow-2xl">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-cyan-400">
            Runtime stack
          </p>
          <h3 className="mt-1 text-sm font-semibold text-white">
            Monaco canvas + Emscripten engine
          </h3>
        </div>
        <div className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.22em] text-cyan-300">
          wasm online
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <RuntimePill icon={<Cpu className="h-3.5 w-3.5" />} label="Editor" value="Monaco host" />
        <RuntimePill icon={<Binary className="h-3.5 w-3.5" />} label="Parser" value="C / Wasm" />
        <RuntimePill icon={<Layers3 className="h-3.5 w-3.5" />} label="Diff" value="Emscripten" />
        <RuntimePill icon={<Braces className="h-3.5 w-3.5" />} label="Build" value="emcc pipeline" />
      </div>
    </div>
  );
};

const RuntimePill: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: string;
}> = ({ icon, label, value }) => (
  <div className="rounded-xl border border-slate-700 bg-slate-900/70 px-3 py-2">
    <div className="flex items-center gap-1.5 text-slate-400">
      {icon}
      {label}
    </div>
    <div className="mt-1 font-semibold text-slate-100">{value}</div>
  </div>
);

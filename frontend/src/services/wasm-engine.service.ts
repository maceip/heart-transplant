import initG3markEngine from '../wasm/generated/g3mark-engine.js';

type G3markModule = {
  UTF8ToString(pointer: number): string;
  _free(pointer: number): void;
  cwrap(
    name: string,
    returnType: 'number',
    args: Array<'string'>,
  ): (...args: string[]) => number;
};

export interface DiffStats {
  added: number;
  removed: number;
  changed: number;
  shared: number;
}

class WasmEngineService {
  private modulePromise: Promise<G3markModule> | null = null;

  private loadModule() {
    if (!this.modulePromise) {
      this.modulePromise = initG3markEngine() as Promise<G3markModule>;
    }
    return this.modulePromise;
  }

  async renderMarkdown(content: string) {
    const module = await this.loadModule();
    const pointer = module.cwrap('render_markdown', 'number', ['string'])(content);
    return this.takeString(module, pointer);
  }

  async renderDiff(original: string, modified: string) {
    const module = await this.loadModule();
    const pointer = module.cwrap('render_diff', 'number', ['string', 'string'])(
      original,
      modified,
    );
    return this.takeString(module, pointer);
  }

  async renderDiffStats(original: string, modified: string) {
    const module = await this.loadModule();
    const pointer = module.cwrap(
      'render_diff_stats',
      'number',
      ['string', 'string'],
    )(original, modified);
    const json = this.takeString(module, pointer);
    return JSON.parse(json) as DiffStats;
  }

  private takeString(module: G3markModule, pointer: number) {
    const value = module.UTF8ToString(pointer);
    module._free(pointer);
    return value;
  }
}

export const wasmEngineService = new WasmEngineService();

declare module '../wasm/generated/g3mark-engine.js' {
  type G3markModule = {
    UTF8ToString(pointer: number): string;
    _free(pointer: number): void;
    cwrap(name: string, returnType: string, args: string[]): (...values: string[]) => number;
  };

  export default function initG3markEngine(): Promise<G3markModule>;
}

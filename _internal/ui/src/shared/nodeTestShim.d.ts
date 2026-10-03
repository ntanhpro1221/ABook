// Chỉ cho test chạy trên Node (pdfPages*.test.ts đọc file mẫu trong tests/fixtures, hay PDF thật của máy): vài chữ ký tối thiểu, khỏi kéo @types/node vào gói giao diện.
declare module "node:fs" {
  export function readFileSync(path: URL | string): Uint8Array & { toString(encoding?: string): string };
  export function writeFileSync(path: string, data: string): void;
  export function mkdirSync(path: string, options?: { recursive?: boolean }): void;
}
declare module "node:path" {
  export const delimiter: string;
  export function basename(path: string): string;
  export function join(...parts: string[]): string;
}
declare const process: { env: Record<string, string | undefined> };
declare module "node:module" {
  export function createRequire(url: string | URL): { resolve(id: string): string };
}
declare module "node:url" {
  export function pathToFileURL(path: string): URL;
}

// Chỉ cho test chạy trên Node (test đọc file mẫu trong tests/fixtures): vài chữ ký tối thiểu, khỏi kéo @types/node vào gói giao diện.
declare module "node:fs" {
  export function readFileSync(path: URL | string): Uint8Array & { toString(encoding?: string): string };
  export function readFileSync(path: URL | string, encoding: string): string;
  export function existsSync(path: URL | string): boolean;
  export function readdirSync(path: URL | string): string[];
  export function statSync(path: URL | string): { isDirectory(): boolean };
  export function writeFileSync(path: string, data: string): void;
  export function mkdirSync(path: string, options?: { recursive?: boolean }): void;
}
declare module "node:path" {
  export const delimiter: string;
  export function basename(path: string): string;
  export function join(...parts: string[]): string;
}
declare const process: { env: Record<string, string | undefined> };
declare module "node:process" { export function cwd(): string; }
declare module "node:module" {
  export function createRequire(url: string | URL): { resolve(id: string): string };
}
declare module "node:url" {
  export function pathToFileURL(path: string): URL;
  export function fileURLToPath(url: URL | string): string;
}

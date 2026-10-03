// Chỉ cho test chạy trên Node (pdfPages.test.ts đọc file mẫu trong tests/fixtures): vài chữ ký tối thiểu, khỏi kéo @types/node vào gói giao diện.
declare module "node:fs" {
  export function readFileSync(path: URL | string): Uint8Array & { toString(encoding?: string): string };
}
declare module "node:module" {
  export function createRequire(url: string | URL): { resolve(id: string): string };
}
declare module "node:url" {
  export function pathToFileURL(path: string): URL;
}

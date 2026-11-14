export function fallbackSeed(link: string): number;
export function seedOf(link: string, info: Record<string, unknown>): number;
export function rgb(seed: number): Uint8Array;
export function bmp(seed: number): Uint8Array;
export function binary(seed: number): string;
export function base64(seed: number): string;

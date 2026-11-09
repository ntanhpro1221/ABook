import { vi } from "vitest";
import { scaledMs } from "./timeScale";

/** `vi.waitFor` với hạn rộng theo hệ số máy tải (mặc định của vitest là 1 giây - quá chật khi cả bộ test chạy song song). */
export function eventually<T>(callback: () => T | Promise<T>, options: { timeout?: number; interval?: number } = {}) {
  return vi.waitFor(callback, { timeout: scaledMs(options.timeout ?? 1000), interval: options.interval ?? 20 });
}

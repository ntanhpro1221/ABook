import { ApiError, type ApiInit, type ApiTransport } from "@/studio/api";
import { EbookLibrary } from "./plugins";

// Điện thoại không có server cục bộ: các lệnh sửa sách ("áp ngay" - tên sách, bìa, tên nhân vật, tên chương, nhạc nền) mà
// giao diện máy tính gửi tới `/api/books/<mã>/...` đi thẳng vào lõi native (LocalStudio.kt) với CÙNG đường dẫn và CÙNG JSON
// trả về - nên các màn hình sửa dùng chung cho cả hai nền tảng, không viết lại.

function splitQuery(path: string): [string, URLSearchParams] {
  const at = path.indexOf("?");
  return at < 0 ? [path, new URLSearchParams()] : [path.slice(0, at), new URLSearchParams(path.slice(at + 1))];
}

/** `studio` của plugin (hay bản giả khi thử) -> đường truyền cho `api()`. Mã >= 400 thành `ApiError` như `fetch` thật. */
export function localStudioTransport(
  studio: (options: { method: string; path: string; body?: unknown }) => Promise<{ status: number; body: unknown }>,
): ApiTransport {
  return async (path: string, init?: ApiInit) => {
    const [route, query] = splitQuery(path);
    const method = init?.method ?? "GET";
    // Lõi native không đọc chuỗi `?...`: tham số của một lệnh GET (vd. tìm bìa `?q=`) đi trong `body`.
    const sent = init?.body === undefined && method === "GET" && query.size ? Object.fromEntries(query) : init?.body;
    const reply = await studio({ method, path: route, body: sent });
    const body = reply.body && typeof reply.body === "object" ? (reply.body as Record<string, unknown>) : null;
    if (reply.status >= 400) {
      throw new ApiError(reply.status, typeof body?.error === "string" ? body.error : `Lỗi ${reply.status}`, body ?? {});
    }
    return reply.body ?? null;
  };
}

export const localStudio: ApiTransport = localStudioTransport((options) => EbookLibrary.studio(options));

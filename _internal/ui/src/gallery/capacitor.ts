import pluginSource from "@/android/plugins.ts?raw";
import { galleryState } from "./state";

// Capacitor giả: trang tin rằng nó chạy trong app Android. @capacitor/core đọc `window.Capacitor` LÚC NẠP - nó thấy `PluginHeaders` (như
// lõi native tự gắn) và gọi `nativePromise` / `nativeCallback` cho mọi phương thức có trong đó; ở đây hai hàm ấy đi vào các bản cài giả
// (phoneNative.ts). Phải cài TRƯỚC khi bất cứ mô-đun nào nhập @capacitor/core (main.tsx nạp app bằng import động sau bước này).

export type NativeImpl = Record<string, (options: Record<string, unknown>) => unknown>;
type Callback = (data: unknown, error?: unknown) => void;

/** Tên phương thức của các plugin (đọc từ chính android/plugins.ts, để phương thức mới thêm vào app cũng có lối vào). */
function methodsOf(source: string): string[] {
  return [...new Set([...source.matchAll(/^ {2}(\w+)\(/gm)].map((match) => match[1]))];
}

const APP_METHODS = ["exitApp", "getInfo", "getState", "getLaunchUrl", "minimizeApp", "toggleBackButtonHandler", "removeAllListeners"];

const listeners = new Map<string, { plugin: string; event: string; callback: Callback }>();
let nextCallback = 1;

/** Phát một sự kiện của plugin tới mọi người nghe (vd `EbookPlayer` "state"). */
export function emitNative(plugin: string, event: string, data: unknown): void {
  for (const listener of listeners.values()) if (listener.plugin === plugin && listener.event === event) listener.callback(data);
}

export function installCapacitor(impls: Record<string, NativeImpl>): void {
  const names = methodsOf(pluginSource);
  const header = (name: string, methods: string[]) => ({
    name,
    methods: [...new Set([...methods, ...Object.keys(impls[name] ?? {}), "addListener", "removeListener", "removeAllListeners"])].map((method) => ({
      name: method,
      rtype: method === "addListener" ? "callback" : "promise",
    })),
  });
  // @capacitor/core đọc globalThis (trong trình duyệt là window; trong test happy-dom có thể khác window).
  const win = globalThis as unknown as Record<string, unknown>;
  win.CapacitorCustomPlatform = { name: "android", plugins: {} };
  win.Capacitor = {
    PluginHeaders: [header("EbookPlayer", names), header("EbookLibrary", names), header("ReadAloud", names), header("App", APP_METHODS)],
    // Đường dẫn file trên máy -> địa chỉ phục vụ được: bìa nằm trong thư mục tĩnh của phòng trưng bày, còn lại không có file thật.
    convertFileSrc: (path: string) => {
      const cover = path.match(/(covers\/[\w-]+\.svg)$/);
      return cover ? `./${cover[1]}` : `about:blank#${encodeURIComponent(path)}`;
    },
    nativePromise: async (plugin: string, method: string, options: Record<string, unknown> = {}) => {
      if (method === "removeListener") {
        listeners.delete(String(options.callbackId));
        return undefined;
      }
      if (method === "removeAllListeners") {
        for (const [id, listener] of listeners) if (listener.plugin === plugin) listeners.delete(id);
        return undefined;
      }
      const impl = impls[plugin]?.[method];
      if (!impl) {
        galleryState.missing.add(`${plugin}.${method}`);
        return {};
      }
      return impl(options);
    },
    nativeCallback: (plugin: string, method: string, options: { eventName?: string } = {}, callback: Callback) => {
      const id = String(nextCallback++);
      if (method === "addListener") listeners.set(id, { plugin, event: options.eventName ?? "", callback });
      return id;
    },
  };
}

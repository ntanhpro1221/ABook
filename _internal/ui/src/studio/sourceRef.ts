/**
 * Tên đọc được của một nguồn truyện. Studio từ xa không biết đường dẫn nào trên máy tính nên nguồn là tham chiếu máy tính đưa
 * (`up:<tầng>/<tầng>/<file>` cho file đã gửi lên, `ref:<kiểu>:<mã cuốn>:<số>:<tên file đã mã hoá>` cho chương của cuốn có sẵn): người
 * dùng chỉ thấy TÊN, không bao giờ thấy chuỗi tham chiếu.
 */
const REF = /^(?:up:|ref:)/;

/** Chuỗi này là tham chiếu của máy tính (không phải đường dẫn) ? */
export function isSourceRef(source: string): boolean {
  return REF.test(source);
}

/** Tên file / thư mục cuối của nguồn: đường dẫn Windows, đường kiểu "/", hay tham chiếu. */
export function sourceName(source: string): string {
  const ref = /^ref:[^:]*:[^:]*:\d+:(.*)$/s.exec(source);
  if (ref) {
    try {
      return decodeURIComponent(ref[1]);
    } catch {
      return ref[1];
    }
  }
  const body = source.startsWith("up:") ? source.slice(3) : source;
  return body.split(/[\\/]/).filter(Boolean).pop() ?? source;
}

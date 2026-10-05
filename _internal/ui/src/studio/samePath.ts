/** Khoá so sánh đường dẫn: dấu gạch "\" và "/" như nhau, bỏ gạch cuối, và phân biệt hoa/thường chỉ với đường kiểu Windows
 *  ("D:\..." hay "\\máy\..."). Đường người dùng gõ ("D:/Truyện/whole.txt") và đường máy quét ("D:\Truyện\whole.txt") là một file. */
export function pathKey(path: string): string {
  const slashed = path.trim().replace(/\\/g, "/");
  const unc = slashed.startsWith("//");
  const collapsed = slashed.replace(/\/{2,}/g, "/");
  const joined = unc ? `/${collapsed}` : collapsed;
  const trimmed = joined.length > 1 ? joined.replace(/\/+$/, "") : joined;
  return /^[A-Za-z]:(\/|$)|^\/\//.test(trimmed) ? trimmed.toLowerCase() : trimmed;
}

export function samePath(a: string, b: string): boolean {
  return pathKey(a) === pathKey(b);
}

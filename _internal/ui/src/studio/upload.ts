import { api } from "@/studio/api";

/**
 * Studio từ xa: gửi các chương TXT từ máy đang xem (điện thoại, máy tính bảng) vào thư viện của máy tính
 * (`POST /api/sources/upload`, webui/actions.upload_source), từng file một, rồi trả thư mục trên máy tính để trình tạo
 * sách đi tiếp như khi chọn thư mục. Gửi byte nguyên vẹn (base64): bảng mã do dây chuyền nhận, như với file trên máy.
 */
export async function uploadChapters(files: File[], onProgress: (done: number, total: number) => void): Promise<string> {
  const chapters = files.filter((file) => file.name.toLowerCase().endsWith(".txt"));
  if (!chapters.length) throw new Error("Chọn các file .txt - mỗi file là một chương");
  const now = new Date();
  const two = (value: number) => String(value).padStart(2, "0");
  // Mỗi lần gửi một thư mục riêng (thêm mã ngẫu nhiên): hai lần gửi trong cùng phút không trộn chương vào nhau.
  const tag = Math.random().toString(36).slice(2, 6);
  const folder = `Tải lên ${two(now.getDate())}-${two(now.getMonth() + 1)}-${now.getFullYear()} ${two(now.getHours())}h${two(now.getMinutes())} ${tag}`;
  let target = "";
  for (const [index, file] of chapters.entries()) {
    const result = await api<{ folder: string }>("/api/sources/upload", {
      method: "POST",
      body: { folder, name: file.name, data: await toBase64(file) },
    });
    target = result.folder;
    onProgress(index + 1, chapters.length);
  }
  return target;
}

async function toBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let start = 0; start < bytes.length; start += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(start, start + 0x8000));
  }
  return btoa(binary);
}

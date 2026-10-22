import type { RemoteBook } from "./plugins";

export function hasNewAudio(book: Pick<RemoteBook, "downloaded" | "audioVersion" | "localAudioVersion">): boolean {
  return book.downloaded && Boolean(book.audioVersion) && book.audioVersion !== book.localAudioVersion;
}

/** Sách đã tải mà máy tính vừa căn thêm chữ sáng theo giọng đọc (hay căn lại): dấu `wordsVersion` của máy tính khác dấu đã lưu theo sách. Máy tính
 *  chưa căn chữ nào (không có dấu) thì không bao giờ có gì mới - sách không đổi thì không tải lại. */
export function hasNewWords(book: Pick<RemoteBook, "downloaded" | "wordsVersion" | "localWordsVersion">): boolean {
  return book.downloaded && Boolean(book.wordsVersion) && book.wordsVersion !== (book.localWordsVersion ?? "");
}

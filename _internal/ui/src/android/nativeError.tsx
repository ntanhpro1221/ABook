import { toast } from "@/shared/toast";
import { ErrorDetails } from "@/shared/ErrorDetails";

/** Mã lỗi Capacitor khi máy kia trả 401 - nó đã thôi ghép điện thoại này (NetErrors.UNPAIRED), không phải tắt máy hay khác mạng. */
export const UNPAIRED = "UNPAIRED";

/** Lỗi từ lõi native (LibraryPlugin.fail): `message` đã là câu cho người nghe theo loại lỗi mạng; chữ gốc của Java nằm ở `data.technical`
 *  (soát a68 lỗi 4). */
export function nativeError(error: unknown): { message: string; code?: string; technical?: string } {
  const value = error as { message?: unknown; code?: unknown; data?: { technical?: unknown } } | null;
  return {
    message: typeof value?.message === "string" && value.message ? value.message : String(error),
    code: typeof value?.code === "string" ? value.code : undefined,
    technical: typeof value?.data?.technical === "string" ? value.data.technical : undefined,
  };
}

export function isUnpaired(error: unknown): boolean {
  return nativeError(error).code === UNPAIRED;
}

/** Lời báo lỗi kèm "Chi tiết" gập lại khi có chữ kỹ thuật. */
export function errorDescription(message: string, technical?: string) {
  return technical ? (
    <>
      {message}
      <ErrorDetails technical={technical} />
    </>
  ) : (
    message
  );
}

export function toastNativeError(title: string, error: unknown) {
  const { message, technical } = nativeError(error);
  toast.error(title, { description: errorDescription(message, technical) });
}

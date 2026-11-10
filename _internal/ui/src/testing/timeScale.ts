// Hạn chờ theo giờ thật của test: một chỗ duy nhất, nhân với hệ số máy tải (Python: tests/timing.py, Kotlin: TestTime.kt).
// `ABOOK_TEST_TIME_SCALE` (mặc định 5) - máy chậm hơn nữa thì đặt cao hơn. Chỉ dùng cho HẠN CHỜ ("không quá N ms"), không
// cho cận dưới ("đã chờ ít nhất N ms") hay hẹn giờ giả (vi.advanceTimersByTime): hai thứ ấy không đổi theo tải máy.
const raw = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.ABOOK_TEST_TIME_SCALE;

export const TIME_SCALE = Math.max(1, Number(raw) || 5);

export const scaledMs = (ms: number): number => ms * TIME_SCALE;

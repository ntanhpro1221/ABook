import { beforeEach, expect, it, vi } from "vitest";
import type { ReactElement } from "react";
const h = vi.hoisted(() => ({ draft: null as unknown, data: { sleepSchedule: null as unknown }, update: vi.fn(), error: vi.fn() }));
vi.mock("react", async (original) => ({ ...await original<typeof import("react")>(), useState: () => [h.draft, (value: unknown) => { h.draft = value; }] }));
vi.mock("@/studio/data", () => ({ usePreferences: () => ({ data: h.data, update: h.update }) }));
vi.mock("sonner", () => ({ toast: { error: h.error } }));
import { SleepSchedule } from "./SleepSchedule";
import { Switch } from "./PhoneSync";
import { MotionPresence } from "@/shared/MotionPresence";
import { TimeSelect } from "@/shared/ui";
function nodes(tree: unknown): ReactElement<Record<string, unknown>>[] {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  if (!tree || typeof tree !== "object" || !("props" in tree)) return [];
  const node = tree as ReactElement<Record<string, unknown>>;
  return [node, ...nodes(node.props.children)];
}
const tree = () => nodes(SleepSchedule());
const toggle = () => tree().find((el) => el.type === Switch)!.props;
beforeEach(() => { h.draft = null; h.data = { sleepSchedule: null }; vi.clearAllMocks(); });
it("PUT chưa về: công tắc đổi ngay, ba ô lịch hiện có motion và chặn gửi lặp", () => {
  (toggle().onCheckedChange as (value: boolean) => void)(true);
  expect(toggle().checked).toBe(true);
  expect(toggle().disabled).toBe(true);
  expect(tree().filter((el) => el.type === TimeSelect).map((el) => el.props.disabled)).toEqual([true, true]);
  expect(tree().find((el) => el.type === MotionPresence)?.props.open).toBe(true);
  expect(h.update.mock.calls[0][0]).toEqual({ sleepSchedule: { from: "22:00", to: "06:00", minutes: 30 } });
});
it("lưu lỗi: trả công tắc về lịch thực, không kẹt trạng thái chờ", () => {
  (toggle().onCheckedChange as (value: boolean) => void)(true);
  h.update.mock.calls[0][1].onError(new Error("offline"));
  expect(toggle().checked).toBe(false);
  expect(toggle().disabled).toBe(false);
});
it("máy chủ trả 200 nhưng bỏ trường lịch: báo lỗi rõ, không giả thành công", () => {
  (toggle().onCheckedChange as (value: boolean) => void)(true);
  h.update.mock.calls[0][1].onSuccess({ sleepSchedule: null });
  expect(h.error).toHaveBeenCalledWith("Chưa đổi được lịch đêm", expect.anything());
  expect(toggle().checked).toBe(false);
});
it("lịch trả về cùng giá trị nhưng thứ tự khoá khác vẫn lưu thành công", () => {
  (toggle().onCheckedChange as (value: boolean) => void)(true);
  h.update.mock.calls[0][1].onSuccess({ sleepSchedule: { minutes: 30, to: "06:00", from: "22:00" } });
  expect(h.error).not.toHaveBeenCalled();
  expect(h.draft).toBeNull();
});

import { useState } from "react";
import { toast } from "@/shared/toast";
import { MotionPresence } from "@/shared/MotionPresence";
import { SettingsRow } from "@/shared/SettingsNav";
import { Select, TimeSelect } from "@/shared/ui";
import { usePreferences } from "@/studio/data";
import type { Preferences } from "@/studio/api";
import { Switch } from "./Switch";

type Schedule = Preferences["sleepSchedule"];
const DEFAULT_SCHEDULE = { from: "22:00", to: "06:00", minutes: 30 };

/** Phản hồi ngay cả khi PUT chậm; chỉ nhận thành công khi server trả đúng lịch đã gửi. */
export function SleepSchedule() {
  const { data, update } = usePreferences();
  const [draft, setDraft] = useState<{ value: Schedule } | null>(null);
  const schedule = draft ? draft.value : data?.sleepSchedule;
  const change = (value: Schedule) => {
    if (!data || draft !== null) return;
    setDraft({ value });
    update({ sleepSchedule: value }, {
      onSuccess: (saved) => {
        setDraft(null);
        const actual = saved.sleepSchedule;
        const matches = value === null ? actual === null : actual?.from === value?.from && actual?.to === value?.to && actual?.minutes === value?.minutes;
        if (!matches) toast.error("Chưa đổi được lịch đêm", { description: "Máy chủ chưa nhận lịch. Thử lại sau." });
      },
      onError: () => setDraft(null), // usePreferences báo nguyên nhân lưu thất bại.
    });
  };
  return <>
    <SettingsRow label="Lịch đêm" hint="Nghe trong khung giờ này thì tự hẹn giờ.">
      <Switch id="sleep-schedule" label="Lịch đêm" checked={Boolean(schedule)} ariaDisabled={!data || draft !== null} onCheckedChange={(on) => change(on ? DEFAULT_SCHEDULE : null)} />
    </SettingsRow>
    <MotionPresence open={Boolean(schedule)}>
      {schedule && <div className="flex flex-wrap items-center gap-2 py-3 text-sm">
        <TimeSelect ariaDisabled={draft !== null} label="Từ" value={schedule.from} onChange={(from) => change({ ...schedule, from })} />
        <span className="text-fg-2">đến</span>
        <TimeSelect ariaDisabled={draft !== null} label="Đến" value={schedule.to} onChange={(to) => change({ ...schedule, to })} />
        <span className="text-fg-2">hẹn</span>
        <Select inline aria-label="Số phút hẹn" value={schedule.minutes} aria-disabled={draft !== null || undefined}
          onPointerDown={(event) => { if (draft !== null) event.preventDefault(); }}
          onKeyDown={(event) => { if (draft !== null && event.key !== "Tab") event.preventDefault(); }}
          onChange={(event) => change({ ...schedule, minutes: Number(event.target.value) })} className="aria-disabled:opacity-50">
          {[15, 30, 45, 60].map((minutes) => <option key={minutes} value={minutes}>{minutes} phút</option>)}
        </Select>
      </div>}
    </MotionPresence>
  </>;
}

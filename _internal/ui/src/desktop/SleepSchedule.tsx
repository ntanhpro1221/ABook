import { useState } from "react";
import { toast } from "@/shared/toast";
import { MotionPresence } from "@/shared/MotionPresence";
import { SettingsRow } from "@/shared/SettingsNav";
import { TimeSelect } from "@/shared/ui";
import { usePreferences } from "@/studio/data";
import type { Preferences } from "@/studio/api";
import { Switch } from "./PhoneSync";

type Schedule = Preferences["sleepSchedule"];
const DEFAULT_SCHEDULE = { from: "22:00", to: "06:00", minutes: 30 };

/** Phản hồi ngay cả khi PUT chậm; chỉ nhận thành công khi server trả đúng lịch đã gửi. */
export function SleepSchedule() {
  const { data, update } = usePreferences();
  const [draft, setDraft] = useState<{ value: Schedule } | null>(null);
  const schedule = draft ? draft.value : data?.sleepSchedule;
  const change = (value: Schedule) => {
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
    <SettingsRow label="Lịch đêm" hint={draft ? "Đang lưu…" : "Nghe trong khung giờ này thì tự hẹn giờ."}>
      <Switch id="sleep-schedule" label="Lịch đêm" checked={Boolean(schedule)} disabled={!data || draft !== null} onCheckedChange={(on) => change(on ? DEFAULT_SCHEDULE : null)} />
    </SettingsRow>
    <MotionPresence open={Boolean(schedule)}>
      {schedule && <div className="flex flex-wrap items-center gap-2 px-4 py-3 text-sm">
        <TimeSelect disabled={draft !== null} label="Từ" value={schedule.from} onChange={(from) => change({ ...schedule, from })} className="h-9 rounded-lg border border-line bg-panel px-2" />
        <span className="text-fg-2">đến</span>
        <TimeSelect disabled={draft !== null} label="Đến" value={schedule.to} onChange={(to) => change({ ...schedule, to })} className="h-9 rounded-lg border border-line bg-panel px-2" />
        <span className="text-fg-2">hẹn</span>
        <select aria-label="Số phút hẹn" value={schedule.minutes} disabled={draft !== null} onChange={(event) => change({ ...schedule, minutes: Number(event.target.value) })} className="h-9 rounded-lg border border-line bg-panel px-2">
          {[15, 30, 45, 60].map((minutes) => <option key={minutes} value={minutes}>{minutes} phút</option>)}
        </select>
      </div>}
    </MotionPresence>
  </>;
}

import { Presence } from "../shared/MotionPresence";
import { S } from "../shared/strings.generated";
import { useState } from "react";
import { toast } from "@/shared/toast";
import { MotionPresence } from "@/shared/MotionPresence";
import { SettingsRow } from "@/shared/SettingsNav";
import { TimeSelect } from "@/shared/ui";
import { ValuePicker } from "@/shared/ValuePicker";
import { VALUE_SPECS } from "@/shared/valuePickerLogic";
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
        if (!matches) toast.error(S.s_chua_doi_duoc_lich_dem_eec117e2, { description: S.s_may_chu_chua_nhan_lich_thu_lai_sau_01362531 });
      },
      onError: () => setDraft(null), // usePreferences báo nguyên nhân lưu thất bại.
    });
  };
  return <>
    <SettingsRow label={S.s_lich_dem_5f61612f} hint={S.s_may_ranh_2_phut_trong_khung_gio_nay_moi_tu_93ce72b6}>
      <Switch id="sleep-schedule" label={S.s_lich_dem_5f61612f} checked={Boolean(schedule)} ariaDisabled={!data || draft !== null} onCheckedChange={(on) => change(on ? DEFAULT_SCHEDULE : null)} />
    </SettingsRow>
    <MotionPresence open={Boolean(schedule)}>
      {<Presence>{schedule && <div className="flex flex-wrap items-center gap-2 py-3 text-sm">
        <TimeSelect ariaDisabled={draft !== null} label={S.s_tu_c2634aaa} value={schedule.from} onChange={(from) => change({ ...schedule, from })} />
        <span className="text-fg-2">{S.s_den_80b69c87}</span>
        <TimeSelect ariaDisabled={draft !== null} label={S.s_den_4f14ac22} value={schedule.to} onChange={(to) => change({ ...schedule, to })} />
      </div>}</Presence>}
      {<Presence>{schedule && <ValuePicker
        dense
        className="pb-3"
        spec={VALUE_SPECS.scheduleMinutes}
        value={schedule.minutes}
        busy={draft !== null}
        label={S.s_hen_244e495e}
        format={(minutes) => S.s_0_phut_2596d212(minutes)}
        onChange={(minutes) => change({ ...schedule, minutes })}
      />}</Presence>}
    </MotionPresence>
  </>;
}

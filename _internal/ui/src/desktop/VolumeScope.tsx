import { S } from "@/shared/strings.generated";
import { Select } from "@/shared/ui";

export function VolumeScope({ volumes, value, onChange }: {
  volumes: { id: number; title: string }[]; value: number | null; onChange: (id: number | null) => void;
}) {
  return <label className="mb-3 flex items-center gap-3 text-sm">
    <span className="font-medium">{S.s_volumes}</span>
    <Select inline aria-label={S.s_volumes} value={value ?? ""} onChange={event => onChange(event.target.value ? Number(event.target.value) : null)}>
      <option value="">{S.s_volume_all}</option>
      {volumes.map(volume => <option key={volume.id} value={volume.id}>{volume.title}</option>)}
    </Select>
  </label>;
}

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/studio/api";
import { S } from "@/shared/strings.generated";
import { Button, Dialog, DialogActions, InlineError } from "@/shared/ui";
import { AnimatedRows, MotionPresence } from "@/shared/MotionPresence";
import { refreshAfterEdit } from "./EditBook";
import type { ListenBook } from "./model";

type Draft = { id: number; number: number; title: string; start: number; image?: string | null };

/** Volume edits only move boundaries; all chapter identities stay in global order. */
/** Id của quyển thêm mới: lớn hơn mọi id đã nạp lẫn đang có. */
export function nextVolumeId(rows: { id: number }[], loaded: { id: number }[] | undefined): number {
  return Math.max(0, ...rows.map(row => row.id), ...(loaded ?? []).map(volume => volume.id)) + 1;
}

/** Còn thêm được quyển: dưới 99 quyển và còn chương sau chương đầu của quyển cuối. */
export function canAddVolume(rows: { start: number }[], chapters: number): boolean {
  return rows.length < 99 && (rows.at(-1)?.start ?? 0) + 1 <= chapters;
}

export function VolumeEditor({ book }: { book: ListenBook }) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<Draft[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pickers = useRef<Record<number, HTMLInputElement | null>>({});
  const chapters = book.chapters ?? [];
  const edit = () => {
    setRows((book.volumes ?? [{ id: 1, number: 1, title: S.s_volume_number(1), chapters }]).map(volume => ({
      id: volume.id, number: volume.number, title: volume.title,
      start: chapters.findIndex(chapter => chapter.id === volume.chapters[0]?.id) + 1,
    })));
    setError(""); setOpen(true);
  };
  const change = (id: number, patch: Partial<Draft>) => setRows(previous => previous.map(row => row.id === id ? { ...row, ...patch } : row));
  const save = async () => {
    if (busy) return;
    setBusy(true); setError("");
    try {
      if (!rows.length || rows[0].start !== 1 || rows.some((row, index) => !row.title.trim() || row.title.length > 240
        || !Number.isInteger(row.number) || row.number < 1 || row.number > 9999 || !Number.isInteger(row.start)
        || row.start > chapters.length || (index > 0 && row.start <= rows[index - 1].start))) throw new Error(S.s_volume_invalid);
      const definitions = rows.map((row, index) => ({ id: row.id, number: row.number, title: row.title,
        chapters: chapters.slice(row.start - 1, (rows[index + 1]?.start ?? chapters.length + 1) - 1).map(chapter => chapter.id) }));
      await api(`/api/books/${book.id}/volumes`, { method: "PUT", body: { volumes: definitions } });
      for (const row of rows) if (row.image !== undefined) await api(`/api/books/${book.id}/volumes/${row.id}/cover`, { method: "PUT", body: { image: row.image } });
      refreshAfterEdit(client, book.id); setOpen(false);
    } catch (failure) { setError(String(failure instanceof Error ? failure.message : failure)); }
    finally { setBusy(false); }
  };
  return <>
    <Button variant="ghost" onClick={edit}>{S.s_volume_manage}</Button>
    <Dialog open={open} onOpenChange={value => { if (!busy) setOpen(value); }} title={S.s_volume_manage}>
      <AnimatedRows items={rows} keyOf={row => String(row.id)} className="divide-y divide-line">
        {row => <div className="space-y-2 py-3">
          <label className="block text-sm">{S.s_volume_title}<input value={row.title} onChange={event => change(row.id, { title: event.target.value })} className="mt-1 w-full rounded-control border border-line bg-panel p-2" /></label>
          <div className="flex gap-3">
            <label className="flex-1 text-sm">{S.s_volume_number(row.number)}<input type="number" min={1} max={9999} value={row.number} onChange={event => change(row.id, { number: Number(event.target.value) })} className="w-full rounded-control border border-line bg-panel p-2" /></label>
            <label className="flex-1 text-sm">{S.s_volume_first_chapter}<input type="number" min={1} max={chapters.length} disabled={row.id === rows[0]?.id} value={row.start} onChange={event => change(row.id, { start: Number(event.target.value) })} className="w-full rounded-control border border-line bg-panel p-2" /></label>
          </div>
          <Button size="sm" variant="ghost" className="flex w-fit justify-start px-0 text-left" disabled={busy} onClick={() => pickers.current[row.id]?.click()}>{S.s_volume_cover}</Button>
          <input ref={input => { pickers.current[row.id] = input; }} className="hidden" aria-label={S.s_volume_cover} type="file" accept="image/*" disabled={busy} onChange={event => {
            const file = event.target.files?.[0]; if (!file) return;
            const reader = new FileReader(); reader.onload = () => change(row.id, { image: String(reader.result) }); reader.readAsDataURL(file);
          }} />
          <Button size="sm" variant="ghost" className="flex w-fit justify-start px-0 text-left" onClick={() => change(row.id, { image: null })}>{S.s_volume_book_cover}</Button>
          <MotionPresence open={row.id !== rows[0]?.id}><Button size="sm" variant="ghost" className="flex w-fit justify-start px-0 text-left" onClick={() => setRows(rows.filter(other => other.id !== row.id))}>{S.s_xoa_777195ab}</Button></MotionPresence>
        </div>}
      </AnimatedRows>
      {/* Id mới lớn hơn mọi id đã nạp lẫn đang có (quyển vừa xoá không bị tái dùng - bìa riêng ghép theo id); quyển mới bắt đầu sau chương đầu của quyển cuối,
          hết chương thì không thêm - như máy tính và điện thoại (soát 0.4.173 B13c, B13d). */}
      <Button variant="ghost" className="justify-start px-0" disabled={!canAddVolume(rows, chapters.length)} onClick={() => setRows([...rows, { id: nextVolumeId(rows, book.volumes), number: rows.length + 1, title: S.s_volume_number(rows.length + 1), start: (rows.at(-1)?.start ?? 0) + 1 }])}>{S.s_volume_add}</Button>
      <InlineError message={error} open={Boolean(error)} onRetry={() => void save()} />
      <DialogActions><Button variant="primary" onClick={save} loading={busy} disabled={busy || !rows.length}>{S.s_volume_save}</Button></DialogActions>
    </Dialog>
  </>;
}

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { S } from "@/shared/strings.generated";
import { PersonAvatar } from "@/shared/PersonAvatar";
import { MotionPresence } from "@/shared/MotionPresence";
import { Button, Sheet, InlineError } from "@/shared/ui";
import type { CastMember } from "@/listen/model";
import { api } from "./api";

/** An explicit choice owns the portrait until the user chooses again. */
export function AvatarEditor({ bookId, person }: { bookId: string; person: CastMember }) {
  const [open, setOpen] = useState(false);
  return <Sheet open={open} onOpenChange={setOpen} title={S.s_avatar_portrait}
    trigger={<button type="button" aria-label={`${S.s_avatar_portrait}: ${person.displayName}`} className="shrink-0 rounded-full">
      <PersonAvatar name={person.name} avatar={person.avatar} bookId={bookId} />
    </button>}>
    <AvatarChoices bookId={bookId} person={person} />
  </Sheet>;
}

/** Mounted only inside the open sheet: rows of the cast list do not each hold a status query. */
function AvatarChoices({ bookId, person }: { bookId: string; person: CastMember }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const client = useQueryClient();
  const path = `/api/books/${bookId}/avatar`;
  const state = useQuery({ queryKey: ["avatar-status", bookId, person.name],
    queryFn: () => api<{ available: boolean; pending?: boolean; error?: string }>(`${path}?character=${encodeURIComponent(person.name)}`),
    refetchInterval: (query) => query.state.data?.pending ? 1000 : false });
  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: ["cast", bookId] }),
    client.invalidateQueries({ queryKey: ["casting", bookId] }),
  ]);
  async function change(action: string, data?: string) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      await api(path, { method: "POST", body: { character: person.name, action, data } });
      await client.invalidateQueries({ queryKey: ["avatar-status", bookId, person.name] });
      await refresh();
    } catch (failure) { setError(failure instanceof Error ? failure.message : String(failure)); }
    finally { setBusy(false); }
  }
  // A finished background request refreshes the cast while the editor remains reviewable.
  const lastPending = useRef(false);
  const pending = Boolean(state.data?.pending);
  useEffect(() => {
    if (lastPending.current && !pending) void refresh();
    lastPending.current = pending;
  }, [pending]); // eslint-disable-line react-hooks/exhaustive-deps
  const problem = error || state.data?.error || "";
  return <div className="flex flex-col items-start gap-3">
    <PersonAvatar name={person.name} avatar={person.avatar} bookId={bookId} size={96} />
    <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" hidden disabled={busy} onChange={(event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => void change("upload", String(reader.result).split(",")[1]);
      reader.readAsDataURL(file); event.target.value = "";
    }} />
    <Button variant="ghost" disabled={busy} onClick={() => input.current?.click()}>{S.s_chon_anh_41ecf092}</Button>
    <Button variant="ghost" loading={busy} disabled={busy || !state.data?.available || pending} onClick={() => change("generate")}>
      {pending ? S.s_avatar_generating : S.s_avatar_generate}
    </Button>
    <MotionPresence open={state.isSuccess && !state.data.available}><p className="text-sm text-fg-2">{S.s_avatar_unavailable}</p></MotionPresence>
    <Button variant="ghost" loading={busy} disabled={busy} onClick={() => change("pattern")}>{S.s_avatar_pattern}</Button>
    <MotionPresence open={Boolean(problem)}><InlineError message={problem} onRetry={() => void state.refetch()} /></MotionPresence>
  </div>;
}

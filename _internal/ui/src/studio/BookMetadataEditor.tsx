import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { BookMetadataDetails, BookMetadataFields, metadataOf, type BookMetadata } from "@/listen/BookMetadata";
import { Button, Dialog } from "@/shared/ui";
import { S } from "@/shared/strings.generated";
import { toast } from "@/shared/toast";
import { api } from "./api";

export function BookMetadataEditor({ book }: { book: BookMetadata & { id: string } }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(() => metadataOf(book));
  const client = useQueryClient();
  const save = useMutation({
    mutationFn: () => api(`/api/books/${book.id}/metadata`, { method: "PUT", body: draft }),
    onSuccess: () => { void client.invalidateQueries(); setOpen(false); toast.success(S.s_bookmeta_saved); },
    onError: (error: Error) => toast.error(S.s_bookmeta_save_error, { description: error.message }),
  });
  return <>
    <BookMetadataDetails book={book} />
    <Button variant="ghost" icon={Pencil} onClick={() => { setDraft(metadataOf(book)); setOpen(true); }}>{S.s_sua_thong_tin_17e4a8a6}</Button>
    <Dialog open={open} onOpenChange={setOpen} title={S.s_sua_thong_tin_17e4a8a6}>
      <form className="space-y-4" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
        <BookMetadataFields value={draft} onChange={setDraft} />
        <Button type="submit" variant="primary" loading={save.isPending}>{S.s_bookmeta_save}</Button>
      </form>
    </Dialog>
  </>;
}

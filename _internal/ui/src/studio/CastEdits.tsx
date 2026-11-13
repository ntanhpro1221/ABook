import { Presence } from "../shared/MotionPresence";
import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { useQueryClient } from "@tanstack/react-query";
import { useId, useEffect, useState } from "react";
import { toast } from "@/shared/toast";
import { cleanName } from "@/listen/BookScreen";
import type { CastMember } from "@/listen/model";
import { formatNumber } from "@/shared/format";
import { DialogActions, Button, Dialog, ChoiceRow } from "@/shared/ui";
import { api } from "./api";
import { refreshAfterDecision, UNDO_MS, undoAction } from "./decisions";
import { voiceToUse } from "./MergePeople";

import { Reveal } from "../shared/MotionPresence";
// Tab Nhân vật: "Đổi tên" và "Đổi giới tính" của một người.
// - Đổi tên chỉ là cái tên trên màn hình (POST /characters/rename -> names.json): không đổi giọng hay audio, có hiệu lực ngay.
// - Đổi giới tính đi đúng đường của thẻ "Nam hay nữ" (POST /voice): một thay đổi chờ "Áp dụng thay đổi", hoàn tác được.

export function RenamePersonDialog({
  bookId,
  person,
  onClose,
  onSaved,
}: {
  bookId: string;
  person: CastMember | null;
  onClose: () => void;
  /** Gọi sau khi đổi tên xong - trang nghe làm mới thư viện, chữ đọc theo, dàn nhân vật (listen/EditBook.tsx). */
  onSaved?: () => void;
}) {
  const dialogForm1 = useId();
  const client = useQueryClient();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => setValue(person ? cleanName(person.displayName) : ""), [person]);
  const save = async (next: string) => {
    if (!person) return;
    setBusy(true);
    try {
      const answer = await api<{ name: string; renamed: boolean }>(`/api/books/${bookId}/characters/rename`, {
        method: "POST",
        body: { character: person.name, name: next },
      });
      refreshAfterDecision(client, bookId);
      onSaved?.();
      toast.success(answer.renamed ? S.s_da_doi_ten_thanh_0_2ce2cbcd(cleanName(answer.name)) : S.s_da_tro_ve_ten_goc_0_82af9bce(cleanName(answer.name)));
      onClose();
    } catch (error) {
      toast.error(S.s_chua_doi_duoc_ten_ad5b4df1, { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const name = person ? cleanName(person.displayName) : "";
  return (
    <Dialog footer={<DialogActions>
          <Reveal when={person?.originalName}><Button type="button" variant="ghost" disabled={busy} onClick={() => void save("")}>{S.s_ve_ten_goc_643cd2e0}</Button></Reveal>
          <Button type="button" variant="ghost" onClick={onClose}>{S.s_thoi_e68f9e88}</Button>
          <Button type="submit" form={dialogForm1} variant="primary" loading={busy} disabled={!value.trim()}>{S.s_luu_e91f26c0}</Button>
        </DialogActions>}
      open={person !== null}
      onOpenChange={(open) => !open && onClose()}
      width="max-w-md"
      title={S.s_doi_ten_0_d6845bbc(name)}
      description={S.s_chi_doi_ten_hien_thi_giu_giong_va_audio_1f7110c8}
    >
      <form id={dialogForm1}
        onSubmit={(event) => {
          event.preventDefault();
          void save(value);
        }}
      >
        <input
          id="rename-person"
          data-autofocus
          value={value}
          maxLength={80}
          onChange={(event) => setValue(event.target.value)}
          aria-label={S.s_ten_moi_cua_0_ac5dd137(name)}
          className="h-9 w-full rounded-control border border-line bg-bg px-3 text-sm outline-none focus-visible:border-focus"
        />
        {<Presence>{person?.originalName && <p className="mt-2 text-xs text-fg-2">{S.s_ten_goc_893370ef}{cleanName(person.originalName)}</p>}</Presence>}

      </form>
    </Dialog>
  );
}

type Gender = "male" | "female";
const GENDERS: { value: Gender; label: string }[] = [
  { value: "male", label: S.s_nam_22dd59c8 },
  { value: "female", label: S.s_nu_e15bc11c },
];

/** Giới người nghe đang thấy ở dòng nhân vật: giới chờ áp dụng nếu có, không thì giới trong sổ. */
function shownGender(person: CastMember | null): Gender | null {
  const label = person?.pendingVoice?.gender || person?.gender;
  return label === S.s_nam_22dd59c8 ? "male" : label === S.s_nu_e15bc11c ? "female" : null;
}

/** `waiting`: cuốn không có xưởng (file .abook) - chỉ ghi ý muốn chờ Studio, câu nói và việc làm lại ở trên không đúng nữa.
 *  `onSaved`: làm mới thêm các màn của trang nghe (số thay đổi chưa lưu). */
export function GenderDialog({ bookId, person, onClose, waiting = false, onSaved }: {
  bookId: string;
  person: CastMember | null;
  onClose: () => void;
  waiting?: boolean;
  onSaved?: () => void;
}) {
  const client = useQueryClient();
  const current = shownGender(person);
  const [choice, setChoice] = useState<Gender | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => setChoice(shownGender(person)), [person]);
  const name = person ? cleanName(person.displayName) : "";
  const recorded = waiting ? 0 : (person?.recorded ?? 0);
  const save = async () => {
    if (!person || !choice) return;
    setBusy(true);
    try {
      const { requestedAt } = await api<{ requestedAt: number }>(`/api/books/${bookId}/voice`, {
        method: "POST",
        body: { character: person.name, gender: choice },
      });
      refreshAfterDecision(client, bookId);
      onSaved?.();
      const label = choice === "female" ? S.s_nu_316c30fd : "nam";
      toast.success(S.s_da_ghi_0_la_nhan_vat_1_8cc62f3d(name, label), {
        action: undoAction(client, bookId, "voice", [{ character: person.name, requestedAt, keep: false }], S.s_0_tro_lai_nhu_truoc_khi_doi_gioi_tinh_3d353230(name)),
        duration: UNDO_MS,
      });
      onClose();
    } catch (error) {
      toast.error(S.s_chua_doi_duoc_gioi_tinh_4eefcf7a, { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog footer={<DialogActions>
        <Button variant="ghost" onClick={onClose}>{S.s_thoi_e68f9e88}</Button>
        <Button variant="primary" loading={busy} disabled={!choice || choice === current} onClick={() => void save()}>{S.s_ghi_lai_923c1fd4}</Button>
      </DialogActions>}
      open={person !== null}
      onOpenChange={(open) => !open && onClose()}
      width="max-w-md"
      title={S.s_gioi_tinh_cua_0_ce17d919(name)}
      description={current ? S.s_hien_dang_la_nhan_vat_0_cda496a1(current === "female" ? S.s_nu_316c30fd : "nam") : S.s_may_chua_xac_dinh_duoc_gioi_cua_nguoi_nay_ea153abc}
    >
      <MotionRegion>
      <ChoiceRow<Gender> value={(choice ?? "") as Gender} onChange={setChoice} options={GENDERS} label={S.s_gioi_tinh_46eb9a2c} />
      {waiting && <p className="mt-3 text-sm text-pretty">{S.s_giong_doc_cua_5e7d06dc}{name}{S.s_chua_doi_ngay_studio_se_lam_khi_ban_mo_fil_cc8fd9a5}</p>}
      {/* Chưa có câu nào được thu: vẫn nói giọng sẽ đổi - đổi giới là đổi giọng (soát UX a23: hộp không nói). */}
      {!waiting && recorded === 0 && person && choice && choice !== current && (
        <p className="mt-3 text-sm text-pretty">{S.s_neu_giong_14749bed}{voiceToUse(person) ? `${voiceToUse(person)} ` : ""}{S.s_dang_doc_080a360c}{name}{S.s_khong_hop_gioi_moi_may_chon_mot_giong_29121ad2}{" "}
          {choice === "female" ? S.s_nu_316c30fd : "nam"}{S.s_khac_cho_nguoi_ay_khi_ap_dung_094fb017}</p>
      )}
      {recorded > 0 && (
        <p className="mt-3 text-sm text-pretty">{S.s_ap_dung_se_thu_lai_adf61f2b}{formatNumber(recorded)}{S.s_cau_cua_35c4143d}{name}{S.s_neu_giong_chua_hop_gioi_moi_dce1d351}</p>
      )}
      </MotionRegion>

    </Dialog>
  );
}

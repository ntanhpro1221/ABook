// Mẫu thiết lập có tên cho sách mới (backlog H4): lưu một bộ lựa chọn của trình tạo sách dưới một cái tên rồi dùng lại.
// Phần thuần ở đây - máy chủ kiểm lại cùng luật (webui/library.py clean_book_templates).
//
// Mẫu CHỈ mang lựa chọn thường: giọng kể, chất lượng, model đọc hiểu, "bắt đầu ngay", "chờ tôi duyệt trước khi thu". Không bao giờ mang nguồn truyện, tên
// sách, ngôi kể, hay `dropCredits` (bỏ dòng ghi công là đồng ý riêng từng cuốn - app không tự sửa chữ của truyện).

export type Profile = "fast" | "balanced" | "high_quality";
const PROFILES: readonly string[] = ["fast", "balanced", "high_quality"];

export const MAX_TEMPLATES = 20;
export const NAME_MAX = 40;
/** Nhãn của lựa chọn "không mẫu" (giá trị mặc định của app) - không đặt được làm tên mẫu. */
export const DEFAULT_LABEL = "Mặc định";

export interface BookTemplate {
  name: string;
  /** "" = giọng do máy chọn (sách có người kể “tôi”: cùng giới với họ; không thì giọng đề xuất). */
  narrator: string;
  profile: Profile;
  /** "" = model mặc định của app. */
  analysisModel: string;
  startNow: boolean;
  /** "Chờ tôi duyệt trước khi thu" (webui/precast.py). */
  precastWait: boolean;
}

/** Phần của nháp trình tạo sách mà mẫu đọc và ghi. `template`: tên mẫu đang theo (nháp nhớ qua lần tải lại trang). */
export interface TemplateFields {
  narrator: string;
  profile: Profile;
  analysisModel?: string;
  startNow: boolean;
  precastWait?: boolean;
  template?: string;
}

const modelKey = (name: string) => name.replace(/:latest$/, "");

/** Model của mẫu mà máy không còn: tên model, "" nếu dùng được. `available` = tên các model Ollama đang có (chưa biết - chưa tải
 * xong hay Ollama tắt - thì không kết luận gì, coi như dùng được). */
export function missingModel(template: Pick<BookTemplate, "analysisModel"> | undefined, available?: readonly string[]): string {
  const wanted = template?.analysisModel ?? "";
  if (!wanted || !available?.length) return "";
  return available.some((name) => modelKey(name) === modelKey(wanted)) ? "" : wanted;
}

/** Giọng kể của mẫu mà máy không còn: tên giọng, "" nếu dùng được. `available` = tên các giọng đã tải (chưa tải thì không kết luận). */
export function missingVoice(template: Pick<BookTemplate, "narrator"> | undefined, available?: readonly string[]): string {
  const wanted = template?.narrator ?? "";
  if (!wanted || !available?.length) return "";
  return available.includes(wanted) ? "" : wanted;
}

/** Lời nhắc khi áp mẫu mà giọng kể của nó không còn. */
export function missingVoiceNote(voice: string): string {
  return `Giọng ${voice} trong mẫu không còn trên máy - giữ giọng đang chọn.`;
}

/** Lời nhắc khi áp mẫu mà bỏ qua model của nó. */
export function missingModelNote(model: string): string {
  return `Model ${modelKey(model)} trong mẫu không còn trên máy - giữ model đang chọn.`;
}

export function cleanName(value: string): string {
  return value.split(/\s+/).filter(Boolean).join(" ");
}

const same = (a: string, b: string) => a.toLocaleLowerCase("vi") === b.toLocaleLowerCase("vi");

/** Danh sách mẫu trong tuỳ chọn - chịu được dữ liệu thiếu hay hỏng (không có thì rỗng). */
export function templatesOf(value: unknown): BookTemplate[] {
  if (!Array.isArray(value)) return [];
  const found: BookTemplate[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const { name, narrator, profile, analysisModel, startNow, precastWait } = item as Record<string, unknown>;
    if (typeof name !== "string" || !name || typeof profile !== "string" || !PROFILES.includes(profile)) continue;
    found.push({
      name,
      narrator: typeof narrator === "string" ? narrator : "",
      profile: profile as Profile,
      analysisModel: typeof analysisModel === "string" ? analysisModel : "",
      startNow: startNow !== false,
      precastWait: precastWait === true,
    });
  }
  return found;
}

export function findTemplate(templates: readonly BookTemplate[], name: string | undefined): BookTemplate | undefined {
  return name === undefined ? undefined : templates.find((item) => same(item.name, name));
}

/** Lời báo cho một cái tên không dùng được, "" nếu được. `except`: tên đang được đổi (không tính là trùng với chính nó). */
export function nameProblem(templates: readonly BookTemplate[], raw: string, except?: string): string {
  const name = cleanName(raw);
  if (!name) return "Đặt cho mẫu một cái tên";
  if (name.length > NAME_MAX) return `Tên mẫu tối đa ${NAME_MAX} chữ`;
  if (same(name, DEFAULT_LABEL)) return `“${DEFAULT_LABEL}” là mẫu có sẵn của app - chọn tên khác`;
  if (templates.some((item) => same(item.name, name) && !(except !== undefined && same(item.name, except)))) {
    return `Đã có mẫu tên “${name}”`;
  }
  return "";
}

/** Đã đủ số mẫu cho phép - lưu thêm mẫu mới phải xoá bớt trước (ghi đè mẫu cũ thì vẫn được). */
export function isFull(templates: readonly BookTemplate[]): boolean {
  return templates.length >= MAX_TEMPLATES;
}

/** Chụp các lựa chọn hiện tại của nháp thành một mẫu. `narratorAuto`: giọng kể đang do máy chọn (bạn chưa bấm giọng nào) - mẫu ghi
 * "" để áp cho sách khác thì máy lại chọn theo sách ấy, không ghim tên giọng máy tình cờ chọn cho sách này. */
export function templateFromDraft(draft: TemplateFields, name: string, narratorAuto = false): BookTemplate {
  return {
    name: cleanName(name),
    narrator: narratorAuto ? "" : draft.narrator,
    profile: draft.profile,
    analysisModel: draft.analysisModel ?? "",
    startNow: draft.startNow,
    precastWait: Boolean(draft.precastWait),
  };
}

/** Áp mẫu lên nháp: chỉ năm lựa chọn ấy + tên mẫu, mọi thứ khác (nguồn, tên sách, ngôi kể...) giữ nguyên. Giọng kể của mẫu
 * không còn trong danh sách giọng (`voiceNames`, nếu đã tải) thì giữ giọng đang chọn thay vì chọn một giọng không có; model
 * của mẫu không còn trong danh sách model (`modelNames`) cũng vậy. Mẫu ghi giọng "" (máy chọn) đưa giọng về `machineVoice` -
 * giọng bạn bấm trước đó không còn được tô sáng khi bước Xác nhận nói "máy chọn". */
export function applyTemplate<T extends TemplateFields>(
  draft: T,
  template: BookTemplate,
  voiceNames?: readonly string[],
  modelNames?: readonly string[],
  machineVoice?: string,
): T {
  const usable = template.narrator && (!voiceNames || voiceNames.includes(template.narrator));
  return {
    ...draft,
    narrator: usable ? template.narrator : !template.narrator && machineVoice ? machineVoice : draft.narrator,
    profile: template.profile,
    analysisModel: missingModel(template, modelNames) ? (draft.analysisModel ?? "") : template.analysisModel,
    startNow: template.startNow,
    precastWait: template.precastWait,
    template: template.name,
  };
}

/** Những lựa chọn mà áp mẫu có thể ghi đè (kèm `narratorPicked` của trình tạo sách): chụp trước khi áp để “Hoàn tác” trả lại đúng. */
export interface TemplateChoices {
  narrator: string;
  narratorPicked?: boolean;
  profile: Profile;
  analysisModel?: string;
  startNow: boolean;
  precastWait?: boolean;
  template?: string;
}

export function templateChoices(draft: TemplateChoices): TemplateChoices {
  return {
    narrator: draft.narrator,
    narratorPicked: draft.narratorPicked,
    profile: draft.profile,
    analysisModel: draft.analysisModel ?? "",
    startNow: draft.startNow,
    precastWait: Boolean(draft.precastWait),
    template: draft.template,
  };
}

const CHOICE_LABELS: [keyof TemplateChoices, string][] = [
  ["narrator", "giọng kể"],
  ["profile", "chất lượng"],
  ["analysisModel", "model đọc hiểu"],
  ["startNow", "bắt đầu ngay"],
  ["precastWait", "chờ bạn duyệt trước khi thu"],
];

/** Áp mẫu đã đổi những lựa chọn nào (nói như người dùng thấy); rỗng khi không đổi gì mà họ đã chọn. */
export function changedChoices(before: TemplateChoices, after: TemplateChoices): string[] {
  const a = templateChoices(before);
  const b = templateChoices(after);
  return CHOICE_LABELS.filter(([key]) => a[key] !== b[key]).map(([, label]) => label);
}

/** Người dùng đã đổi lựa chọn nào đó sau khi áp mẫu. Mẫu không ghi giọng kể ("" = máy đề xuất) thì giọng không tính; model mẫu
 * mang mà máy không còn (`modelNames`) cũng không tính - mẫu không áp được nó. */
export function isModified(draft: TemplateFields, template: BookTemplate, modelNames?: readonly string[]): boolean {
  return (
    (template.narrator !== "" && draft.narrator !== template.narrator) ||
    draft.profile !== template.profile ||
    (!missingModel(template, modelNames) && (draft.analysisModel ?? "") !== template.analysisModel) ||
    draft.startNow !== template.startNow ||
    Boolean(draft.precastWait) !== template.precastWait
  );
}

/** Danh sách sau khi lưu `template`: trùng tên (không phân biệt hoa thường) thì thay chỗ cũ, không thì thêm cuối. */
export function upsertTemplate(templates: readonly BookTemplate[], template: BookTemplate): BookTemplate[] {
  const at = templates.findIndex((item) => same(item.name, template.name));
  if (at < 0) return [...templates, template];
  return templates.map((item, index) => (index === at ? template : item));
}

export function removeTemplate(templates: readonly BookTemplate[], name: string): BookTemplate[] {
  return templates.filter((item) => !same(item.name, name));
}

/** Đổi tên một mẫu, giữ nguyên chỗ trong danh sách. Tên mới không dùng được thì trả danh sách như cũ. */
export function renameTemplate(templates: readonly BookTemplate[], from: string, to: string): BookTemplate[] {
  if (nameProblem(templates, to, from)) return [...templates];
  return templates.map((item) => (same(item.name, from) ? { ...item, name: cleanName(to) } : item));
}

/** Tên mức chất lượng như người dùng thấy (Cài đặt, danh sách mẫu). */
export const PROFILE_LABEL: Record<Profile, string> = {
  high_quality: "Chất lượng cao",
  balanced: "Cân bằng",
  fast: "Nhanh",
};

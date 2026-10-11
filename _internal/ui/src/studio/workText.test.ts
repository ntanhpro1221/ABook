import { describe, expect, it } from "vitest";
import { PENDING_NOTE } from "@/studio/decisions";
import { decidedTitle, inboxLead, markNames, narratorButtons, narratorDecidedTitle, nameKey, rerecordSentence, sameNames } from "@/studio/workText";

describe("tô tên ứng viên trong lời kể (thẻ “Người này có phải X?”)", () => {
  const marked = (text: string, names?: string[]) => markNames(text, names).filter((part) => part.mark).map((part) => part.text);

  it("tô mọi chỗ có tên, không phân biệt hoa thường, ghép lại đúng nguyên câu", () => {
    const parts = markNames("Mira bước vào, theo sau là Lena. MIRA cười.", ["mira", "lena"]);
    expect(parts.map((part) => part.text).join("")).toBe("Mira bước vào, theo sau là Lena. MIRA cười.");
    expect(parts.filter((part) => part.mark).map((part) => part.text)).toEqual(["Mira", "Lena", "MIRA"]);
  });

  it("chỉ tô nguyên chữ, và tên dài thắng phần của nó", () => {
    expect(marked("Miranda và Mira", ["mira"])).toEqual(["Mira"]);
    expect(marked("Giáo sư Fernando đến.", ["fernando", "giáo sư fernando"])).toEqual(["Giáo sư Fernando"]);
    expect(marked("Ảnh nhìn Đào Ảnh", ["ảnh"])).toEqual(["Ảnh", "Ảnh"]);
  });

  it("không có tên thì giữ nguyên câu; ký tự đặc biệt trong tên không làm vỡ phép tìm", () => {
    expect(markNames("Không ai cả.", [])).toEqual([{ text: "Không ai cả.", mark: false }]);
    expect(markNames("Không ai cả.")).toEqual([{ text: "Không ai cả.", mark: false }]);
    expect(marked("Tre'ainar (A.) đứng đó", ["tre'ainar", "a."])).toEqual(["Tre'ainar", "A."]);
  });
});

describe("tiêu đề thẻ hai tên gần giống sau khi quyết", () => {
  it("nói kết quả theo tên được hỏi, như thẻ một người hai tên", () => {
    expect(decidedTitle({ kind: "alias", current: "Hai người khác nhau", subject: "Aria", requested: "Arya" })).toBe("“Aria” là Arya");
  });
});

describe("tiêu đề thẻ người kể sau khi quyết", () => {
  it("không lặp tiền tố của nhãn lựa chọn", () => {
    expect(narratorDecidedTitle("Lâm", "Người kể: Mai")).toBe("Đoạn này do Mai kể");
    expect(narratorDecidedTitle("Lâm", "Đổi người kể")).toBe("Đoạn này không phải Lâm kể");
    expect(narratorDecidedTitle("Lâm", "Giữ nguyên")).toBe("Đoạn này vẫn do Lâm kể");
  });

  it("đi qua decidedTitle cho thẻ narrator, và các thẻ khác vẫn nói kết quả", () => {
    expect(decidedTitle({ kind: "narrator", current: "Lâm", requested: "Người kể: Mai" })).toBe("Đoạn này do Mai kể");
    expect(decidedTitle({ kind: "narrator", current: "Lâm", requested: null })).toBeNull();
    expect(decidedTitle({ kind: "speaker", current: "Lâm", requested: "Vai phụ không tên", lines: [1] })).toBe("Câu này của vai phụ không tên");
    expect(decidedTitle({ kind: "pronunciation", current: "Hên-khơ", surface: "Hailkes", requested: "Hên-khơ" })).toBe("Giữ: “Hailkes” đọc là “Hên-khơ”");
  });
});

describe("nút của thẻ người kể", () => {
  it("đoạn mở bằng dòng tiêu đề góc nhìn: nút nhận nói đúng tên dòng ấy gọi", () => {
    expect(narratorButtons("Lâm", { label: "Mai" })).toEqual({ accept: "Nhận: Mai kể đoạn này", keep: "Giữ Lâm là người kể", accepted: "Người kể: Mai" });
    expect(narratorButtons("Lâm", { label: "" })).toEqual({ accept: "Nhận: đoạn kể ngôi thứ ba", keep: "Giữ Lâm là người kể", accepted: "Đổi người kể" });
  });
  it("thẻ cũ giữ nguyên chữ; chương kể ngôi thứ ba không nói 'Giữ  là người kể'", () => {
    expect(narratorButtons("Lâm")).toEqual({ accept: "Không phải Lâm kể - đoạn kể ngôi thứ ba", keep: "Giữ Lâm là người kể", accepted: "Đổi người kể" });
    expect(narratorButtons("", { label: "Mai" }).keep).toBe("Giữ nguyên ngôi thứ ba");
    expect(narratorDecidedTitle("", "Giữ nguyên")).toBe("Đoạn này vẫn kể ở ngôi thứ ba");
    expect(narratorDecidedTitle("", "Người kể: Mai")).toBe("Đoạn này do Mai kể");
  });
});

describe("cái giá của đổi giọng", () => {
  it("mọi nơi nói 'thu lại N câu' cùng một cách", () => {
    expect(rerecordSentence("đổi giọng, thu lại 12 câu")).toBe("Sẽ thu lại 12 câu bằng giọng mới.");
    expect(rerecordSentence("thu lại 22 câu ở các chương chung")).toBe("Sẽ thu lại 22 câu ở các chương chung bằng giọng mới.");
    expect(rerecordSentence(undefined)).toContain("thu lại");
  });
  it("chưa thu câu nào thì nói không phải thu lại (soát UX a23)", () => {
    expect(rerecordSentence("đổi giọng, chưa thu nên không phải thu lại")).toBe("Chưa thu câu nào của người ấy nên không phải thu lại.");
    expect(rerecordSentence("chưa thu nên không phải thu lại")).not.toMatch(/sẽ/i);
  });
});

describe("lời mở đầu hộp việc", () => {
  it("sách đang dừng không tự mâu thuẫn bằng câu 'không phải dừng sách'", () => {
    const stopped = inboxLead({ running: false, paused: null, phase: "casting" });
    expect(stopped).toContain("Sách đang dừng");
    expect(stopped).not.toContain("không phải dừng sách");
  });

  it("mỗi trạng thái nói đúng vế của nó", () => {
    expect(inboxLead({ running: true, paused: "listener", phase: "synthesis" })).toContain("tạm dừng");
    expect(inboxLead({ running: true, paused: null, phase: "synthesis" })).toContain("đang chạy tiếp");
    expect(inboxLead({ running: false, paused: null, phase: "done" })).toContain("Áp dụng thay đổi");
  });
});

describe("tên trùng trong danh sách nhân vật", () => {
  it("so tên bỏ gạch dưới, dấu cách thừa và hoa thường", () => {
    expect(nameKey("  Lính_gác ")).toBe("lính gác");
    const same = sameNames([{ displayName: "Lính gác" }, { displayName: "lính  gác" }, { displayName: "Lính_gác" }, { displayName: "Lâm" }]);
    expect([...same]).toEqual(["lính gác"]);
  });

  it("không có tên trùng thì rỗng", () => {
    expect(sameNames([{ displayName: "Lâm" }, { displayName: "Mai" }]).size).toBe(0);
  });
});

describe("nhắc việc đã quyết khi sách đang chạy", () => {
  it("nói áp từ chương sau, không nhắc ranh giới", () => {
    expect(PENDING_NOTE.running).toBe("áp từ chương sau");
  });
});

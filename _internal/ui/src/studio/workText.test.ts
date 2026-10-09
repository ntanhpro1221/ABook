import { describe, expect, it } from "vitest";
import { PENDING_NOTE } from "@/studio/decisions";
import { decidedTitle, inboxLead, narratorDecidedTitle, nameKey, rerecordSentence, sameNames } from "@/studio/workText";

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

describe("cái giá của đổi giọng", () => {
  it("mọi nơi nói 'thu lại N câu' cùng một cách", () => {
    expect(rerecordSentence("đổi giọng, thu lại 12 câu")).toBe("Sẽ thu lại 12 câu bằng giọng mới.");
    expect(rerecordSentence("thu lại 22 câu ở các chương chung")).toBe("Sẽ thu lại 22 câu ở các chương chung bằng giọng mới.");
    expect(rerecordSentence(undefined)).toContain("thu lại");
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

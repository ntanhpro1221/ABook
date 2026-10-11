import { describe, expect, it } from "vitest";
import { analyzerLabel, narratorLabel } from "./analyzerLabel";

describe("analyzerLabel", () => {
  it("model của app nói bằng số bản, không lộ tên kỹ thuật", () => {
    expect(analyzerLabel("abook-analyzer:v4")).toBe("Model phân tích bản 4");
  });
  it("model khác giữ tên, bỏ :latest", () => {
    expect(analyzerLabel("qwen3:8b")).toBe("Phân tích bằng qwen3:8b");
    expect(analyzerLabel("custom:latest")).toBe("Phân tích bằng custom");
  });
});

describe("narratorLabel (soát UX a24)", () => {
  it("đang chờ đổi giọng kể thì ghi giọng sẽ dùng, kèm chờ áp dụng", () => {
    expect(narratorLabel({ narrator: "Phạm Tuyên", narratorPending: "Hải Đăng" })).toBe("Giọng kể Hải Đăng (chờ áp dụng)");
  });
  it("không chờ gì thì giọng đang đọc; chưa có giọng thì không ghi", () => {
    expect(narratorLabel({ narrator: "Phạm Tuyên", narratorPending: "" })).toBe("Giọng kể Phạm Tuyên");
    expect(narratorLabel({ narrator: "" })).toBe("");
  });
});

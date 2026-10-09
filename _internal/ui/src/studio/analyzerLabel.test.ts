import { describe, expect, it } from "vitest";
import { analyzerLabel } from "./analyzerLabel";

describe("analyzerLabel", () => {
  it("model của app nói bằng số bản, không lộ tên kỹ thuật", () => {
    expect(analyzerLabel("abook-analyzer:v4")).toBe("Model phân tích bản 4");
  });
  it("model khác giữ tên, bỏ :latest", () => {
    expect(analyzerLabel("qwen3:8b")).toBe("Phân tích bằng qwen3:8b");
    expect(analyzerLabel("custom:latest")).toBe("Phân tích bằng custom");
  });
});

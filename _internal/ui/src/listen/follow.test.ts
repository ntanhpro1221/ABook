import { describe, expect, it } from "vitest";
import { chapterToFollow, firstVisibleIndex, followScrollTop, needsFollowScroll, placementOf, SETTLE_MS, shouldResumeFollowing, showJumpToPlaying } from "./follow";

const VIEW = { top: 100, bottom: 700 }; // khung cuộn cao 600 px

describe("placementOf", () => {
  it("trên, trong, dưới khung; ló một phần vẫn là trong", () => {
    expect(placementOf({ top: 20, bottom: 90 }, VIEW)).toBe("above");
    expect(placementOf({ top: 60, bottom: 102 }, VIEW)).toBe("above"); // chỉ ló 2 px
    expect(placementOf({ top: 80, bottom: 130 }, VIEW)).toBe("inside");
    expect(placementOf({ top: 300, bottom: 340 }, VIEW)).toBe("inside");
    expect(placementOf({ top: 690, bottom: 740 }, VIEW)).toBe("inside");
    expect(placementOf({ top: 698, bottom: 740 }, VIEW)).toBe("below");
    expect(placementOf({ top: 900, bottom: 940 }, VIEW)).toBe("below");
  });
});

describe("theo giọng", () => {
  it("chỉ cuộn khi câu chạm mép trên hay xuống quá 85% khung - không cuộn theo từng câu", () => {
    expect(needsFollowScroll({ top: 200, bottom: 240 }, VIEW)).toBe(false);
    expect(needsFollowScroll({ top: 560, bottom: 610 }, VIEW)).toBe(false); // 610 < 100 + 510
    expect(needsFollowScroll({ top: 590, bottom: 640 }, VIEW)).toBe(true);
    expect(needsFollowScroll({ top: 90, bottom: 140 }, VIEW)).toBe(true);
    expect(needsFollowScroll({ top: 1500, bottom: 1540 }, VIEW)).toBe(true);
  });

  it("cuộn tới đặt câu ở khoảng một phần ba từ trên, không âm", () => {
    // câu ở y=900 (800 px dưới mép trên) -> lên 180 px dưới mép trên
    expect(followScrollTop({ top: 900, bottom: 940 }, VIEW, 1000)).toBe(1000 + 800 - 180);
    expect(followScrollTop({ top: 50, bottom: 90 }, VIEW, 10)).toBe(0);
  });

  it("người cuộn đi thì thôi theo; tự cuộn về chỗ câu đang nghe và dừng tay đủ lâu thì theo lại", () => {
    const now = 10_000;
    expect(shouldResumeFollowing(false, "inside", now - SETTLE_MS, now)).toBe(true);
    expect(shouldResumeFollowing(false, "inside", now - 200, now)).toBe(false); // vẫn đang cuộn
    expect(shouldResumeFollowing(false, "below", now - 60_000, now)).toBe(false); // đứng yên lâu mà câu ngoài khung: không giật trang
    expect(shouldResumeFollowing(true, "inside", 0, now)).toBe(false);
    expect(shouldResumeFollowing(false, null, 0, now)).toBe(false);
  });

  it("'Tới câu đang nghe' hiện bất cứ khi nào câu ngoài khung mà không đang theo", () => {
    expect(showJumpToPlaying(false, "below")).toBe(true);
    expect(showJumpToPlaying(false, "above")).toBe(true);
    expect(showJumpToPlaying(false, "inside")).toBe(false);
    expect(showJumpToPlaying(true, "below")).toBe(false);
    expect(showJumpToPlaying(false, null)).toBe(false);
  });
});

describe("firstVisibleIndex", () => {
  const items = [
    { index: 0, top: -400, bottom: -300 },
    { index: 1, top: -300, bottom: 98 },
    // câu ngắn, cả câu nằm ngay dưới mép trên: trước đây mốc +72 px bỏ qua nó
    { index: 2, top: 110, bottom: 140 },
    { index: 3, top: 150, bottom: 260 },
  ];

  it("câu đầu tiên thật sự thấy, kể cả câu ngắn sát mép trên", () => {
    expect(firstVisibleIndex(items, VIEW)).toBe(2);
  });

  it("câu dài ló phần đuôi vẫn là câu đang thấy", () => {
    expect(firstVisibleIndex([{ index: 5, top: -200, bottom: 160 }, { index: 6, top: 170, bottom: 200 }], VIEW)).toBe(5);
  });

  it("không câu nào thấy: câu đầu", () => {
    expect(firstVisibleIndex([{ index: 4, top: 900, bottom: 950 }], VIEW)).toBe(4);
    expect(firstVisibleIndex([], VIEW)).toBe(0);
  });
});

describe("màn đọc theo giọng sang chương kế", () => {
  it("đang mở đúng chương đang nghe: theo sang chương mới", () => {
    expect(chapterToFollow(1, 2, 1)).toBe(2);
  });

  it("người đã mở chương khác chương đang nghe: không kéo đi", () => {
    expect(chapterToFollow(1, 2, 5)).toBeNull();
    expect(chapterToFollow(1, 2, 2)).toBeNull(); // đã ở chương mới rồi
  });

  it("chưa có chương nào đang nghe, hay chương không đổi: đứng yên", () => {
    expect(chapterToFollow(null, 2, 2)).toBeNull();
    expect(chapterToFollow(2, null, 2)).toBeNull();
    expect(chapterToFollow(2, 2, 2)).toBeNull();
  });
});

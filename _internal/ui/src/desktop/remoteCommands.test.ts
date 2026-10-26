import { describe, expect, it } from "vitest";
import { commandRunner } from "./RemotePhone";

/** Lời hứa tự giải tay: lệnh "load" chờ máy chủ trả cuốn sách. */
function deferred() {
  let resolve: () => void = () => undefined;
  const promise = new Promise<void>((done) => (resolve = done));
  return { promise, resolve };
}

describe("lệnh từ máy đã ghép: mỗi mã làm đúng một lần, theo thứ tự (hai lần báo cùng mang một lô lệnh)", () => {
  it("lần báo thứ hai về giữa lúc lệnh đầu còn chờ: không làm lại lệnh sau, không làm lệnh sau trước lệnh đầu", async () => {
    const book = deferred();
    const done: string[] = [];
    const run = commandRunner(new Map(), async (command: { id: string; action: string }) => {
      if (command.action === "load") await book.promise;
      done.push(command.id);
      return null;
    }, () => undefined);
    const batch = [{ id: "1", action: "load" }, { id: "2", action: "toggle" }];
    const first = run(batch);
    // Lần báo ngay (wait 0) về trong lúc lần hỏi dài còn chờ máy chủ trả sách: host giao lại cùng lô (chưa có kết quả).
    const second = run(batch);
    book.resolve();
    await Promise.all([first, second]);
    expect(done).toEqual(["1", "2"]);
  });

  it("lệnh hỏng giữa chừng vẫn gửi kết quả, lệnh sau vẫn chạy", async () => {
    const acks: { id: string; ok: boolean }[] = [];
    const run = commandRunner(new Map(), async (command: { id: string }) => {
      if (command.id === "1") throw new Error("hỏng");
      return null;
    }, (ack) => acks.push(ack));
    await run([{ id: "1" }, { id: "2" }]);
    expect(acks.map((ack) => [ack.id, ack.ok])).toEqual([["1", false], ["2", true]]);
  });
});

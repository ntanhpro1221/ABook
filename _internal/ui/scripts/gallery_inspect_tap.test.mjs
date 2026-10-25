// @vitest-environment node
import { describe, it, expect } from "vitest";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { browserAvailable, launch, findBrowser, connect, openPage, evaluate } from "./gallery_browser.mjs";
import { inspectTapReach } from "./gallery_inspect_tap.mjs";
import { normalizeRule, DEFAULT_FAIL_ON } from "./gallery_inspect.mjs";

const cases = [
  ["lớp tốt", '<div role="dialog"><button>Tốt</button></div>', 0],
  ["menu mất chạm trong dialog", '<div role="dialog"><button>Nền</button><div role="menu" style="pointer-events:none"><button role="menuitem">Sửa thông tin</button></div></div>', 1],
  ["nút dưới scrim", '<main><button>Bị che</button></main><div style="position:fixed;inset:0;background:#888"></div>', 1],
  ["mục cuộn khuất", '<div role="menu" style="height:60px;overflow:auto"><button>Hiện</button><div style="height:80px"></div><button>Khuất</button></div>', 0],
  ["input dưới label for", '<main><div style="position:relative"><input id="chon" type="checkbox" style="pointer-events:none"><label for="chon" style="position:absolute;inset:0;background:white">Chọn</label></div></main>', 0],
  ["input dưới label cha", '<main><label style="position:relative;display:block"><input type="checkbox" style="pointer-events:none"><span style="position:absolute;inset:0;background:white">Chọn</span></label></main>', 0],
  ["chân dính của chính lớp", '<div role="dialog" style="height:100px;overflow:auto"><div style="height:50px"></div><button>Bị chân che</button><footer style="position:sticky;bottom:0;height:60px;background:white">Chân</footer></div>', 0, "FOOTER"],
  ["đầu dính của chính lớp", '<div role="dialog"><button>Bị đầu che</button><header style="position:sticky;top:0;margin-top:-48px;height:48px;background:white">Đầu</header></div>', 0, "HEADER"],
  ["opacity 0 và nhỏ hơn 0,05", '<main><button style="opacity:0;pointer-events:none">Ẩn</button><div style="opacity:.1"><button style="opacity:.4;pointer-events:none">Mờ</button></div></main>', 0],
  ["inert và disabled", '<main><div inert><button>Inert</button></div><button disabled>Khoá</button><button aria-disabled="true" style="pointer-events:none">Khoá ARIA</button></main>', 0],
  ["lớp lá cuối, bỏ lớp đóng và nền", '<div role="dialog"><button style="pointer-events:none">Nền</button><div role="menu"><button>Tốt</button></div></div><div role="listbox" data-state="closed"><button style="pointer-events:none">Đóng</button></div>', 0],
  ["pe none dù hit trong lớp", '<div role="dialog"><button style="pointer-events:none">Mất chạm</button></div>', 1],
  ["con khôi phục chạm trong cha none", '<div role="dialog" style="pointer-events:none"><button style="pointer-events:auto">Nhận chạm</button></div>', 0],
  ["nút mở bảng đang đóng vẫn phải nhận chạm", '<main><button data-state="closed" style="pointer-events:none">Mở bảng</button></main>', 1],
  ["tâm ngoài viewport", '<main><button style="position:absolute;top:2000px;pointer-events:none">Ngoài</button></main>', 0],
  ["opacity đúng 0,05 vẫn kiểm", '<main><button style="opacity:.05;pointer-events:none">Biên</button></main>', 1],
  ...[100, 101, 102, 200].map((height) => [
    `cùng thanh cố định, tâm hàng cách mép client ${height - 99} px`,
    `<main><div style="height:${height}px;overflow:auto"><div style="height:75px"></div><button>Hàng bị che</button><div style="height:200px"></div></div></main><div style="position:fixed;left:20px;right:20px;top:119px;height:100px;background:white">Thanh phát</div>`,
    height <= 101 ? 0 : 1,
  ]),
  ...[[124, 0], [96, 1]].map(([center, count]) => [
    `hàng cuộn ngang trong trang cuộn dọc, tâm ${center > 120 ? "dưới" : "trong"} mép trang, thanh cố định che`,
    `<main style="height:100px;overflow:auto"><div style="height:${center - 44}px"></div><div style="display:flex;overflow-x:auto"><button>Lọc</button></div><div style="height:200px"></div></main><div style="position:fixed;left:0;right:0;top:${center > 120 ? 120 : 80}px;height:200px;background:white">Thanh tab</div>`,
    count,
  ]),
  ["toast che nút trang thường: chỉ ghi chi tiết", '<main><button>Nền</button></main><div data-sonner-toast style="position:fixed;inset:20px;background:white">Thông báo</div>', 0, undefined, 1],
  ["div thường che nút vẫn lỗi", '<main><button>Nền</button></main><div style="position:fixed;inset:20px;background:white">Khung thường</div>', 1],
  ...["dialog", "alertdialog", "menu", "listbox"].map((role) => [
    `toast che nút ${role} vẫn lỗi`, `<div role="${role}"><button>Chọn</button></div><div data-sonner-toast style="position:fixed;inset:20px;background:white">Thông báo</div>`, 1,
  ]),
  ["nút toast nhận chạm trong toast", '<main></main><div data-sonner-toast><button>Đóng</button><button>Hoàn tác</button></div>', 0],
  ["nút toast pe none vẫn lỗi", '<main></main><div data-sonner-toast><button style="pointer-events:none">Hoàn tác</button></div>', 1],
  ["nút toast bị lớp khác che vẫn lỗi", '<main></main><div data-sonner-toast><button>Đóng</button></div><div style="position:fixed;inset:0;background:white">Che toast</div>', 1],
  ["kiểm toast ngay cả khi không có main", '<div data-sonner-toast><button style="pointer-events:none">Đóng</button></div>', 1],
  ["toast trong DOM của dialog vẫn không được che nút bảng", '<div role="dialog"><button>Chọn</button><div data-sonner-toast style="position:fixed;inset:20px;background:white">Thông báo</div></div>', 1],
  ["nút toast nằm trong main chỉ kiểm đúng một lần", '<main><div data-sonner-toast><button style="pointer-events:none">Đóng</button></div></main>', 1],
];

describe("TAP REACH trên Edge thật", () => {
  it("luật 15 nằm trong cổng mặc định", () => {
    expect(normalizeRule("rule15")).toBe("TAP REACH");
    expect(DEFAULT_FAIL_ON).toContain("TAP REACH");
  });
  it.skipIf(!browserAvailable)("đối chứng hai phía và từng ngoại lệ", async () => {
    const browser = await launch(findBrowser(), { preserveProfile: true });
    let cdp;
    const results = [];
    try {
      cdp = await connect(browser.endpoint);
      for (const mobile of [false, true]) for (const theme of ["light", "dark"]) {
        const page = await openPage(cdp, { width: mobile ? 412 : 1440, height: 915, scale: 1, mobile, theme });
        const { frameTree } = await cdp.send("Page.getFrameTree", {}, page.sessionId);
        for (const [name, body, count, expectedHit, detailCount = 0] of cases) {
          await cdp.send("Page.setDocumentContent", { frameId: frameTree.frame.id, html: `<!doctype html><html lang="vi"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:20px}button{height:48px;min-width:100px}input{width:24px;height:24px}[role=dialog],main{position:relative;min-height:100px}label{min-height:48px}</style>${body}</html>` }, page.sessionId);
          const result = await evaluate(cdp, page.sessionId, `(()=>{const findings=[];const details=(${inspectTapReach.toString()})({css:getComputedStyle,rect:r=>({x:r.x,y:r.y,width:r.width,height:r.height}),selector:e=>e.localName+(e.id?'#'+e.id:''),add:(rule,e,text,rects,details)=>findings.push({rule,text,rects,...details})});return {findings,...details}})()`);
          const hit = await evaluate(cdp, page.sessionId, "(()=>{const e=document.querySelector('button,input');if(!e)return null;const r=e.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.tagName})()");
          results.push({ name, mobile, theme, expected: count, expectedHit, detailCount, hit, ...result });
        }
        await cdp.send("Target.closeTarget", { targetId: page.targetId });
      }
    } finally {
      cdp?.close();
      await browser.close();
      if (process.env.TAP_FIXTURE_OUT) {
        mkdirSync(process.env.TAP_FIXTURE_OUT, { recursive: true });
        writeFileSync(path.join(process.env.TAP_FIXTURE_OUT, "findings.json"), JSON.stringify(results, null, 2));
      }
    }
    for (const r of results) {
      expect(r.findings.length, `${r.name} / ${r.mobile} / ${r.theme}`).toBe(r.expected);
      expect(r.tapToastOcclusions.length, `${r.name} / chi tiết toast`).toBe(r.detailCount);
      if (r.expectedHit) expect(r.hit, r.name).toBe(r.expectedHit);
    }
  }, 60000);
});

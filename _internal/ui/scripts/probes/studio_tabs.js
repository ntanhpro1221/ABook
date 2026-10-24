// Căn lề và nhịp của các tab trong dự án Studio (Kịch bản, Cần nghe lại, Nhật ký), số đếm trên tab, và danh sách cuộn trong hộp thoại.
// Trả mảng chuỗi, mỗi chuỗi là một vấn đề; rỗng = đạt. Dùng: gallery_shots --probe scripts/probes/studio_tabs.js (máy tính 1440 x 900).
(() => {
  const out = [];
  const box = (element) => element.getBoundingClientRect();
  const textBox = (element) => { const range = document.createRange(); range.selectNodeContents(element); return range.getBoundingClientRect(); };
  const near = (a, b, tolerance = 0.5) => Math.abs(a - b) <= tolerance;
  const baseline = (node) => {
    const mark = document.createElement("span");
    mark.style.cssText = "display:inline-block;width:0;height:0;vertical-align:baseline";
    node.parentNode.insertBefore(mark, node);
    const y = mark.getBoundingClientRect().bottom;
    mark.remove();
    return y;
  };
  const firstText = (element, skip) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.data.trim() && !(skip && skip.contains(node)) && !node.parentElement.closest(".sr-only")) return node;
    }
    return null;
  };

  // Không tràn ngang.
  for (const element of [document.documentElement, document.body, ...document.querySelectorAll("#root, main")]) {
    if (element.scrollWidth !== element.clientWidth) out.push(`tràn ngang ${element.tagName} ${element.scrollWidth} > ${element.clientWidth}`);
  }

  // Số đếm tab: chữ trơn (không nền, không bo), thẳng đường chân chữ với tên tab.
  for (const tab of document.querySelectorAll('[role="tablist"] button')) {
    const count = tab.querySelector(".tabular");
    const label = firstText(tab, count);
    const digits = count && firstText(count);
    if (!count || !label || !digits) continue;
    const style = getComputedStyle(count);
    const name = label.data.trim();
    if (style.backgroundColor !== "rgba(0, 0, 0, 0)" || parseFloat(style.paddingLeft) > 0) out.push(`số đếm của tab "${name}" còn là viên thuốc`);
    const delta = baseline(digits) - baseline(label);
    if (Math.abs(delta) > 0.5) out.push(`số đếm của tab "${name}" lệch đường chân chữ ${delta.toFixed(2)} px`);
  }

  const edge = document.querySelector('[role="tablist"]');
  const left = edge ? box(edge).left : null;
  const right = edge ? box(edge).right : null;

  // Nhật ký: chấm đúng tâm vạch dọc, và đúng tâm dòng chữ đầu.
  const line = [...document.querySelectorAll("section ol")].find((element) => element.className.includes("border-l"));
  if (line) {
    const lineBox = box(line);
    const centre = lineBox.left + parseFloat(getComputedStyle(line).borderLeftWidth) / 2;
    for (const item of line.querySelectorAll("li")) {
      const dot = item.querySelector("span.absolute");
      const time = item.querySelector("span.tabular");
      if (!dot || !time) continue;
      const d = box(dot);
      const t = textBox(time);
      if (!near(d.left + d.width / 2, centre)) out.push(`chấm nhật ký lệch vạch ${(d.left + d.width / 2 - centre).toFixed(2)} px`);
      if (!near(d.top + d.height / 2, t.top + t.height / 2, 1)) out.push(`chấm nhật ký lệch dòng chữ ${(d.top + d.height / 2 - (t.top + t.height / 2)).toFixed(2)} px`);
    }
  }

  // Kịch bản: mọi hàng chung mép trái của ô người nói, của nút nghe và của chữ; thanh công cụ, chú giải, "Phím tắt" cùng mép trái.
  const script = document.querySelector('ol[aria-label^="Kịch bản"]');
  if (script && left !== null) {
    if (document.querySelector("select#script-chapter")) out.push("ô chọn chương còn là <select> gốc");
    const filter = document.querySelector('[role="radiogroup"][aria-label="Hiện câu nào"]');
    if (filter) {
      if (filter.className.includes("border ") || filter.querySelector("[class*='bg-accent ']")) out.push("bộ lọc Kịch bản còn là hộp segmented");
      const last = filter.lastElementChild;
      if (!near(box(last).right, right)) out.push(`bộ lọc lệch mép phải ${(box(last).right - right).toFixed(2)} px`);
    }
    const title = document.getElementById("script-chapter");
    if (title) {
      const t = textBox(title.querySelector("span"));
      if (!near(t.left, left, 1.5)) out.push(`tên chương lệch mép trái ${(t.left - left).toFixed(2)} px`);
    }
    const legend = document.querySelector('[role="group"][aria-label^="Người nói trong chương"]');
    if (legend) {
      const avatar = legend.querySelector(".avatar");
      if (!near(box(avatar).left, left, 1)) out.push(`chú giải lệch mép trái ${(box(avatar).left - left).toFixed(2)} px`);
    }
    const hint = [...document.querySelectorAll("button")].find((element) => element.textContent.trim() === "Phím tắt");
    if (hint && !near(box(hint.querySelector("svg")).left, left, 1.5)) out.push(`"Phím tắt" lệch mép trái ${(box(hint.querySelector("svg")).left - left).toFixed(2)} px`);
    const rows = [...script.children].map((row) => {
      const text = row.querySelector("p");
      const cell = row.querySelector("button.avatar") ?? row.querySelector("span.truncate");
      const play = row.querySelector('button[aria-label^="Nghe câu"], button[aria-label="Dừng"]');
      return { row, text: textBox(text), cell: cell && (cell.tagName === "BUTTON" ? box(cell) : textBox(cell)), play: play && box(play), height: box(row).height, lines: (() => { const range = document.createRange(); range.selectNodeContents(text); return range.getClientRects().length; })() };
    });
    for (const [index, item] of rows.entries()) {
      if (item.cell && !near(item.cell.left, left, 1)) out.push(`hàng ${index + 1}: ô người nói lệch mép trái ${(item.cell.left - left).toFixed(2)} px`);
      if (!near(item.text.left, rows[0].text.left)) out.push(`hàng ${index + 1}: chữ không thẳng cột`);
      if (item.play && !near(item.play.left, rows.find((other) => other.play).play.left)) out.push(`hàng ${index + 1}: nút nghe không thẳng cột`);
      if (item.play && item.text.left - item.play.right > 14) out.push(`hàng ${index + 1}: nút nghe cách chữ ${(item.text.left - item.play.right).toFixed(1)} px`);
      // Hàng chỉ có một dòng chữ (không dòng phụ): cao đúng một dòng + đệm, không cao hơn vì cột hành động.
      if (item.lines === 1 && item.row.querySelectorAll("p").length === 1 && item.height > 40) out.push(`hàng ${index + 1}: cao ${item.height.toFixed(1)} px cho một dòng chữ`);
    }
  }

  // Cần nghe lại: hàng chung mép nội dung (vòng ▶ ở mép trái, chữ nút cuối ở mép phải), nút không viền, dấu chấm giữa chỉ một kiểu.
  for (const row of document.querySelectorAll("[data-review-row]")) {
    if (!row.className.includes("grid") || left === null) continue;
    const first = row.firstElementChild;
    const buttons = [...row.lastElementChild.querySelectorAll("button")];
    if (!near(box(first).left, left, 1)) out.push(`Cần nghe lại: vòng nghe lệch mép trái ${(box(first).left - left).toFixed(2)} px`);
    if (buttons.length && !near(textBox(buttons[buttons.length - 1]).right, right, 1)) out.push(`Cần nghe lại: chữ nút cuối lệch mép phải ${(textBox(buttons[buttons.length - 1]).right - right).toFixed(2)} px`);
    for (const button of buttons) if (parseFloat(getComputedStyle(button).borderTopWidth) > 0) out.push(`Cần nghe lại: nút "${button.innerText.trim()}" còn viền`);
    const meta = row.querySelector("div.flex-wrap");
    if (meta && [...meta.querySelectorAll("span")].some((span) => /^\s*·/.test(span.textContent))) out.push("Cần nghe lại: dấu · đầu một phần riêng (không đều)");
  }

  // Danh sách cuộn trong hộp thoại: phải có mép mờ báo còn nữa.
  for (const element of document.querySelectorAll('[role="dialog"] *')) {
    const style = getComputedStyle(element);
    if ((style.overflowY === "auto" || style.overflowY === "scroll") && element.scrollHeight > element.clientHeight + 2 && element.clientHeight > 150) {
      const atEnd = element.scrollTop + element.clientHeight >= element.scrollHeight - 2;
      if (!atEnd && !(style.maskImage && style.maskImage !== "none")) out.push(`danh sách cuộn trong hộp thoại không có mép mờ (${element.scrollHeight} > ${element.clientHeight})`);
    }
  }
  return out;
})()

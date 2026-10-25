/** Chỉ đánh dấu phần tử đang focus: đổi cờ ở html làm tính lại style cả chương dù chỉ cần giấu một vòng. */
export function installFocusModality(doc: Document): () => void {
  let pointer = false;
  let marked: Element | null = null;
  const clear = () => { marked?.removeAttribute("data-pointer-focus"); marked = null; };
  const focus = () => {
    clear();
    if (pointer && doc.activeElement && doc.activeElement !== doc.body) {
      marked = doc.activeElement;
      marked.setAttribute("data-pointer-focus", "");
    }
  };
  const down = () => { pointer = true; focus(); };
  const key = () => { pointer = false; clear(); };
  doc.addEventListener("pointerdown", down, true);
  doc.addEventListener("keydown", key, true);
  doc.addEventListener("focusin", focus, true);
  doc.addEventListener("focusout", clear, true);
  return () => {
    clear();
    doc.removeEventListener("pointerdown", down, true);
    doc.removeEventListener("keydown", key, true);
    doc.removeEventListener("focusin", focus, true);
    doc.removeEventListener("focusout", clear, true);
  };
}

import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";
const src=fileURLToPath(new URL('../src',import.meta.url));
const files=(dir)=>readdirSync(dir,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?files(path.join(dir,entry.name)):[path.join(dir,entry.name)]);
const css=readFileSync(path.join(src,'styles.css'),'utf8');
// Đổi theme cố ý đổi cả trang; dataset.theme không phải chỗ đặt biến cho một vùng con.
const themeFiles=['desktop/App.tsx','android/settings.ts','gallery/boot.ts'];
// dataset.vt ở motion.ts phối hợp ảnh chuyển cảnh; trace c14 kiểm riêng phạm vi .now-playing-vt.
const vtFiles=['shared/motion.ts'];
const rootStyleWrite=/\b(?:documentElement|root)\s*\.\s*style\s*\.\s*setProperty\s*\(/;
it("cấm ghi biến style lên html trong app, kể cả file đổi theme / chuyển cảnh",()=>{
  const app=files(src).filter(file=>/\.tsx?$/.test(file)&&!file.includes('.test.'));
  const hits=app.filter(file=>rootStyleWrite.test(readFileSync(file,'utf8')));
  expect(hits.map(file=>path.relative(src,file))).toEqual([]);
  for(const [attribute,allowed] of [['theme',themeFiles],['vt',vtFiles]])for(const file of app){
    const write=new RegExp(`\\b(?:documentElement|root)\\s*\\.\\s*dataset\\s*\\.\\s*${attribute}\\b`);
    if(write.test(readFileSync(file,'utf8')))expect(allowed).toContain(path.relative(src,file).split(path.sep).join('/'));
  }
});
it("policy nhận cả cách viết documentElement và alias root qua xuống dòng",()=>{
  for(const code of ['document.documentElement.style.setProperty("--x", "1")','root.style.setProperty("--x", "1")','root\n .style . setProperty ("--x", "1")'])expect(rootStyleWrite.test(code)).toBe(true);
  for(const code of ['root.dataset.theme = next','root.dataset.vt = "1"','toaster.style.setProperty("--toast-top", top)'])expect(rootStyleWrite.test(code)).toBe(false);
});
it("không đưa group-has qua :is hay selector focus ở html trở lại: chúng invalidation toàn trang",()=>{
  const hits=files(src).filter(file=>/\.tsx?$/.test(file)&&!file.includes('.test.')).filter(file=>/group-has-|html\[data-input/.test(readFileSync(file,'utf8')));
  expect(hits).toEqual([]);expect(css).not.toContain('html[data-input');
  expect(css).toContain('.project-row:has([data-state="open"]) .project-updated { opacity: 0; }');
  const projects=readFileSync(path.join(src,'studio/ProjectsScreen.tsx'),'utf8');
  expect(projects).toContain('className="project-row group relative"');
  expect(projects).toContain('"project-updated tabular');
  expect(css).toMatch(/\[data-pointer-focus\]:focus-visible:not\(input, textarea, select, \[contenteditable\]\)/);
});
it("cấm thêm transition layout/all; giữ hai ngoại lệ đã đo: gạch chân rỗng và chỗ bảng Đang nghe",()=>{
  const hits=files(src).filter(file=>/\.tsx$/.test(file)&&!file.includes('.test.')&&!file.endsWith('SlidingIndicator.tsx')).flatMap(file=>{
    const matches=readFileSync(file,'utf8').match(/transition-(?:all\b|\[[^\]\n]*(?:height|width|padding|margin|\btop\b)[^\]\n]*\])/g);
    // FLIP của chỗ bảng không vượt vùng nhiễu ở 6x (c13); giữ tween cũ, không cho phép thêm kiểu tween layout khác.
    return matches?.filter(value=>!(file.endsWith('PlayerViews.tsx')&&value==='transition-[padding-bottom]')).map(value=>`${path.relative(src,file)}: ${value}`)??[];
  });expect(hits).toEqual([]);
  for(const selector of ['.now-playing','.page-motion','.reading-surface'])for(const rule of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)){
    if(!rule[1].trim().split(',').some(s=>s.trim()===selector))continue;
    expect(rule[2].match(/transition(?:-property)?:[^;]+/g)?.join(' ')??'').not.toMatch(/height|width|padding|margin|\btop\b|\ball\b/);
  }
});

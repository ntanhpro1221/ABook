import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";
const src=fileURLToPath(new URL('../src',import.meta.url));
const files=(dir)=>readdirSync(dir,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?files(path.join(dir,entry.name)):[path.join(dir,entry.name)]);
const css=readFileSync(path.join(src,'styles.css'),'utf8');
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

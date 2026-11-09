// The pinned TypeScript compiler parses JSX, templates, regexes and comments.
import { API } from 'typescript/unstable/sync';
import * as ts from 'typescript/unstable/ast';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const config = path.join(root,'ui/tsconfig.json');
const api = new API({cwd:path.join(root,'ui')});
const snapshot = api.updateSnapshot({openProjects:[config]});
const program = snapshot.getProject(config).program;
const vi = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i;
const result=[];
try {
  for(const file of program.getSourceFileNames()) {
    const rel=path.relative(root,file).replaceAll('\\','/');
    if(!/^ui\/src\/(desktop|listen|shared|studio|android)\//.test(rel) || /\.test\.|\.d\.ts$|generated\./.test(rel)) continue;
    const sf=program.getSourceFile(file);
    function visit(n) {
      let value;
      const p=n.parent;
      const attr=p && ts.isJsxAttribute(p)?p.name.text : p && ts.isJsxExpression(p) && ts.isJsxAttribute(p.parent)?p.parent.name.text : p && ts.isPropertyAssignment(p) && p.initializer===n ? p.name.getText(sf).replaceAll(/['"]/g,'') : '';
      const uiValue=/^(label|title|text|placeholder|description|aria-label|alt|hint|caption|subtitle|heading|emptyText|confirmLabel|cancelLabel)$/.test(attr);
      if(ts.isJsxText(n)) value=n.text.replace(/\s+/g,' ').trim();
      else if(ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) {
        if(ts.isImportDeclaration(n.parent) || ts.isExportDeclaration(n.parent) || ts.isLiteralTypeNode(n.parent)) return;
        if(ts.isPropertyAssignment(n.parent) && n.parent.name===n) return;
        value=n.text;
      } else if(ts.isTemplateExpression(n)) {
        value=n.head.text;
        n.templateSpans.forEach((s,i)=> {value+='{'+i+'}'+s.literal.text;});
      }
      if(value && (vi.test(value) || ((ts.isJsxText(n) || uiValue) && /[\p{L}]/u.test(value)) || /^[A-Z][a-z]+(?: [A-Za-z]+)*$/.test(value))) {
        if (/^h[1-6]$/.test(value) || /^(?:!?text-|#[0-9a-f]+$)/i.test(value)) return;
        result.push([rel,value]);
      }
      n.forEachChild(visit);
    }
    visit(sf);
  }
  fs.writeFileSync(process.argv[2],JSON.stringify(result));
} finally {snapshot.dispose();api.close();}

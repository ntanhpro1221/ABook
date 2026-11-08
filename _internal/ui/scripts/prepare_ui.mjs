import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const python = process.env.ABOOK_PYTHON || 'D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe';
const result = spawnSync(python, ['-X', 'utf8', fileURLToPath(new URL('../../scripts/prepare_ui.py', import.meta.url))], {stdio:'inherit', windowsHide:true});
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);

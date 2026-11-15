from pathlib import Path
import os
import shutil
import subprocess

import pytest


@pytest.mark.skipif(shutil.which('node') is None, reason='Node is unavailable')
def test_windowless_adapter_preserves_fork_options_and_exec_callbacks():
    preload = Path(__file__).resolve().parents[1] / 'docs/affordance/windowless_node.cjs'
    source = r'''
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const calls = [];
for (const name of ['spawn','spawnSync','fork','execFile','execFileSync']) cp[name] = (...args) => calls.push([name,...args]);
require(process.argv[1]);
cp.fork('worker.cjs', undefined, {serialization:'advanced', env:{TASK:'own'}, stdio:['pipe','pipe','pipe','ipc']});
let call = calls.pop();
assert.deepEqual(call[2], []);
assert.deepEqual(call[3], {serialization:'advanced',env:{TASK:'own'},stdio:['pipe','pipe','pipe','ipc'],windowsHide:true});
const callback = () => {};
cp.execFile('node', ['-v'], callback);
call = calls.pop(); assert.equal(call[4], callback); assert.equal(call[3].windowsHide,true);
cp.spawnSync('node', ['-v'], {input:'payload',encoding:'utf8'});
call = calls.pop(); assert.equal(call[3].input,'payload'); assert.equal(call[3].encoding,'utf8'); assert.equal(call[3].windowsHide,true);
'''
    env = dict(os.environ)
    env.pop('NODE_OPTIONS', None)
    subprocess.run([shutil.which('node'), '-e', source, str(preload)], check=True, env=env,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), capture_output=True)

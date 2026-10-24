"""Serve existing ABook static UI with new synthetic data. No model/worker runs.

--state-dir MUST be a new directory; all app writes stay beneath it.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
os.environ['ABOOK_CAST_DISCOVERY'] = '0'
os.environ['ABOOK_PRECAST_WATCH'] = '0'
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '4'

def main():
    from ui_tap_audit import limit_cpu
    limit_cpu()
    parser=argparse.ArgumentParser(description=__doc__)
    repo=Path(__file__).resolve().parents[3]
    parser.add_argument('--state-dir',required=True)
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--static-dir',type=Path,help='override this tree\'s built UI')
    args=parser.parse_args()
    root=Path(args.state_dir).resolve()
    root.mkdir(parents=True,exist_ok=False)
    prefs=root/'data/preferences.json'
    os.environ['ABOOK_PREFERENCES']=str(prefs)
    sys.path.insert(0,str(repo/'_internal'))
    from abook.webui import actions
    from abook.webui.library import Preferences
    from abook.webui.server import App,Server
    import httpx
    preferences=Preferences(prefs)
    preferences.update({'libraryRoot':str(root/'library')})
    static=(args.static_dir or repo/'_internal/abook/webui/static').resolve()
    if not (static/'index.html').is_file():
        raise RuntimeError(f'Built UI missing: {static}; build ui with Vite first')
    extra={'static_dir':static}
    app=App(preferences=preferences,runner=actions.FakeRunner(),token=None,version='dev',**extra)
    server=Server(app,port=args.port).start()
    try:
        with httpx.Client(base_url=server.url,trust_env=False,timeout=30) as http:
            source=root/'chapter.txt'
            source.write_text('Chapter 1\n\nA quiet morning. This book is synthetic UI test data.\n\nEveryone reads a book.\n',encoding='utf-8')
            def post(path,body):
                r=http.post(path,json=body);r.raise_for_status();return r.json()
            listen=post('/api/listen/import',{'path':str(source),'title':'Tap Audit Fixture'})['id']
            post(f'/api/listen/books/{listen}/reading',{'chapterId':1,'index':0})
            voice=http.get('/api/voices').json()[0]['name']
            studio=post('/api/books',{'paths':[str(source)],'title':'Tap Studio Fixture','profile':'high_quality','narrator':voice,'firstPerson':'','start':False})['id']
            library=http.get('/api/library').json()
            book=next(b for b in library['books'] if b['id']==studio)
            db=Path(book['path'])/'project.sqlite3'
            # New synthetic fixture DB only. Planned voice metadata never synthesizes audio.
            with sqlite3.connect(db) as conn:
                now=time.time();line='A quiet morning. This is synthetic UI fixture text.'
                cur=conn.execute('INSERT INTO voice_profiles(voice_key,engine,seed,created_at,updated_at) VALUES(?,?,?,?,?)',('tap-test-voice','fixture',42,now,now))
                conn.execute('INSERT INTO segments(stable_id,chapter_id,seq,text,text_sha256,kind_hint,kind,speaker,voice_profile_id,status,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',('tap-ui-line-1',1,0,line,hashlib.sha256(line.encode()).hexdigest(),'dialogue','dialogue','TAP_PERSON',cur.lastrowid,'analyzed',now))
                conn.execute("UPDATE chapters SET total_segments=1,status='analyzed' WHERE id=1")
            template=(Path(__file__).resolve().parent/'scenarios.json').read_text(encoding='utf-8')
            scenario_path=root/'scenarios.json'
            scenario_path.write_text(template.replace('{listen}',listen).replace('{studio}',studio),encoding='utf-8')
            metadata=dict(url=server.url,listen=listen,studio=studio,scenarios=str(scenario_path),pid=os.getpid(),repo=str(repo),static=str(app.static_dir) if hasattr(app,'static_dir') else str(repo/'_internal/abook/webui/static'))
            (root/'ready.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
            print(json.dumps(metadata),flush=True)
        sys.stdin.readline()  # parent closes stdin to request graceful shutdown
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        app.close()

if __name__=='__main__': main()

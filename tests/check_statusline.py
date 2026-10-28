"""Windows integration check using a mock payload; never prints user config."""
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

settings = json.loads((Path.home()/'.claude/settings.json').read_text(encoding='utf-8-sig'))
command = settings['statusLine']['command']
assert 'statusline_wrapper.py' not in command, 'Statusline still invokes wrapper'
script = (Path.home()/'.claude/statusline-command.sh').read_text(encoding='utf-8-sig')
assert 'statusline_wrapper.py' not in script, 'Script still invokes wrapper'
assert 'collector.py' in script, 'Collector tap missing'
fixture = json.dumps({'model':{'display_name':'Opus'},'cwd':str(Path.cwd()),
                     'workspace':{'current_dir':str(Path.cwd())},
                     'context_window':{'used_percentage':25},'session_id':'usage-verification',
                     'rate_limits':{'five_hour':{'used_percentage':12,'resets_at':1990000000},
                                    'seven_day':{'used_percentage':34,'resets_at':1990000000}},
                     'test_secret':'NEVER_PERSIST_THIS'}).encode()
with tempfile.TemporaryDirectory(prefix='aiusage-direct-') as temp:
    start = time.monotonic()
    result = subprocess.run(['C:/Program Files/Git/bin/bash.exe','-c',command],input=fixture,
                            env=dict(os.environ,LOCALAPPDATA=temp),capture_output=True,timeout=10)
    assert result.returncode == 0, 'Statusline command failed'
    assert result.stdout.strip(), 'Statusline output is empty'
    assert not result.stderr, 'Statusline emitted an error'
    elapsed = time.monotonic()-start
    cached = Path(temp)/'AIUsageStreamDeck/claude.json'
    for _ in range(30):
        if cached.is_file():
            break
        time.sleep(0.1)
    text = cached.read_text(encoding='utf-8')
    assert 'NEVER_PERSIST_THIS' not in text
    assert json.loads(text)['five_hour']['used'] == 12
    print(f'PASS: original command, nonempty output, no stderr, no wrapper, sanitized collector cache ({elapsed:.2f}s)')

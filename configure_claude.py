"""Restore a previous Claude statusline and remove the old Stream Deck tap from it.

Never replace an unrelated statusline. Only modify our wrapper setting or a
script which already contains the StreamDeck AI-usage marker.
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path


def backup(path):
    target = path.with_name(path.name + '.aiusage-repair-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    target.write_bytes(path.read_bytes())


def previous_statusline(settings_path):
    previous_path = Path(os.environ['LOCALAPPDATA'])/'AIUsageStreamDeck/previous-statusline.json'
    if previous_path.is_file():
        previous = json.loads(previous_path.read_text(encoding='utf-8-sig'))
        command = previous.get('command')
        if command and 'statusline_wrapper.py' not in command:
            return {'type':'command','command':command}
    # Early installers could leave the wrapper configured without this file.
    candidates = sorted(settings_path.parent.glob('settings.json.aiusage-backup-*'),
                        key=lambda p:p.stat().st_mtime, reverse=True)
    for candidate in candidates:
        try:
            status = json.loads(candidate.read_text(encoding='utf-8-sig')).get('statusLine')
            if status and 'statusline_wrapper.py' not in status.get('command',''):
                return status
        except (OSError, ValueError):
            continue
    raise ValueError('Original statusline was not found in the saved settings backups')


def configure():
    settings_path = Path.home()/'.claude/settings.json'
    if not settings_path.is_file():
        return
    settings = json.loads(settings_path.read_text(encoding='utf-8-sig'))
    status = settings.get('statusLine') or {}
    command = status.get('command') or ''
    if 'com.local.aiusage.sdPlugin' in command and 'statusline_wrapper.py' in command:
        previous = previous_statusline(settings_path)
        command = previous.get('command') or ''
        if 'statusline_wrapper.py' in command:
            raise ValueError('Previous statusline must not point to the wrapper')
        backup(settings_path)
        if command:
            settings['statusLine'] = previous
        else:
            settings.pop('statusLine', None)
        # Claude's settings stay UTF-8 without the Windows PowerShell BOM.
        settings_path.write_text(json.dumps(settings,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    script = Path.home()/'.claude/statusline-command.sh'
    if 'statusline-command.sh' not in command or not script.is_file():
        print('Original statusline preserved. See README for the optional collector tap.')
        return
    content = script.read_text(encoding='utf-8-sig')
    marker = '# --- StreamDeck AI-usage side-effect'
    if marker not in content:
        print('Original statusline preserved. See README for the optional collector tap.')
        return
    # The collector now reads the usage API and each account's usage-cache.json by itself,
    # so the old background tap (which could leave Git Bash processes behind) is removed.
    stripped, count = re.subn(r'# --- StreamDeck AI-usage side-effect.*?(?=model="")', 'sd_out=""\n\n', content, count=1, flags=re.S)
    if count != 1:
        raise ValueError('Existing collector block not found')
    backup(script)
    script.write_text(stripped, encoding='utf-8', newline='\n')
    print('Original Claude statusline restored; Stream Deck collector tap removed.')


if __name__ == '__main__':
    configure()

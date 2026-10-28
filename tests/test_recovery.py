import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from configure_claude import previous_statusline


class RecoveryTests(unittest.TestCase):
    def test_missing_previous_file_uses_original_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current = root/'settings.json'
            original = {'type':'command','command':'bash ~/.claude/statusline-command.sh'}
            (root/'settings.json.aiusage-backup-1').write_text(json.dumps({'statusLine':original}))
            (root/'settings.json.aiusage-backup-2').write_text(json.dumps({'statusLine':{
                'type':'command','command':'python statusline_wrapper.py'}}))
            with patch.dict(os.environ,LOCALAPPDATA=temp):
                self.assertEqual(previous_statusline(current),original)


if __name__ == '__main__':
    unittest.main()

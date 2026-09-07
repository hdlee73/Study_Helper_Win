"""Offline regression tests: backend functions only, no GUI/network/model downloads."""
import ast
import asyncio
import html
import os
from pathlib import Path
import re
import tempfile
import unittest
import pandas as pd

SOURCE = Path(__file__).with_name('study_helper.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)
NAMES = {'sanitize_filename', 'split_sentences', 'dedupe_df', 'atomic_write', 'save_rows_to_excel',
         'pandas_module', 'find_anki_executable', 'import_excel_to_anki', 'render_audio_plan',
         'calculate_pause_seconds', 'detect_lang'}
NS = dict(Path=Path, os=os, re=re, tempfile=tempfile, PANDAS=pd, List=list, html=html,
          asyncio=asyncio, shutil=__import__('shutil'), time=__import__('time'),
          subprocess=__import__('subprocess'), requests=__import__('requests'))
exec(compile(ast.Module(body=[n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name in NAMES],type_ignores=[]), '<backend>', 'exec'), NS)

class RegressionTests(unittest.TestCase):
    def test_heavy_dependencies_are_lazy(self):
        top_imports = set()
        for node in TREE.body:
            if isinstance(node, ast.Import):
                top_imports.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                top_imports.add(node.module.split('.')[0])
        self.assertTrue({'pandas', 'yt_dlp', 'edge_tts', 'fpdf', 'deep_translator'}.isdisjoint(top_imports))

    def test_configured_anki_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / 'Anki.exe'
            executable.write_bytes(b'test')
            NS['CONFIG'] = {'anki_executable': str(executable)}
            self.assertEqual(NS['find_anki_executable'](), executable)

    def test_windows_names(self):
        for raw in ('CON', 'NUL.txt', 'a/b:c', 'hello.', '../escape'):
            safe = NS['sanitize_filename'](raw)
            self.assertNotRegex(safe, r'[\\/:*?"<>|]')
            self.assertFalse(safe.endswith('.'))
        self.assertEqual(NS['sanitize_filename']('CON'), '_CON')

    def test_korean_sentence(self):
        self.assertEqual(NS['split_sentences'](['바다 위로 새가 날아요. 다음 문장입니다.']),
                         ['바다 위로 새가 날아요.', '다음 문장입니다.'])

    def test_excel_append_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'한국어.xlsx'
            NS['save_rows_to_excel']([['안녕','hello','one']], str(target))
            _, count=NS['save_rows_to_excel']([['안녕','hello','one'],['둘','two','two']],str(target))
            self.assertEqual(count,2)
            self.assertEqual(pd.read_excel(target,header=None).iloc[0,0],'안녕')

    def test_corrupt_excel_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'broken.xlsx'; target.write_bytes(b'original content')
            with self.assertRaises(Exception): NS['save_rows_to_excel']([['a','b','c']],str(target))
            self.assertEqual(target.read_bytes(),b'original content')

    def test_failed_atomic_write_preserves_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'test.txt'; target.write_text('old')
            def fail(p):
                p.write_text('partial')
                raise RuntimeError('simulated failure')
            with self.assertRaises(RuntimeError): NS['atomic_write'](target,fail)
            self.assertEqual(target.read_text(),'old')
            self.assertEqual(len(list(Path(tmp).iterdir())),1)

    def test_workers_have_no_tk_reads(self):
        for task in ast.walk(TREE):
            if isinstance(task,ast.FunctionDef) and task.name=='task':
                for call in ast.walk(task):
                    if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute):
                        self.assertNotEqual(call.func.attr,'after')
                        if call.func.attr=='get' and isinstance(call.func.value,ast.Attribute):
                            self.assertNotEqual(ast.unparse(call.func.value.value),'self')

    def test_audio_cache_order_cleanup(self):
        generated=[]; parts=[]
        async def tts(text, voice, path):
            generated.append((text,voice)); Path(path).write_bytes(b'audio')
        NS.update(require_ffmpeg=lambda:'mock', save_tts_line=tts,
                  make_silence_mp3=lambda seconds,path:Path(path).write_bytes(b'silence'),
                  concat_mp3_files=lambda files,target:parts.extend(files))
        NS['render_audio_plan']([('hello','voice'),(1,None),('hello','voice')],'unused.mp3')
        self.assertEqual(generated,[('hello','voice')])
        self.assertEqual(parts[0],parts[2])
        self.assertTrue(all(not Path(p).exists() for p in parts))

    def test_anki_scope_escape_and_counts(self):
        calls=[]
        def request(action, **kw):
            calls.append((action,kw))
            return {'version':6,'modelNames':['English'],'modelFieldNames':['Front','Back','Example'],
                    'createDeck':1,'findNotes':[], 'addNotes':[123]}.get(action)
        NS.update(CONFIG={'anki_note_type':'English'},anki_request=request)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.xlsx'
            pd.DataFrame([['<b>','&','x']]).to_excel(p,index=False,header=False)
            result=NS['import_excel_to_anki'](str(p),'A "quoted" deck')
        self.assertEqual(result[1:],(1,0,1))
        query=next(kw['query'] for a,kw in calls if a=='findNotes')
        self.assertIn('deck:"A \\"quoted\\" deck"',query)
        note=next(kw['notes'][0] for a,kw in calls if a=='addNotes')
        self.assertEqual(note['fields']['Front'],'&lt;b&gt;')

if __name__=='__main__': unittest.main(verbosity=2)

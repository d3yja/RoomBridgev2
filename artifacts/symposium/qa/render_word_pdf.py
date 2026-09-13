"""Use Word's PDF conversion with the packaged renderer's rasterisation step."""
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = Path('C:/Users/hp/.cache/codex-runtimes/codex-primary-runtime/dependencies')
poppler = next((RUNTIME / 'native' / 'poppler').rglob('pdftoppm.exe')).parent
os.environ['PATH'] = str(poppler) + os.pathsep + os.environ.get('PATH', '')
source = Path('C:/Users/hp/.codex/plugins/cache/openai-primary-runtime/documents/26.905.11957/skills/documents/render_docx.py')
spec = importlib.util.spec_from_file_location('docx_renderer', source)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
stem = sys.argv[1] if len(sys.argv) > 1 else 'RoomBridge_Symposium_Abstract'
pdf = HERE / f'{stem}.pdf'
renderer.convert_to_pdf = lambda *args, **kwargs: (str(pdf), 'Converted using Microsoft Word')
pages = renderer.rasterize(str(HERE.parent / f'{stem}.docx'),
                          str(HERE / f'render_{stem}'), 130, False, False)
print('\n'.join(pages))

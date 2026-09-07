"""Preserve installed distribution metadata and license files in the frozen distribution."""
from importlib.metadata import distributions
from pathlib import Path
import shutil

target = Path('THIRD_PARTY_NOTICES')
target.mkdir(exist_ok=True)
index = ['# Installed third-party distributions', '',
         'These notices describe dependencies; they do not license Study Helper itself.', '']
for dist in sorted(distributions(), key=lambda d: d.metadata.get('Name','').lower()):
    name = dist.metadata.get('Name', 'unknown')
    folder = target / (name + '-' + dist.version)
    folder.mkdir(exist_ok=True)
    metadata = dist.read_text('METADATA') or ''
    (folder / 'METADATA.txt').write_text(metadata, encoding='utf-8')
    count=0
    for file in dist.files or []:
        if any(word in str(file).lower() for word in ('license','copying','notice')):
            source=Path(dist.locate_file(file))
            if source.is_file():
                dest=folder / str(file).replace('..','_').replace('\\','_').replace('/','_')
                shutil.copy2(source,dest)
                count+=1
    index.append(f'- {name} {dist.version}: {count} license/notice files; see METADATA for upstream links.')
(target/'INDEX.md').write_text('\n'.join(index)+'\n', encoding='utf-8')

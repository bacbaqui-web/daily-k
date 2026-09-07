from pathlib import Path
import shutil,re
root=Path(__file__).resolve().parents[1];out=root/'dist/client';target=root/'docs'
if target.exists():shutil.rmtree(target)
shutil.copytree(out,target)
nested=target/'daily-k'
if nested.exists():
 for item in nested.iterdir():
  dest=target/item.name
  if item.is_dir():shutil.copytree(item,dest,dirs_exist_ok=True)
  else:shutil.copy2(item,dest)
 shutil.rmtree(nested)
(target/'.nojekyll').touch()
for url in set(re.findall(r'(?:src|href)="([^"]+)"',(target/'index.html').read_text())):
 if url.startswith('/daily-k/'):
  assert (target/url.removeprefix('/daily-k/')).exists(),url
print('GitHub Pages assets verified')

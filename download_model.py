"""Download public model weights only. Never reads the user's reference audio."""
import pathlib,json,urllib.request,hashlib,time
from config import workspace
ROOT=workspace()/'voice-clone'
ROOT.mkdir(parents=True,exist_ok=True)
REPO='Qwen/Qwen3-TTS-12Hz-0.6B-Base'
REV='5d83992436eae1d760afd27aff78a71d676296fc'
model=ROOT/'model';model.mkdir(exist_ok=True)
with urllib.request.urlopen(f'https://huggingface.co/api/models/{REPO}/revision/{REV}?blobs=true',timeout=60) as response: meta=json.load(response)
files=[]
for item in meta['siblings']:
    name=item['rfilename']
    if not name.endswith(('.json','.txt','.safetensors')): continue
    from config import safe_child
    target=safe_child(model,name);target.parent.mkdir(parents=True,exist_ok=True)
    expected=item.get('lfs',{}).get('sha256'); size=item.get('size')
    if not target.exists() or (size and target.stat().st_size!=size):
        partial=target.with_suffix(target.suffix+'.partial');h=hashlib.sha256();last=time.monotonic();done=0
        print('Downloading '+name,flush=True)
        with urllib.request.urlopen(f'https://huggingface.co/{REPO}/resolve/{REV}/{name}',timeout=120) as src,partial.open('wb') as dst:
            while chunk:=src.read(1024*1024):
                dst.write(chunk);h.update(chunk);done+=len(chunk)
                if time.monotonic()-last>15:
                    print(f'{name}: {done//1048576} MiB',flush=True);last=time.monotonic()
        if size and done!=size: raise RuntimeError('Incomplete download: '+name)
        if expected and h.hexdigest()!=expected: raise RuntimeError('SHA256 mismatch: '+name)
        partial.replace(target)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    if expected and digest!=expected: raise RuntimeError('SHA256 mismatch: '+name)
    files.append({'file':name,'bytes':target.stat().st_size,'sha256':digest,'verified_lfs':bool(expected)})
(ROOT/'model-manifest.json').write_text(json.dumps({'repository':REPO,'revision':REV,'files':files},indent=2),encoding='utf-8')
print('MODEL_DOWNLOAD_VERIFIED',flush=True)

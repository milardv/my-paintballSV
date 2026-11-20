#!/usr/bin/env python3
"""Copy embedded original images without changing their pixels; Unity handles web import."""
import json, pathlib, re, struct
root=pathlib.Path(__file__).resolve().parent.parent
out=root/'unity/Assets/Chateau/Paintball/WebTextures'
out.mkdir(parents=True,exist_ok=True)
manifest=[]
for p in sorted((root/'export/composants').glob('*.glb')):
    b=p.read_bytes(); n=struct.unpack_from('<I',b,12)[0]; data=json.loads(b[20:20+n]); offset=28+n
    for i,im in enumerate(data.get('images',[])):
        if 'bufferView' not in im: continue
        name=im.get('name',f'image_{i}');view=data['bufferViews'][im['bufferView']]
        ext='.jpg' if im.get('mimeType')=='image/jpeg' else '.png'
        filename=p.stem+'__'+re.sub(r'[^a-zA-Z0-9_-]','_',name)+ext
        dest=out/filename
        content=b[offset+view.get('byteOffset',0):offset+view.get('byteOffset',0)+view['byteLength']]
        if not dest.exists() or dest.read_bytes()!=content: dest.write_bytes(content)
        manifest.append(dict(source=p.stem,texture=name,path='Assets/Chateau/Paintball/WebTextures/'+filename))
(out/'manifest.json').write_text(json.dumps(dict(images=manifest),indent=2))
print(f'{len(manifest)} images originales extraites pour compression Unity.')

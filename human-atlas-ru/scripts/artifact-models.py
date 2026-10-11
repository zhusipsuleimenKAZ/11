"""Prepare dist/ for hosts that refuse .gz files (e.g. claude.ai artifacts).

Base64-encodes every dist/models/*.bin.gz into *.bin.gz.txt, deletes the
originals and points atlas.json at the .txt files. app/model-download.ts
decodes .txt responses back to gzip bytes.
"""
import base64, glob, json, os

models = os.path.join(os.path.dirname(__file__), '..', 'dist', 'models')
for path in glob.glob(os.path.join(models, 'body-*.bin*')):
    if path.endswith('.bin.gz'):
        with open(path, 'rb') as src, open(path + '.txt', 'w') as out:
            out.write(base64.b64encode(src.read()).decode())
    if not path.endswith('.txt'):
        os.remove(path)
atlas = os.path.join(models, 'atlas.json')
data = json.load(open(atlas))
for chunk in data['chunks']:
    if not chunk['gzip'].endswith('.txt'):
        chunk['gzip'] += '.txt'
json.dump(data, open(atlas, 'w'), separators=(',', ':'))

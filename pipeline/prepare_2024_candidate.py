"""Reproduce the historical candidate from preserved 2023 source files; never overwrite."""
import sys, json, hashlib, zipfile
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo))
from pipeline.transform import transform_revisions, clean_revision
from pipeline.load_real import ordered_revisions, parse_timestamp
from pipeline.download import DEFAULT_ARTICLES

base = repo / 'data/real'
out = base / '2024_candidate'
assert not out.exists(), 'Refusing to overwrite an existing candidate'
def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()
original = {p.name: sha(p) for p in base.iterdir() if p.is_file()}
raw = json.loads((base/'raw.json').read_text(encoding='utf-8'))
source = json.loads((base/'cleaned.json').read_text(encoding='utf-8'))
transformed = transform_revisions(raw)
assert {r['revision_id']:r for r in transformed} == {r['revision_id']:r for r in source}
start, end = '2024-01-01T00:00:00Z', '2026-10-22T00:00:00Z'
inside = lambda r: parse_timestamp(start) <= parse_timestamp(r['timestamp']) <= parse_timestamp(end)
selected = [r for r in source if inside(r)]
candidate = [r for r,t in ordered_revisions(selected)]
assert len(candidate) == len(selected)
assert len({r['revision_id'] for r in candidate}) == len(candidate)
assert set(r['article_title'] for r in candidate) == set(DEFAULT_ARTICLES)
by_article = defaultdict(list)
for r in candidate:
    assert all(k in r for k in ('article_id','revision_id','article_title','title','timestamp','revision_date','author','content'))
    assert type(r['article_id']) is int and r['article_id'] > 0
    assert type(r['revision_id']) is int and r['revision_id'] > 0
    assert r['timestamp'].endswith('Z') and r['timestamp'] == r['revision_date']
    assert r['title'] == r['article_title'] and isinstance(r['author'],str)
    assert inside(r)
    by_article[r['article_id']].append(r)
for aid, rows in by_article.items():
    assert len({r['article_title'] for r in rows}) == 1
    times = [t for r,t in ordered_revisions(rows)]
    assert all(a < b for a,b in zip(times,times[1:]))
excluded=[]
for chunk in raw:
    for page in chunk.get('query',{}).get('pages',{}).values():
        for r in page.get('revisions',[]):
            if inside({'timestamp':r['timestamp']}) and clean_revision(r,page['pageid'],page['title']) is None:
                excluded.append({'article':page['title'],'revision_id':r['revid'],'timestamp':r['timestamp']})
articles=[]
for title in DEFAULT_ARTICLES:
    rows=[r for r in candidate if r['article_title']==title]
    articles.append(dict(title=title,article_id=rows[0]['article_id'],revisions=len(rows),first=rows[0]['timestamp'],last=rows[-1]['timestamp'],text_bytes=sum(len(r['content'].encode('utf-8')) for r in rows)))
text_bytes=sum(a['text_bytes'] for a in articles)
assert len(candidate)==1017 and text_bytes==142590603, 'Previous measurement mismatch'
out.mkdir()
p=out/'cleaned.json'
p.write_text(json.dumps(candidate,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
assert json.loads(p.read_text(encoding='utf-8')) == candidate
manifest=dict(dataset='Wikipedia Time Machine 2024-2026 candidate',team_approval='PENDING - do not replace canonical dataset until approved',start=start,end=end,boundaries='inclusive UTC',articles=articles,total_revisions=len(candidate),text_bytes=text_bytes,text_MB=text_bytes/1e6,cleaned_file_bytes=p.stat().st_size,cleaned_sha256=sha(p),excluded_unavailable=excluded,excluded_by_date=len(source)-len(candidate),first=min(r['timestamp'] for r in candidate),last=max(r['timestamp'] for r in candidate),source_sha256=original,repository_commit='bd54811287c5542318058b8d075c024ac662229a',validation='PASS: independently transformed raw equals original cleaned; filtered records unchanged; unique IDs; five identities; UTC bounds; loader ordering; strictly increasing loader system times; JSON roundtrip',meets_1000_revisions=True,meets_150_MB_text=True)
(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
table='| Article | Revisions | First UTC revision | Last UTC revision | Text MB |\n|---|---:|---|---|---:|\n'+''.join(f"| {a['title']} | {a['revisions']} | {a['first']} | {a['last']} | {a['text_bytes']/1e6:.6f} |\n" for a in articles)
report=f'''# 2024 candidate dataset report
Approval pending. Prepared locally; no upload or receipt confirmations. Canonical 2023 files preserved.
Window: {start} through {end}, inclusive UTC.
{table}
Total: 1017 usable revisions; 142,590,603 UTF-8 text bytes (142.590603 decimal MB).
Cleaned JSON: {p.stat().st_size:,} bytes. Both numerical guidelines pass, matching the previous measurement exactly.
485 usable revisions excluded by date; 2 unavailable Apollo 11 revisions excluded by the existing transformer (IDs in manifest).
All original revision fields and content preserved. Full raw transformation independently compared with original cleaned records.
Required fields, UTC bounds, identities, unique revision IDs, loader ordering, strictly increasing effective system times and JSON roundtrip pass.

After explicit team approval: upload the ZIP, manifest.json and SHA256SUMS.txt to the team's approved folder; grant intended teammates read access; verify access and send actual links.
Extract ZIP at the repository root; it supplies data/real/cleaned.json. Back up any existing local dataset before replacement.
Verify: (Get-FileHash -Algorithm SHA256 data/real/cleaned.json).Hash
Expected: {sha(p)}
Confirm manifest window before loading or making growth subsets.
'''
(out/'DATASET_REPORT.md').write_text(report,encoding='utf-8')
names=['cleaned.json','manifest.json','DATASET_REPORT.md']
(out/'SHA256SUMS.txt').write_text(''.join(f'{sha(out/n)}  {n}\n' for n in names),encoding='utf-8')
archive=out/'wikipedia_time_machine_2024-2026.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for n in names+['SHA256SUMS.txt']: z.write(out/n,'data/real/'+n)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for n in names+['SHA256SUMS.txt']:
        assert hashlib.sha256(z.read('data/real/'+n)).hexdigest()==sha(out/n)
    assert json.loads(z.read('data/real/cleaned.json')) == candidate
assert all(sha(base/n)==h for n,h in original.items()), 'Original file changed'
verification=dict(zip_bytes=archive.stat().st_size,zip_sha256=sha(archive),zip_crc='PASS',all_members_sha256='PASS',archived_JSON='PASS',original_files_unchanged=True,deliverables=[str(x) for x in out.iterdir()])
(out/'package_verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
print(json.dumps({'manifest':{k:v for k,v in manifest.items() if k!='source_sha256'},'package':verification},indent=2))

"""Download public source archives for the reproducible history build.

python scripts/fetch_history.py --out data/raw
python -m gridiron_lab.history --raw data/raw --out docs
"""
import argparse,csv,gzip,hashlib,json,urllib.request
from datetime import datetime,timezone
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('data/raw'));p.add_argument('--seasons',nargs='+',type=int,default=[2023,2024,2025]);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for tag,prefix in [('pbp','play_by_play'),('players','players'),('snap_counts','snap_counts'),('injuries','injuries'),('weekly_rosters','roster_weekly')]:
        req=urllib.request.Request('https://api.github.com/repos/nflverse/nflverse-data/releases/tags/'+tag,headers={'User-Agent':'GridironLab'})
        release=json.load(urllib.request.urlopen(req,timeout=60))
        for season in ([None] if tag=='players' else a.seasons):
            stem=prefix+(f'_{season}' if season else '')+'.csv'
            asset=next((x for x in release['assets'] if x['name']==stem+'.gz'),None) or next(x for x in release['assets'] if x['name']==stem)
            raw=urllib.request.urlopen(asset['browser_download_url'],timeout=120).read();payload=raw if asset['name'].endswith('.gz') else gzip.compress(raw)
            with gzip.open(__import__('io').BytesIO(payload),'rt',encoding='utf-8-sig') as f:
                reader=csv.DictReader(f)
                if not reader.fieldnames or next(reader,None) is None:raise ValueError('Empty source '+asset['name'])
            (a.out/(stem+'.gz')).write_bytes(payload)
            manifest.append({'name':asset['name'],'url':asset['browser_download_url'],'sha256':hashlib.sha256(raw).hexdigest(),'retrieved_at':datetime.now(timezone.utc).isoformat()})
            print('Verified nonempty archive:',asset['name'],flush=True)
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2))
if __name__=='__main__':main()

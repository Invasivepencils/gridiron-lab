"""Compress derived historical snapshots for the public browser site."""
import gzip
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'docs'
for season in (2023, 2024, 2025):
    source = root / f'history-{season}.json'
    raw = source.read_bytes()
    packed = gzip.compress(raw, compresslevel=9, mtime=0)
    assert gzip.decompress(packed) == raw
    source.with_suffix('.json.gz').write_bytes(packed)
    print(f'{season}: {len(raw):,} -> {len(packed):,} bytes')

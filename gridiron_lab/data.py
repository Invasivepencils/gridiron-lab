"""Validated local data and optional nflverse acquisition."""
import csv
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from .engine import Game, Injury, timestamp


def read_games(path):
    games = []
    with open(path, newline='', encoding='utf-8-sig') as handle:
        for row in csv.DictReader(handle):
            games.append(Game(row['game_id'], int(row['season']), int(row['week']),
                              timestamp(row['kickoff']), row['home'], row['away'],
                              float(row['home_score']) if row['home_score'] else None,
                              float(row['away_score']) if row['away_score'] else None,
                              timestamp(row['result_available_at']) if row['result_available_at'] else None,
                              row.get('neutral', 'false').lower() == 'true'))
    if len({g.game_id for g in games}) != len(games):
        raise ValueError('Duplicate game IDs')
    return games


def read_injuries(path):
    if path is None:
        return []
    with open(path, newline='', encoding='utf-8-sig') as handle:
        return [Injury(row['game_id'], row['team'], row['player_id'], timestamp(row['observed_at']),
                       float(row['absence_probability']), float(row['impact_points']), float(row['impact_sd']),
                       timestamp(row['impact_available_at']), row['source']) for row in csv.DictReader(handle)]


def fingerprint(path):
    return {'file': str(path), 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def download(seasons, destination):
    """Archive provider tables without pretending dates are publication timestamps."""
    try:
        import nflreadpy as nfl
    except ImportError as exc:
        raise RuntimeError('Install the data extra: python -m pip install -e ".[data]"') from exc
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    manifest = {'provider': 'nflverse via nflreadpy', 'seasons': seasons,
                'retrieved_at': datetime.now(timezone.utc).isoformat(), 'datasets': [],
                'note': 'Hashes verify file integrity, not factual accuracy or historical publication time.'}
    loaders = {'schedules': nfl.load_schedules, 'player_stats': nfl.load_player_stats,
               'team_stats': nfl.load_team_stats, 'injuries': nfl.load_injuries,
               'snap_counts': nfl.load_snap_counts}
    for name, loader in loaders.items():
        try:
            frame = loader(seasons)
            path = root / (name + '.csv')
            frame.write_csv(path)
            record = {'dataset': name, 'rows': frame.height, **fingerprint(path)}
            if 'season' in frame.columns:
                record['seasons_present'] = sorted(frame['season'].drop_nulls().unique().to_list())
                record['missing_requested_seasons'] = sorted(set(seasons) - set(record['seasons_present']))
            record['status'] = 'downloaded' if frame.height else 'empty'
            manifest['datasets'].append(record)
        except Exception as exc:
            manifest['datasets'].append({'dataset': name, 'status': 'unavailable', 'error': str(exc)})
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest

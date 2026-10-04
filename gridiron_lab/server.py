"""Local research UI. No trading, arbitrary file reads, or external services."""
import argparse
import json
import tempfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .data import read_games, read_injuries
from .engine import backtest, timestamp
from .bayes import fit, predict

ROOT = Path(__file__).resolve().parent.parent
WEB = Path(__file__).resolve().parent / 'web'


def analyze(payload):
    with tempfile.TemporaryDirectory(prefix='gridiron-') as temp:
        games_path = Path(temp)/'games.csv'
        injuries_path = Path(temp)/'injuries.csv'
        games_path.write_text(payload['games_csv'],encoding='utf-8')
        games = read_games(games_path)
        if payload.get('action') == 'inspect':
            return {'games':[{'game_id':g.game_id,'home':g.home,'away':g.away,'kickoff':g.kickoff.isoformat(),
                              'completed':g.home_score is not None} for g in games]}
        injuries = []
        if payload.get('injuries_csv'):
            injuries_path.write_text(payload['injuries_csv'],encoding='utf-8')
            injuries = read_injuries(injuries_path)
        ids = {g.game_id for g in games}
        if any(i.game_id not in ids for i in injuries): raise ValueError('Unknown game ID in injuries')
        if payload.get('action') == 'backtest':
            if len(games)>2500: raise ValueError('Browser backtesting supports at most 2500 games; use the CLI for larger data')
            return backtest(games,injuries,24,1000,7,'bayesian')
        game = next((g for g in games if g.game_id == payload['game_id']),None)
        if game is None: raise ValueError('Select a valid game ID')
        cutoff = timestamp(payload['cutoff'])
        return predict(fit(games,game,cutoff),game,injuries,cutoff,10000,7)


class Handler(BaseHTTPRequestHandler):
    def respond(self,body,status=200,kind='application/json'):
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.path = urlsplit(self.path).path
        if self.path == '/api/demo':
            data = {'games_csv':(ROOT/'examples/games.csv').read_text(),
                    'injuries_csv':(ROOT/'examples/injuries.csv').read_text(),
                    'game_id':'DEMO_4','cutoff':'2024-09-28T17:00:00Z'}
            self.respond(json.dumps(data).encode())
            return
        paths = {'/':('index.html','text/html; charset=utf-8'),
                 '/app.css':('app.css','text/css; charset=utf-8'),
                 '/app.js':('app.js','text/javascript; charset=utf-8'),
                 '/experiment.html':('experiment.html','text/html; charset=utf-8'),
                 '/history.css':('history.css','text/css; charset=utf-8'),
                 '/history.js':('history.js','text/javascript; charset=utf-8')}
        if self.path in {'/history-index.json','/history-2023.json','/history-2024.json','/history-2025.json'}:
            file=ROOT/'docs'/self.path.lstrip('/')
            if not file.exists():self.respond(b'{"error":"Build historical data first"}',404);return
            self.respond(file.read_bytes());return
        if self.path not in paths:
            self.respond(b'{"error":"Not found"}',404); return
        name,kind = paths[self.path]
        self.respond((WEB/name).read_bytes(),kind=kind)

    def do_POST(self):
        if self.path != '/api/analyze': self.respond(b'{}',404); return
        try:
            size = int(self.headers.get('Content-Length','0'))
            if not 0<size<=2_000_000: raise ValueError('Upload limit is 2 MB')
            payload = json.loads(self.rfile.read(size))
            report = analyze(payload)
            self.respond(json.dumps(report,allow_nan=False).encode())
        except (ValueError,KeyError,TypeError) as exc:
            self.respond(json.dumps({'error':str(exc)}).encode(),400)


def main():
    parser = argparse.ArgumentParser(description='Launch the local Gridiron Lab research UI')
    parser.add_argument('--port',type=int,default=8081)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'Gridiron Lab: http://127.0.0.1:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == '__main__': main()

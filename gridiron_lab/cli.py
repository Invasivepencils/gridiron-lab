import argparse
import json
from pathlib import Path
from .data import download, fingerprint, read_games, read_injuries
from .engine import backtest, fit_before, forecast, timestamp


def main():
    parser = argparse.ArgumentParser(description='NFL strength and injury-scenario research')
    sub = parser.add_subparsers(dest='command', required=True)
    fetch = sub.add_parser('fetch', help='Archive public nflverse tables (optional data extra)')
    fetch.add_argument('--seasons', nargs='+', type=int, required=True)
    fetch.add_argument('--out', default='data/raw')
    for name in ('backtest', 'forecast'):
        command = sub.add_parser(name)
        command.add_argument('--games', required=True)
        command.add_argument('--injuries')
        command.add_argument('--out', required=True)
        command.add_argument('--simulations', type=int, default=2000)
        command.add_argument('--seed', type=int, default=7)
        command.add_argument('--model', choices=['baseline', 'bayesian'], default='bayesian')
        if name == 'backtest':
            command.add_argument('--hours-before', type=float, default=24)
        else:
            command.add_argument('--game-id', required=True)
            command.add_argument('--cutoff', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'fetch':
            report = download(args.seasons, args.out)
            print(json.dumps(report, indent=2))
            return
        games = read_games(args.games)
        injuries = read_injuries(args.injuries)
        known_ids = {g.game_id for g in games}
        if any(i.game_id not in known_ids for i in injuries):
            raise ValueError('Injury contains an unknown game ID')
        if args.command == 'backtest':
            report = backtest(games, injuries, args.hours_before, args.simulations, args.seed, args.model)
        else:
            game = next((g for g in games if g.game_id == args.game_id), None)
            if game is None:
                raise ValueError('Unknown game ID')
            cutoff = timestamp(args.cutoff)
            if args.model == 'bayesian':
                from .bayes import fit, predict
                report = predict(fit(games, game, cutoff), game, injuries, cutoff, args.simulations, args.seed)
            else:
                model = fit_before(games, cutoff, game.season)
                report = forecast(model, game, injuries, cutoff, args.simulations, args.seed)
        report['inputs'] = [fingerprint(args.games)] + ([fingerprint(args.injuries)] if args.injuries else [])
        report['run_config'] = vars(args)
        destination = Path(args.out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print('Saved ' + str(destination))
    except (ValueError, KeyError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()

"""Launch T3 with an exclusive console log; refuse existing experiment artifacts."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('config')
    a = p.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    name = cfg['name']
    if Path(name).name != name:
        raise ValueError('Invalid experiment name')
    console = Path('results') / (name + '.console.log')
    if any(path.exists() for path in [console, Path('results') / name, Path('checkpoints') / name]):
        raise FileExistsError('Existing artifacts are protected; create a config with a new name')
    with console.open('x') as f:
        result = subprocess.run([sys.executable, '-u', '-m', 'src.t3_train', a.config],
                                stdout=f, stderr=subprocess.STDOUT)
    print(f'Console: {console}; exit_code: {result.returncode}')
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()

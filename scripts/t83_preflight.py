"""Read-only checks for the formal 8797 launcher. Uses only the Python standard library."""
import argparse
from html.parser import HTMLParser
from http.client import HTTPConnection, HTTPException
import json
from pathlib import Path
import re
import socket
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'web/human-signal/dist-t72'
ORIGIN = 'http://127.0.0.1:8797'
RUNBOOK = 'docs/T83_START_STOP.md'
MODELS = [('w32', 93), ('t3', 56), ('w16', 97)]
LABELS = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']
CSS_URL = re.compile(r'''url\(\s*["']?([^"')]+)["']?\s*\)''')


class ReleasePage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.release = None
        self.scripts, self.styles, self.icons = [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('name') == 'emotionlab-release':
            self.release = attrs.get('content')
        elif tag == 'script' and 'src' in attrs:
            self.scripts.append(attrs['src'])
        elif tag == 'link' and 'href' in attrs:
            rel = (attrs.get('rel') or '').split()
            if 'stylesheet' in rel:
                self.styles.append(attrs['href'])
            if 'icon' in rel:
                self.icons.append(attrs['href'])


def checked_asset(url, relative_to=DIST):
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc:
        raise ValueError('正式构建引用了外部资源：' + url)
    path = unquote(parsed.path)
    asset = ((DIST / path.lstrip('/')) if path.startswith('/') else (relative_to / path)).resolve()
    if not asset.is_relative_to(DIST.resolve()) or not asset.is_file() or asset.stat().st_size == 0:
        raise ValueError('前端构建资源缺失、为空或不在发布目录：' + url)
    return asset


def local_release():
    index = DIST / 'index.html'
    if not index.is_file():
        raise ValueError('缺少正式前端构建 web/human-signal/dist-t72/index.html')
    body = index.read_bytes()
    page = ReleasePage()
    page.feed(body.decode('utf-8'))
    if page.release != 'human-signal-t72' or not all((page.scripts, page.styles, page.icons)):
        raise ValueError('正式首页缺少 T7.2 发布标记、脚本、样式或图标')
    assets = {checked_asset(url) for url in page.scripts + page.styles + page.icons}
    for url in page.styles:
        stylesheet = checked_asset(url)
        for ref in CSS_URL.findall(stylesheet.read_text(encoding='utf-8')):
            ref = ref.strip()
            if not ref.startswith(('#', 'data:')):
                assets.add(checked_asset(ref, stylesheet.parent))
    return body, assets


def port_free():
    with socket.socket() as probe:
        # A recently closed connection should not veto a valid restart.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(('127.0.0.1', 8797))
            probe.listen(1)
        except OSError:
            return False
    return True


def same_ready_service(index):
    def read(path, limit):
        connection = HTTPConnection('127.0.0.1', 8797, timeout=1.5)
        try:
            connection.request('GET', path)
            with connection.getresponse() as response:
                return response.read(limit) if response.status == 200 else b''
        finally:
            connection.close()

    try:
        if read('/', len(index) + 1) != index:
            return False
        health = json.loads(read('/api/health', 65536))
        return (health.get('status') == 'ready' and health.get('model_loads') == 1
                and health.get('labels') == LABELS
                and [(model['key'], model['epoch']) for model in health.get('models', [])] == MODELS)
    except (OSError, HTTPException, ValueError, AttributeError, KeyError, TypeError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('start', 'check'))
    args = parser.parse_args()
    try:
        index, assets = local_release()
    except (OSError, ValueError) as error:
        print(f'{error}。请按 {RUNBOOK} 恢复原发布文件。', file=sys.stderr)
        return 2
    if not port_free():
        if same_ready_service(index):
            print(f'HUMAN SIGNAL 已运行，三模型就绪 · {ORIGIN}/')
            # 10 is internal to start_t72.sh: reuse rather than starting a worker.
            return 10 if args.mode == 'start' else 0
        print('8797 已被占用，但未确认是当前就绪的 HUMAN SIGNAL。'
              '若刚启动本项目请等待；否则用 lsof -nP -iTCP:8797 -sTCP:LISTEN 核对进程。', file=sys.stderr)
        return 2
    if args.mode == 'check':
        print(f'8797 可用；正式首页及 {len(assets)} 项直接引用的本地资源齐全。')
    return 0


if __name__ == '__main__':
    sys.exit(main())

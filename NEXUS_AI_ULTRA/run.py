"""Start NEXUS in one native Windows window; headless mode is explicit."""
import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys

from nexus.desktop import LocalBackend, load_webview, run_desktop


def configure_logging(data):
    handlers = [RotatingFileHandler(data / 'desktop.log', maxBytes=1_000_000, backupCount=2, encoding='utf-8')]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s', handlers=handlers, force=True)


def report_error(message):
    logging.error('%s', message)
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, 'NEXUS AI ULTRA', 0x10)
    elif sys.stderr is not None:
        print(message, file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description='NEXUS native desktop application (Windows WebView2).')
    parser.add_argument('--headless', '--no-browser', dest='headless', action='store_true', help='Run only the local API for development/tests; never open a browser.')
    parser.add_argument('--floating',action='store_true',help='Start the figure-only avatar and auto voice without showing the dashboard.')
    args = parser.parse_args(argv)
    if args.floating and args.headless:parser.error('--floating cannot be used with --headless')
    backend = None
    try:
        data = Path(os.getenv('NEXUS_DATA_DIR', str(Path.home() / '.nexus_ai_ultra')))
        data.mkdir(parents=True, exist_ok=True)
        configure_logging(data)
        # Resolve desktop prerequisites before starting an otherwise invisible API.
        webview = None if args.headless else load_webview()
        backend = LocalBackend(data)
        if args.headless:
            backend.prepare()
            backend.run()
            if backend.failure:
                raise RuntimeError('Backend failed. See desktop.log.') from backend.failure
        else:
            if args.floating:run_desktop(backend,webview,floating=True)
            else:run_desktop(backend, webview)
        return 0
    except Exception as exc:
        report_error(str(exc))
        return 1
    finally:
        if backend:
            try:
                backend.close()
            except Exception as exc:
                report_error(str(exc))
                return 1


if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    raise SystemExit(main())

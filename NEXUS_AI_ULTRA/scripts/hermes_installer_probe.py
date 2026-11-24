"""File-based installer probes; no Python source is passed through native argv.

Windows PowerShell 5 / Legacy argument passing strips embedded quotes from -c
strings. Keeping code in this file covers version, catalog and startup checks.
"""
import argparse
import importlib
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('version')
    catalog = actions.add_parser('schemas')
    catalog.add_argument('--installation', type=Path, required=True)
    catalog.add_argument('--output', type=Path, required=True)
    startup = actions.add_parser('check-app')
    startup.add_argument('--installation', type=Path, required=True)
    startup.add_argument('--data', type=Path, required=True)
    options = parser.parse_args()
    if options.action == 'version':
        print('.'.join(map(str, sys.version_info[:3])))
        return
    sys.path.insert(0, str(options.installation.resolve()))
    if options.action == 'schemas':
        from nexus.tools import CATALOG
        schemas = [dict(type='function', function=dict(name=name, description=description,
            parameters=dict(type='object', properties={key: dict(type=kind) for key, kind in args.items()},
                            required=list(args), additionalProperties=False)))
                   for name, (description, _, args) in CATALOG.items()]
        options.output.write_text(json.dumps(schemas, ensure_ascii=True), encoding='utf-8')
        return
    os.environ['NEXUS_DATA_DIR'] = str(options.data.resolve())
    app = importlib.import_module('nexus.app')
    app.hermes.config()
    app.state()
    print('NEXUS Hermes configuration verified; app startup checked with isolated temporary data')


if __name__ == '__main__':
    main()

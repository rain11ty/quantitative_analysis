#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight quick launcher for the Flask web app."""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from runtime_encoding import configure_utf8_environment

configure_utf8_environment()

from app import create_app



def _env_flag(name: str, default: str = 'false') -> bool:
    return os.getenv(name, default).strip().lower() in {'1', 'true', 'yes', 'on'}


def main() -> None:
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', '5001'))
    config_name = os.getenv('FLASK_ENV', 'default')
    debug = _env_flag('QUICK_START_DEBUG', 'false')

    app = create_app(config_name)

    print('=' * 60)
    print('Stock Analysis Web App')
    print('=' * 60)
    print(f'Config : {config_name}')
    print(f'URL    : http://{host}:{port}')
    print('Tip    : Press Ctrl+C to stop the server.')
    print('=' * 60)

    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == '__main__':
    main()

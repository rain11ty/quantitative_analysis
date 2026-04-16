#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

from runtime_encoding import configure_utf8_environment

configure_utf8_environment()

from app import create_app


app = create_app(os.getenv('FLASK_ENV', 'default'))


if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '5001'))
    debug = os.getenv('DEBUG', 'False').strip().lower() == 'true'
    app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=False,
    )

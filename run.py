#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import socket

from runtime_encoding import configure_utf8_environment

configure_utf8_environment()

from app import create_app


app = create_app(os.getenv('FLASK_ENV', 'default'))


def print_access_urls(host: str, port: int) -> None:
    if host in {'0.0.0.0', '::'}:
        print(f" * Local URL: http://127.0.0.1:{port}")
        print(f" * Local URL: http://localhost:{port}")
        try:
            lan_ip = socket.gethostbyname(socket.gethostname())
            if lan_ip and not lan_ip.startswith('127.'):
                print(f" * LAN URL:   http://{lan_ip}:{port}")
        except OSError:
            pass
        return

    print(f" * Local URL: http://{host}:{port}")


if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '5001'))
    debug = os.getenv('DEBUG', 'False').strip().lower() == 'true'
    print_access_urls(host, port)
    app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=False,
    )

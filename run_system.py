#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Project launcher with UTF-8 safe startup behavior."""

from __future__ import annotations

import subprocess
import sys
import webbrowser
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from runtime_encoding import configure_utf8_environment

configure_utf8_environment()

from app import create_app
from app.extensions import db


class SystemManager:
    def __init__(self):
        self.app = None

    def check_dependencies(self) -> bool:
        print('Checking dependencies...')
        python_version = sys.version_info
        if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
            print('Python 3.8+ is required.')
            return False
        print(f'Python version: {python_version.major}.{python_version.minor}.{python_version.micro}')

        required_packages = [
            'flask', 'sqlalchemy', 'pandas', 'numpy', 'scikit-learn',
            'xgboost', 'lightgbm', 'cvxpy', 'loguru', 'requests',
        ]
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
                print(f'OK  {package}')
            except ImportError:
                missing_packages.append(package)
                print(f'MISS {package}')

        if missing_packages:
            print('Please install missing packages:')
            print('pip install ' + ' '.join(missing_packages))
            return False

        print('All dependencies are available.')
        return True

    def setup_database(self) -> bool:
        print('Initializing database...')
        try:
            self.app = create_app('development')
            with self.app.app_context():
                db.create_all()
            print('Database initialization completed.')
            return True
        except Exception as exc:
            print(f'Database initialization failed: {exc}')
            return False

    def start_web_server(self, host='127.0.0.1', port=5001, debug=False) -> None:
        print(f'Starting web server at http://{host}:{port}')
        print('Press Ctrl+C to stop.')
        try:
            if not self.app:
                self.app = create_app('development')
            if not debug:
                webbrowser.open(f'http://{host}:{port}/')
            self.app.run(host=host, port=port, debug=debug, use_reloader=False)
        except KeyboardInterrupt:
            print('Server stopped.')
        except Exception as exc:
            print(f'Failed to start server: {exc}')

    def run_demo(self) -> None:
        demo_script = project_root / 'examples' / 'complete_system_example.py'
        print('Running demo...')
        if not demo_script.exists():
            print('Demo script not found.')
            return
        try:
            subprocess.run([sys.executable, str(demo_script)], check=False)
        except Exception as exc:
            print(f'Demo failed: {exc}')

    def show_system_info(self) -> None:
        print('=' * 60)
        print('Stock Analysis System Launcher')
        print('=' * 60)
        print('1. Check dependencies')
        print('2. Initialize database')
        print('3. Start web server (debug)')
        print('4. Start web server (production mode)')
        print('5. Run demo')
        print('0. Exit')
        print('=' * 60)


def main() -> None:
    manager = SystemManager()

    if '--menu' not in sys.argv:
        print('No --menu argument provided. Starting web server directly.')
        manager.start_web_server(debug=False)
        return

    while True:
        manager.show_system_info()
        choice = input('Select an option (0-5): ').strip()
        if choice == '0':
            print('Bye.')
            break
        if choice == '1':
            manager.check_dependencies()
        elif choice == '2':
            manager.setup_database()
        elif choice == '3':
            manager.start_web_server(debug=True)
        elif choice == '4':
            manager.start_web_server(debug=False)
        elif choice == '5':
            manager.run_demo()
        else:
            print('Invalid option. Please try again.')


if __name__ == '__main__':
    main()

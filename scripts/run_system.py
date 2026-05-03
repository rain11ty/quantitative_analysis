#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interactive launcher for local development and maintenance."""

from __future__ import annotations

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
            ('flask', 'Flask'),
            ('flask_cors', 'Flask-CORS'),
            ('flask_limiter', 'Flask-Limiter'),
            ('sqlalchemy', 'SQLAlchemy'),
            ('pandas', 'pandas'),
            ('numpy', 'numpy'),
            ('sklearn', 'scikit-learn'),
            ('xgboost', 'xgboost'),
            ('lightgbm', 'lightgbm'),
            ('cvxpy', 'cvxpy'),
            ('loguru', 'loguru'),
            ('requests', 'requests'),
            ('apscheduler', 'APScheduler'),
            ('baostock', 'baostock'),
            ('tushare', 'tushare'),
            ('akshare', 'akshare'),
        ]
        missing_packages = []
        for module_name, package_name in required_packages:
            try:
                __import__(module_name)
                print(f'OK  {package_name}')
            except ImportError:
                missing_packages.append(package_name)
                print(f'MISS {package_name}')

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

    def show_project_layout(self) -> None:
        print('=' * 60)
        print('Current project layout')
        print('=' * 60)
        print('app/                Flask app, templates, services, models')
        print('scripts/diagnostics Manual smoke checks and connectivity checks')
        print('scripts/db_tools    Database inspection utilities')
        print('docs/guides         Current setup and structure docs')
        print('docs/archive        Archived documents for removed modules')
        print('deploy/             Deployment examples')
        print('models/             Demo model assets')
        print('images/             Screenshots used by documentation')
        print('=' * 60)
        print('Recommended start commands:')
        print('  python run.py')
        print('  python quick_start.py')
        print('  python run_system.py --menu')

    def show_system_info(self) -> None:
        print('=' * 60)
        print('Stock Analysis System Launcher')
        print('=' * 60)
        print('1. Check dependencies')
        print('2. Initialize database')
        print('3. Start web server (debug)')
        print('4. Start web server (production mode)')
        print('5. Show project layout')
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
            manager.show_project_layout()
        else:
            print('Invalid option. Please try again.')


if __name__ == '__main__':
    main()

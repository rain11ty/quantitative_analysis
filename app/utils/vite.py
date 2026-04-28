# -*- coding: utf-8 -*-
import json
import os
from pathlib import Path

from flask import current_app, url_for


def _vite_dev_server_url():
    configured = current_app.config.get('VITE_DEV_SERVER_URL') or os.getenv('VITE_DEV_SERVER_URL', '')
    configured = configured.strip()
    return configured.rstrip('/') if configured else ''


def get_vite_asset_context(entry_name='src/main.ts'):
    dev_server_url = _vite_dev_server_url()
    if dev_server_url:
        return {
            'available': True,
            'mode': 'dev',
            'dev_server_url': dev_server_url,
            'entry_url': f'{dev_server_url}/{entry_name}',
            'css_urls': [],
            'missing_reason': None,
        }

    manifest_path = Path(current_app.static_folder) / 'vue' / '.vite' / 'manifest.json'
    if not manifest_path.exists():
        return {
            'available': False,
            'mode': 'build',
            'dev_server_url': '',
            'entry_url': '',
            'css_urls': [],
            'missing_reason': f'Vite manifest not found: {manifest_path}',
        }

    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            'available': False,
            'mode': 'build',
            'dev_server_url': '',
            'entry_url': '',
            'css_urls': [],
            'missing_reason': f'Failed to load Vite manifest: {exc}',
        }

    entry = manifest.get(entry_name)
    if not entry:
        entry = manifest.get('index.html')
    if not entry:
        return {
            'available': False,
            'mode': 'build',
            'dev_server_url': '',
            'entry_url': '',
            'css_urls': [],
            'missing_reason': f'Vite manifest is missing entry "{entry_name}" (and fallback "index.html")',
        }

    css_urls = [
        url_for('static', filename=f"vue/{css_path}")
        for css_path in entry.get('css', [])
    ]

    return {
        'available': True,
        'mode': 'build',
        'dev_server_url': '',
        'entry_url': url_for('static', filename=f"vue/{entry['file']}"),
        'css_urls': css_urls,
        'missing_reason': None,
    }

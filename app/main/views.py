# -*- coding: utf-8 -*-
from flask import g, render_template, redirect, url_for

from app.main import main_bp
from app.utils.vite import get_vite_asset_context


def _build_vue_app_context(route_path=''):
    user = getattr(g, 'current_user', None)
    display_name = None
    if user is not None:
        display_name = getattr(user, 'username', None) or getattr(user, 'email', None)

    return {
        'auth': {
            'isAuthenticated': user is not None,
            'isAdmin': bool(user and getattr(user, 'is_admin', False)),
            'displayName': display_name,
        },
        'initialPath': f'/{route_path}' if route_path else '/',
    }


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/stocks')
def stocks():
    return render_template('stocks.html')


@main_bp.route('/stock/<ts_code>')
def stock_detail(ts_code):
    return render_template('stock_detail.html', ts_code=ts_code)


@main_bp.route('/analysis')
def analysis():
    return redirect(url_for('main.stocks'))


@main_bp.route('/screen')
def screen():
    return render_template('screen.html')


@main_bp.route('/backtest')
def backtest():
    return render_template('backtest.html')


@main_bp.route('/ai-assistant')
def ai_assistant():
    return render_template('ai_assistant.html')


@main_bp.route('/news')
def news():
    return render_template('news.html')


@main_bp.route('/monitor')
def monitor():
    return render_template('realtime_monitor.html')


@main_bp.route('/app', strict_slashes=False)
@main_bp.route('/app/<path:route_path>')
def vue_app(route_path=''):
    return render_template(
        'vue_shell.html',
        vite_assets=get_vite_asset_context('src/main.ts'),
        app_context=_build_vue_app_context(route_path),
    )

# -*- coding: utf-8 -*-
from functools import wraps
from flask import g, request, redirect, url_for, flash


MSG_LOGIN_REQUIRED = '\u8bf7\u5148\u767b\u5f55\u540e\u518d\u8bbf\u95ee\u8be5\u9875\u9762\u3002'
MSG_ADMIN_REQUIRED = '\u4ec5\u7ba1\u7406\u5458\u53ef\u4ee5\u8bbf\u95ee\u8be5\u9875\u9762\u3002'


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not getattr(g, 'current_user', None):
            flash(MSG_LOGIN_REQUIRED, 'warning')
            return redirect(url_for('auth.login', next=request.path))
        return view_func(*args, **kwargs)

    return wrapped_view


def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        current_user = getattr(g, 'current_user', None)
        if not current_user:
            flash(MSG_LOGIN_REQUIRED, 'warning')
            return redirect(url_for('admin.login', next=request.path))
        if not getattr(current_user, 'is_admin', False):
            flash(MSG_ADMIN_REQUIRED, 'danger')
            return redirect(url_for('main.index'))
        return view_func(*args, **kwargs)

    return wrapped_view


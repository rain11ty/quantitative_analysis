# -*- coding: utf-8 -*-
from importlib import import_module

from flask import Blueprint

api_bp = Blueprint('api', __name__)

for _module in (
    '.analysis_api',
    '.ai_assistant_api',
    '.news_api',
    '.realtime_monitor_api',
    '.stock_api',
):
    import_module(_module, __name__)

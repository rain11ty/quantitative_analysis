# -*- coding: utf-8 -*-
from importlib import import_module

from flask import Blueprint

main_bp = Blueprint('main', __name__)

import_module('.views', __name__)

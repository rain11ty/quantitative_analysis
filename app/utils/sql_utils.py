# -*- coding: utf-8 -*-

def escape_like(value: str) -> str:
    """转义 SQL LIKE 通配符，防止 % 和 _ 被误解为通配符。"""
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

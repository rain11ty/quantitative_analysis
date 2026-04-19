# -*- coding: utf-8 -*-
"""
API 统一错误处理工具

功能：
1. api_error_handler 装饰器：自动捕获异常，返回统一格式的 JSON 错误响应
   - 开发环境(DEBUG=True)：返回详细错误信息，方便调试
   - 生产环境：只返回通用错误信息，防止内部信息泄露

2. safe_api_response 函数：手动构建安全响应的快捷方法

使用方式：
    @api_error_handler
    def my_api_endpoint():
        ...  # 不需要 try/except，装饰器自动处理
"""

import functools
from flask import jsonify
from loguru import logger


def api_error_handler(func=None, *, default_message='服务器内部错误，请稍后重试', default_code=500):
    """
    API 异常处理装饰器

    自动捕获被装饰函数中的所有异常，返回统一的 JSON 错误响应。
    开发环境会记录并返回详细的异常堆栈信息；生产环境仅返回通用提示。

    Args:
        func: 被装饰的函数（支持 @api_error_handler 和 @api_error_handler() 两种用法）
        default_message: 生产环境下返回给前端的通用错误提示
        default_code: HTTP 状态码

    用法示例：
        # 方式一：直接使用默认值
        @api_error_handler
        def get_data():
            ...

        # 方式二：自定义错误消息和状态码
        @api_error_handler(default_message='服务暂不可用', default_code=503)
        def call_external():
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                from config import Config
                is_debug = getattr(Config, 'DEBUG', False)

                # 记录完整错误到日志（无论什么环境都记录）
                logger.error(f'[API] {fn.__name__} 执行失败: {exc}', exc_info=True)

                if is_debug:
                    # 开发环境：返回详细信息便于调试
                    message = f'{default_message}: {exc}'
                else:
                    # 生产环境：只返回通用提示，不暴露内部细节
                    message = default_message

                return jsonify({'code': default_code, 'message': message, 'data': None}), default_code
        return wrapper

    if func is not None:
        # 支持 @api_error_handler 无括号用法
        return decorator(func)
    # 支持 @api_error_handler(...) 带参数用法
    return decorator


def safe_api_response(success=True, message='success', data=None, code=200):
    """
    手动构建安全的 API 响应（用于正常响应场景）

    Args:
        success: 是否成功
        message: 提示消息
        data: 数据载荷
        code: 业务状态码（非HTTP状态码）

    Returns:
        tuple: (jsonify_response, http_status_code)
    """
    if not success and code == 200:
        code = 500
    return jsonify({'code': code, 'message': message, 'data': data})

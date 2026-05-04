# -*- coding: utf-8 -*-
"""
LLM service wrapper.

Supports DeepSeek, Qwen (DashScope compatible mode), and OpenAI style chat
completion APIs through one shared interface for the Flask app.
"""

import json
import logging
from typing import Any, Dict, Iterator, List

import requests
from flask import current_app

logger = logging.getLogger(__name__)

OPENAI_COMPATIBLE_PROVIDERS = {
    'deepseek': 'DeepSeek',
    'qwen': '百炼 / Qwen',
    'openai': 'OpenAI',
}

SUPPORTED_PROVIDERS = tuple(OPENAI_COMPATIBLE_PROVIDERS.keys())


class LLMService:
    """统一封装对话与状态检测能力。"""

    def __init__(self, provider: str | None = None, model: str | None = None):
        self.config = current_app.config.get('LLM_CONFIG', {})
        self.default_provider = self._normalize_provider(self.config.get('provider')) or SUPPORTED_PROVIDERS[0]
        self.provider = self._normalize_provider(provider) or self.default_provider
        self.model_override = (model or '').strip() or None

    @staticmethod
    def _normalize_provider(provider: str | None) -> str | None:
        if provider is None:
            return None
        normalized = str(provider).strip().lower()
        return normalized or None

    def _resolve_provider(self) -> str:
        provider = self.provider or self.default_provider
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f'Unsupported LLM provider: {provider}')
        return provider

    def _get_provider_config(self, provider: str | None = None) -> Dict[str, Any]:
        return self.config.get(provider or self._resolve_provider(), {})

    def _get_provider_label(self, provider: str | None = None) -> str:
        provider_key = provider or self._resolve_provider()
        return OPENAI_COMPATIBLE_PROVIDERS.get(provider_key, provider_key.title())

    def _get_compatible_provider(self) -> tuple[str, str, Dict[str, Any]]:
        provider = self._resolve_provider()
        if provider not in OPENAI_COMPATIBLE_PROVIDERS:
            raise ValueError(f'Provider {provider} is not OpenAI compatible')
        return provider, self._get_provider_label(provider), self._get_provider_config(provider)

    def _get_available_models(self, provider: str) -> List[str]:
        provider_config = self._get_provider_config(provider)
        configured_model = (provider_config.get('model') or '').strip()
        values: List[str] = []

        for item in provider_config.get('available_models') or []:
            model_name = str(item).strip()
            if model_name and model_name not in values:
                values.append(model_name)

        if configured_model and configured_model not in values:
            values.insert(0, configured_model)

        return values

    def get_effective_model(self, provider: str | None = None) -> str:
        provider_key = provider or self._resolve_provider()
        provider_config = self._get_provider_config(provider_key)
        model = self.model_override or provider_config.get('model')
        model = (model or '').strip()
        if not model:
            raise ValueError(f'No model configured for provider: {provider_key}')
        return model

    def get_runtime_config(self) -> Dict[str, Any]:
        provider = self._resolve_provider()
        provider_config = self._get_provider_config(provider)
        return {
            'provider': provider,
            'provider_label': self._get_provider_label(provider),
            'model': self.get_effective_model(provider),
            'app_id_configured': bool(provider_config.get('app_id')) if provider == 'qwen' else False,
        }

    def _provider_is_selectable(self, provider: str) -> bool:
        provider_config = self._get_provider_config(provider)
        return bool((provider_config.get('api_key') or '').strip())

    def _build_frontend_provider_options(self, include_unconfigured: bool = False) -> List[Dict[str, Any]]:
        options: List[Dict[str, Any]] = []

        for provider in SUPPORTED_PROVIDERS:
            configured = self._provider_is_selectable(provider)
            if not include_unconfigured and not configured:
                continue

            models = self._get_available_models(provider)
            if not models:
                continue

            provider_config = self._get_provider_config(provider)
            default_model = (provider_config.get('model') or models[0]).strip()
            options.append({
                'value': provider,
                'label': self._get_provider_label(provider),
                'configured': configured,
                'default_model': default_model,
                'models': [{'value': model, 'label': model} for model in models],
            })

        return options

    def get_frontend_options(self) -> Dict[str, Any]:
        all_providers = self._build_frontend_provider_options(include_unconfigured=True)
        providers = [item for item in all_providers if item['configured']]

        default_provider = ''
        default_model = ''

        if providers:
            default_provider = self.default_provider if any(
                item['value'] == self.default_provider for item in providers
            ) else providers[0]['value']

            for item in providers:
                if item['value'] == default_provider:
                    default_model = item['default_model']
                    break

        return {
            'default_provider': default_provider,
            'default_model': default_model,
            'providers': providers,
            'all_providers': all_providers,
        }

    def _openai_headers(self, provider: str, provider_config: Dict[str, Any]) -> Dict[str, str]:
        headers = {
            'Authorization': f"Bearer {provider_config.get('api_key')}",
            'Content-Type': 'application/json',
        }
        app_id = str(provider_config.get('app_id') or '').strip()
        if provider == 'qwen' and app_id:
            headers['X-DashScope-App-Id'] = app_id
        return headers

    @staticmethod
    def _has_multimodal_content(messages: List[Dict[str, Any]]) -> bool:
        for msg in messages:
            content = msg.get('content')
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'image_url':
                        return True
        return False

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """非流式对话。"""
        try:
            request_kwargs = dict(kwargs)
            request_kwargs.pop('stream', None)
            provider = self._resolve_provider()
            provider_config = self._get_provider_config(provider)
            if provider == 'qwen' and provider_config.get('app_id') and not self._has_multimodal_content(messages):
                return self._bailian_app_chat(messages, **request_kwargs)
            return self._openai_chat(messages, **request_kwargs)
        except Exception as exc:
            logger.error(f'大模型调用失败: {exc}')
            return {
                'success': False,
                'error': str(exc),
                'content': None,
            }

    def stream_chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> Iterator[str]:
        """流式对话。"""
        request_kwargs = dict(kwargs)
        request_kwargs.pop('stream', None)

        try:
            provider = self._resolve_provider()
            provider_config = self._get_provider_config(provider)
            if provider == 'qwen' and provider_config.get('app_id') and not self._has_multimodal_content(messages):
                yield from self._bailian_app_stream(messages, **request_kwargs)
            else:
                yield from self._openai_stream_chat(messages, **request_kwargs)
        except Exception as exc:
            logger.error(f'大模型流式调用失败: {exc}')
            raise

    # ── 百炼智能应用体 API ──

    def _bailian_app_headers(self, provider_config: Dict[str, Any]) -> Dict[str, str]:
        return {
            'Authorization': f"Bearer {provider_config.get('api_key')}",
            'Content-Type': 'application/json',
            'X-DashScope-App-Id': str(provider_config.get('app_id') or '').strip(),
        }

    def _bailian_app_url(self, provider_config: Dict[str, Any]) -> str:
        base_url = (provider_config.get('base_url') or 'https://dashscope.aliyuncs.com').rstrip('/')
        # Bailian App API uses a different path than compatible-mode; strip the compatible-mode suffix
        # e.g. "https://dashscope.aliyuncs.com/compatible-mode/v1" -> "https://dashscope.aliyuncs.com"
        if '/compatible-mode' in base_url:
            base_url = base_url.split('/compatible-mode')[0]
        # Also strip trailing /v1 if present
        if base_url.endswith('/v1'):
            base_url = base_url[:-3]
        base_url = base_url.rstrip('/')
        return f'{base_url}/api/v1/apps/{provider_config["app_id"]}/completion'

    @staticmethod
    def _extract_bailian_content(result: Dict[str, Any]) -> str:
        """从百炼 API 响应中提取文本内容，兼容多种响应格式。"""
        # 格式一：output.choices[].message.content（标准 message 格式）
        choices = result.get('output', {}).get('choices', [])
        if choices:
            message = choices[0].get('message') or {}
            content = message.get('content')
            if content:
                return content
            # 如果 content 为空但存在 tool_calls，说明工具正在执行
            # 非流式模式下百炼 App API 会自动完成工具调用并返回最终结果
            # 如果仍然为空，记录日志供排查
            tool_calls = message.get('tool_calls')
            if tool_calls:
                logger.info('百炼 App API: 非流式响应包含工具调用，tool_calls=%s', tool_calls)
        # 格式二：output.text（text 格式 / 部分插件响应）
        text = result.get('output', {}).get('text')
        if text:
            return text
        return ''

    def _bailian_app_chat(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        provider_config = self._get_provider_config('qwen')
        headers = self._bailian_app_headers(provider_config)
        data = {
            'input': {'messages': messages},
            'parameters': {'result_format': 'message'},
        }
        try:
            url = self._bailian_app_url(provider_config)
            # 非流式请求使用更长超时，因为工具调用（如 MCP 股票查询）可能耗时较长
            timeout = max(provider_config.get('timeout', 120), 180)
            response = requests.post(url, headers=headers, json=data, timeout=timeout)
            if response.status_code != 200:
                return {'success': False, 'error': f'百炼 API 错误: {response.status_code} - {response.text}', 'content': None}
            result = response.json()
            # 检查百炼 API 错误响应（无 output 字段，顶层含 code/message）
            if 'code' in result and 'output' not in result:
                error_msg = result.get('message') or result.get('code', '未知错误')
                return {'success': False, 'error': f'百炼 API 错误: {error_msg}', 'content': None}
            content = self._extract_bailian_content(result)
            if not content:
                logger.warning('百炼 App API 返回空内容，原始响应: %s', result)
                # 检查是否包含工具调用信息
                choices = result.get('output', {}).get('choices', [])
                if choices:
                    message = choices[0].get('message') or {}
                    if message.get('tool_calls'):
                        return {
                            'success': False,
                            'error': '百炼智能体执行了工具调用但未返回最终回复，请检查百炼控制台中 MCP 工具配置。',
                            'content': None,
                        }
                return {'success': False, 'error': '百炼 API 返回空内容，请检查百炼智能应用体配置（插件/工具是否正常）', 'content': None}
            return {
                'success': True,
                'content': content,
                'model': provider_config.get('model', 'qwen3.6-plus'),
                'usage': result.get('usage', {}),
                'provider': 'qwen',
            }
        except requests.exceptions.Timeout:
            return {'success': False, 'error': '百炼请求超时，MCP 工具执行可能耗时较长，请稍后重试。', 'content': None}
        except Exception as exc:
            return {'success': False, 'error': f'百炼调用异常: {exc}', 'content': None}

    def _bailian_app_stream(self, messages: List[Dict[str, Any]], **kwargs) -> Iterator[str]:
        provider_config = self._get_provider_config('qwen')
        headers = self._bailian_app_headers(provider_config)
        data = {
            'input': {'messages': messages},
            'parameters': {'result_format': 'message'},
            'stream': True,
        }
        url = self._bailian_app_url(provider_config)
        has_content = False
        tool_call_detected = False
        event_count = 0
        last_event_type = ''
        try:
            # 流式请求使用更长超时：工具调用（如 MCP 股票查询）期间服务端可能长时间无数据输出
            stream_timeout = max(provider_config.get('timeout', 120), 180)
            with requests.post(url, headers=headers, json=data,
                               timeout=stream_timeout, stream=True) as response:
                if response.status_code != 200:
                    raise RuntimeError(f'百炼 API 错误: {response.status_code} - {response.text}')
                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    line = raw_line.strip()
                    # 处理 SSE event: 标记行（如 event:result、event:ping 等）
                    if line.startswith('event:'):
                        last_event_type = line[6:].strip()
                        continue
                    if not line.startswith('data:'):
                        continue
                    payload = line[5:].strip()
                    if payload == '[DONE]':
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        logger.debug('百炼 SSE: 无法解析的 JSON: %s', payload[:200])
                        continue

                    event_count += 1

                    # 检查百炼 API 在 SSE 流中的错误响应
                    if 'code' in chunk and 'output' not in chunk:
                        error_msg = chunk.get('message') or chunk.get('code', '未知错误')
                        raise RuntimeError(f'百炼 API 错误: {error_msg}')

                    output = chunk.get('output', {})
                    yielded = False

                    # 从 output.choices 提取内容
                    choices = output.get('choices', [])
                    if choices:
                        delta = choices[0].get('message') or {}
                        # 处理 content：可能是 string、null 或缺失
                        content = delta.get('content') or ''
                        # 检测工具调用事件
                        tool_calls = delta.get('tool_calls')
                        if tool_calls:
                            tool_call_detected = True
                            tool_names = []
                            for tc in (tool_calls if isinstance(tool_calls, list) else []):
                                fn = tc.get('function') or {}
                                tool_names.append(fn.get('name') or 'unknown')
                            logger.info('百炼 App API: 检测到工具调用 [%s]，等待执行完成...', ', '.join(tool_names))
                            # 工具调用事件不包含文本内容，跳过但不视为错误
                            continue
                        if content:
                            has_content = True
                            yield content
                            yielded = True
                        else:
                            # content 为空且无工具调用，检查 finish_reason
                            finish_reason = choices[0].get('finish_reason', '')
                            if finish_reason:
                                logger.debug('百炼 SSE: finish_reason=%s, content 为空', finish_reason)

                    # 兼容 output.text 格式（部分插件/工具/MCP 响应使用此格式）
                    # 必须在 choices 之后检查，因为工具调用完成后可能返回 text 格式
                    if not yielded:
                        text = output.get('text', '')
                        if text:
                            has_content = True
                            yield text
                            continue

                    # 某些中间事件（如 ping、keepalive）可能不含 output，
                    # 仅含 request_id / usage 等元数据，正常跳过
                    if event_count <= 3 or event_count % 50 == 0:
                        logger.debug('百炼 SSE 事件 #%d (event=%s): %s', event_count, last_event_type, str(chunk)[:300])

            if not has_content:
                if tool_call_detected:
                    raise RuntimeError(
                        '百炼智能体执行了工具调用，但未返回最终回复。'
                        '请检查百炼控制台中 MCP 工具配置是否正常，'
                        '或尝试一个不需要工具调用的问题来验证基本功能。'
                    )
                raise RuntimeError('百炼 API 未返回任何内容，请检查百炼智能应用体配置（插件/工具是否正常工作）')
        except requests.exceptions.ConnectionError:
            raise RuntimeError('百炼服务无法连接')
        except requests.exceptions.Timeout:
            if tool_call_detected:
                raise RuntimeError(
                    '百炼智能体工具调用执行超时。MCP 工具（如股票数据查询）可能执行时间较长，'
                    '请稍后重试或尝试更简单的问题。'
                )
            raise RuntimeError('百炼请求超时')
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f'百炼调用异常: {exc}')

    def _openai_chat(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        provider, provider_label, provider_config = self._get_compatible_provider()
        api_key = provider_config.get('api_key')
        if not api_key:
            return {
                'success': False,
                'error': f'{provider_label} API 密钥未配置',
                'content': None,
            }

        base_url = (provider_config.get('base_url') or 'https://api.openai.com/v1').rstrip('/')
        model = self.get_effective_model(provider)
        headers = self._openai_headers(provider, provider_config)
        data = {
            'model': model,
            'messages': messages,
            'temperature': kwargs.get('temperature', provider_config.get('temperature', 0.1)),
            'max_tokens': kwargs.get('max_tokens', provider_config.get('max_tokens', 2048)),
        }

        try:
            response = requests.post(
                f'{base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=provider_config.get('timeout', 60),
            )

            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f'{provider_label} API 错误: {response.status_code} - {response.text}',
                    'content': None,
                }

            result = response.json()
            message = ((result.get('choices') or [{}])[0].get('message') or {}).get('content', '')
            return {
                'success': True,
                'content': message,
                'model': model,
                'usage': result.get('usage', {}),
                'provider': provider,
            }
        except Exception as exc:
            return {
                'success': False,
                'error': f'{provider_label} 调用异常: {exc}',
                'content': None,
            }

    def _openai_stream_chat(self, messages: List[Dict[str, str]], **kwargs) -> Iterator[str]:
        provider, provider_label, provider_config = self._get_compatible_provider()
        api_key = provider_config.get('api_key')
        if not api_key:
            raise RuntimeError(f'{provider_label} API 密钥未配置')

        base_url = (provider_config.get('base_url') or 'https://api.openai.com/v1').rstrip('/')
        model = self.get_effective_model(provider)
        headers = self._openai_headers(provider, provider_config)
        data = {
            'model': model,
            'messages': messages,
            'temperature': kwargs.get('temperature', provider_config.get('temperature', 0.1)),
            'max_tokens': kwargs.get('max_tokens', provider_config.get('max_tokens', 2048)),
            'stream': True,
        }

        try:
            with requests.post(
                f'{base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=provider_config.get('timeout', 60),
                stream=True,
            ) as response:
                if response.status_code != 200:
                    raise RuntimeError(f'{provider_label} API 错误: {response.status_code} - {response.text}')

                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue

                    line = raw_line.strip()
                    if not line.startswith('data:'):
                        continue

                    payload = line[5:].strip()
                    if payload == '[DONE]':
                        break

                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    choice = (chunk.get('choices') or [{}])[0]
                    delta = choice.get('delta') or {}
                    content = delta.get('content')
                    if content is None:
                        content = (choice.get('message') or {}).get('content', '')

                    if content:
                        yield content
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(f'{provider_label} 服务无法连接') from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(f'{provider_label} 请求超时') from exc
        except Exception as exc:
            raise RuntimeError(f'{provider_label} 调用异常: {exc}') from exc

    def check_service_status(self) -> Dict[str, Any]:
        provider = self._resolve_provider()
        if provider in OPENAI_COMPATIBLE_PROVIDERS:
            return self._check_openai_status()

        return {
            'status': 'error',
            'message': f'不支持的提供商: {provider}',
        }

    def _check_openai_status(self) -> Dict[str, Any]:
        provider, provider_label, provider_config = self._get_compatible_provider()
        api_key = provider_config.get('api_key')
        target_model = self.get_effective_model(provider)

        if not api_key:
            return {
                'status': 'error',
                'message': f'{provider_label} API 密钥未配置',
                'target_model': target_model,
                'provider': provider,
                'app_id_configured': bool(provider_config.get('app_id')) if provider == 'qwen' else False,
            }

        base_url = (provider_config.get('base_url') or 'https://api.openai.com/v1').rstrip('/')
        headers = self._openai_headers(provider, provider_config)

        try:
            response = requests.get(
                f'{base_url}/models',
                headers=headers,
                timeout=provider_config.get('timeout', 60),
            )

            if response.status_code == 200:
                payload = response.json()
                models = [item.get('id') for item in payload.get('data', []) if item.get('id')]
                model_available = target_model in models if models else True
                return {
                    'status': 'online' if model_available else 'model_not_found',
                    'message': (
                        f'{provider_label} 已连接'
                        if model_available
                        else f'{provider_label} 未找到目标模型'
                    ),
                    'models': models,
                    'target_model': target_model,
                    'provider': provider,
                    'provider_label': provider_label,
                    'app_id_configured': bool(provider_config.get('app_id')) if provider == 'qwen' else False,
                }

            if provider == 'qwen' and response.status_code in (404, 405):
                return {
                    'status': 'configured',
                    'message': '百炼兼容模式已配置完成，模型列表接口未开放，将在首次对话时校验可用性。',
                    'target_model': target_model,
                    'provider': provider,
                    'provider_label': provider_label,
                    'app_id_configured': bool(provider_config.get('app_id')),
                }

            return {
                'status': 'error',
                'message': f'{provider_label} 服务响应异常: {response.status_code}',
                'target_model': target_model,
                'provider': provider,
                'provider_label': provider_label,
                'app_id_configured': bool(provider_config.get('app_id')) if provider == 'qwen' else False,
            }
        except requests.exceptions.ConnectionError:
            return {
                'status': 'offline',
                'message': f'{provider_label} 服务无法连接',
                'target_model': target_model,
                'provider': provider,
                'provider_label': provider_label,
                'app_id_configured': bool(provider_config.get('app_id')) if provider == 'qwen' else False,
            }
        except Exception as exc:
            return {
                'status': 'error',
                'message': f'检测 {provider_label} 状态失败: {exc}',
                'target_model': target_model,
                'provider': provider,
                'provider_label': provider_label,
                'app_id_configured': bool(provider_config.get('app_id')) if provider == 'qwen' else False,
            }

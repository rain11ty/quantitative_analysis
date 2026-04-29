# -*- coding: utf-8 -*-
"""
大模型服务
支持 DeepSeek、Qwen（阿里百炼）和 OpenAI 等 API 提供商。
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

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """非流式对话。"""
        try:
            request_kwargs = dict(kwargs)
            request_kwargs.pop('stream', None)
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
            yield from self._openai_stream_chat(messages, **request_kwargs)
        except Exception as exc:
            logger.error(f'大模型流式调用失败: {exc}')
            raise

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

    def enhance_sql_generation(self, user_query: str, context: Dict[str, Any]) -> str | None:
        """使用大模型增强 SQL 生成。"""
        try:
            prompt = self._build_sql_prompt(user_query, context)
            messages = [
                {
                    'role': 'system',
                    'content': '你是一个专业的 SQL 生成助手，专门为股票分析系统生成准确的 SQL 查询语句。',
                },
                {
                    'role': 'user',
                    'content': prompt,
                },
            ]

            result = self.chat_completion(messages, temperature=0.1)
            if result['success']:
                return self._extract_sql_from_response(result['content'])

            logger.error(f"大模型 SQL 生成失败: {result['error']}")
            return None
        except Exception as exc:
            logger.error(f'大模型 SQL 增强失败: {exc}')
            return None

    def _build_sql_prompt(self, user_query: str, context: Dict[str, Any]) -> str:
        tables_info = context.get('tables_info', {})
        intent = context.get('intent', {})
        entities = context.get('entities', {})

        return f"""
请根据用户的自然语言查询生成对应的 SQL 语句。

用户查询: {user_query}

识别的意图: {intent.get('name', 'unknown')}
提取的实体: {json.dumps(entities, ensure_ascii=False)}

可用的数据表结构:
{self._format_tables_info(tables_info)}

要求:
1. 生成标准的 MySQL SQL 语句。
2. 只返回 SQL 语句，不要附加解释。
3. 确保语法正确。
4. 使用适当的 WHERE、ORDER BY 和 LIMIT。

请生成 SQL:
"""

    def _format_tables_info(self, tables_info: Dict[str, Any]) -> str:
        if not tables_info:
            return """
stock_business表（股票基础数据）:
- ts_code: 股票代码
- stock_name: 股票名称
- daily_close: 收盘价
- factor_pct_change: 涨跌幅
- vol: 成交量
- amount: 成交额
- pe_ttm: 市盈率
- pb: 市净率

stock_factor表（技术指标）:
- ts_code: 股票代码
- macd: MACD指标
- macd_dif: MACD DIF线
- macd_dea: MACD DEA线
- rsi_6: RSI指标

stock_moneyflow表（资金流向）:
- ts_code: 股票代码
- net_mf_amount: 净流入金额
- net_mf_vol: 净流入量
"""

        formatted = ''
        for table_name, table_info in tables_info.items():
            formatted += f'\n{table_name}表:\n'
            for field_name, field_info in table_info.items():
                formatted += f"- {field_name}: {field_info.get('description', '')}\n"
        return formatted

    def _extract_sql_from_response(self, response: str) -> str:
        response = response.strip()
        if response.startswith('```sql'):
            response = response[6:]
        elif response.startswith('```'):
            response = response[3:]

        if response.endswith('```'):
            response = response[:-3]

        sql = response.strip()
        if not sql.endswith(';'):
            sql += ';'
        return sql

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
                    'message': f'{provider_label} 已连接' if model_available else f'{provider_label} 未找到目标模型',
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


_llm_service = None


def get_llm_service() -> LLMService:
    """获取单例服务实例。"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

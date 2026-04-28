# -*- coding: utf-8 -*-
"""
大模型服务
支持本地ollama和OpenAI等多种大模型提供商
"""

import json
import requests
import logging
from typing import Any, Dict, Iterator, List
from flask import current_app

logger = logging.getLogger(__name__)

OPENAI_COMPATIBLE_PROVIDERS = {
    'openai': 'OpenAI',
    'deepseek': 'DeepSeek',
    'qwen': 'Qwen',
}

OLLAMA_PROVIDER = 'ollama'
SUPPORTED_PROVIDERS = (OLLAMA_PROVIDER, *OPENAI_COMPATIBLE_PROVIDERS.keys())
PROVIDER_LABELS = {
    OLLAMA_PROVIDER: 'Ollama',
    **OPENAI_COMPATIBLE_PROVIDERS,
}


class LLMService:
    """大模型服务"""
    
    def __init__(self, provider: str | None = None, model: str | None = None):
        self.config = current_app.config.get('LLM_CONFIG', {})
        self.default_provider = self._normalize_provider(self.config.get('provider')) or OLLAMA_PROVIDER
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
        provider_key = provider or self._resolve_provider()
        return self.config.get(provider_key, {})

    def _get_provider_label(self, provider: str | None = None) -> str:
        provider_key = provider or self._resolve_provider()
        return PROVIDER_LABELS.get(provider_key, provider_key.title())

    def _get_compatible_provider(self):
        provider = self._resolve_provider()
        if provider not in OPENAI_COMPATIBLE_PROVIDERS:
            raise ValueError(f'Provider {provider} is not OpenAI compatible')
        provider_config = self._get_provider_config(provider)
        provider_label = self._get_provider_label(provider)
        return provider, provider_label, provider_config

    def get_effective_model(self, provider: str | None = None) -> str:
        provider_key = provider or self._resolve_provider()
        provider_config = self._get_provider_config(provider_key)
        model = self.model_override or provider_config.get('model')
        if not model:
            raise ValueError(f'No model configured for provider: {provider_key}')
        return model

    def get_runtime_config(self) -> Dict[str, str]:
        provider = self._resolve_provider()
        return {
            'provider': provider,
            'provider_label': self._get_provider_label(provider),
            'model': self.get_effective_model(provider),
        }

    def _provider_is_selectable(self, provider: str) -> bool:
        if provider == OLLAMA_PROVIDER:
            return True
        provider_config = self._get_provider_config(provider)
        return bool(provider_config.get('api_key'))

    def get_frontend_options(self) -> Dict[str, Any]:
        providers = []

        for provider in SUPPORTED_PROVIDERS:
            provider_config = self._get_provider_config(provider)
            if not self._provider_is_selectable(provider) and provider != self.default_provider:
                continue

            configured_model = provider_config.get('model')
            available_models = list(provider_config.get('available_models') or [])
            if configured_model and configured_model not in available_models:
                available_models.insert(0, configured_model)

            available_models = [model for model in available_models if model]
            if not available_models:
                continue

            providers.append({
                'value': provider,
                'label': self._get_provider_label(provider),
                'default_model': configured_model or available_models[0],
                'models': [
                    {'value': model, 'label': model}
                    for model in available_models
                ],
            })

        default_provider = self.default_provider
        if providers and default_provider not in {item['value'] for item in providers}:
            default_provider = providers[0]['value']

        default_model = ''
        for provider in providers:
            if provider['value'] == default_provider:
                default_model = provider['default_model']
                break

        return {
            'default_provider': default_provider,
            'default_model': default_model,
            'providers': providers,
        }

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """聊天完成接口"""
        try:
            request_kwargs = dict(kwargs)
            request_kwargs.pop('stream', None)

            provider = self._resolve_provider()
            if provider == OLLAMA_PROVIDER:
                return self._ollama_chat(messages, **request_kwargs)
            if provider in OPENAI_COMPATIBLE_PROVIDERS:
                return self._openai_chat(messages, **request_kwargs)

            raise ValueError(f"不支持的大模型提供商: {provider}")
        except Exception as e:
            logger.error(f"大模型调用失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'content': None
            }

    def stream_chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> Iterator[str]:
        """流式聊天完成接口"""
        request_kwargs = dict(kwargs)
        request_kwargs.pop('stream', None)

        try:
            provider = self._resolve_provider()
            if provider == OLLAMA_PROVIDER:
                yield from self._ollama_stream_chat(messages, **request_kwargs)
                return
            if provider in OPENAI_COMPATIBLE_PROVIDERS:
                yield from self._openai_stream_chat(messages, **request_kwargs)
                return

            raise ValueError(f"不支持的大模型提供商: {provider}")
        except Exception as e:
            logger.error(f"大模型流式调用失败: {e}")
            raise

    def _ollama_chat(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """Ollama聊天接口"""
        ollama_config = self.config.get('ollama', {})
        base_url = ollama_config.get('base_url', 'http://localhost:11434')
        model = self.get_effective_model(OLLAMA_PROVIDER)
        
        # 构建请求数据
        data = {
            'model': model,
            'messages': messages,
            'stream': False,
            'options': {
                'temperature': kwargs.get('temperature', ollama_config.get('temperature', 0.1)),
                'num_predict': kwargs.get('max_tokens', ollama_config.get('max_tokens', 2048))
            }
        }
        
        try:
            response = requests.post(
                f"{base_url}/api/chat",
                json=data,
                timeout=ollama_config.get('timeout', 60)
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'content': result.get('message', {}).get('content', ''),
                    'model': model,
                    'usage': result.get('usage', {})
                }
            else:
                return {
                    'success': False,
                    'error': f"Ollama API错误: {response.status_code} - {response.text}",
                    'content': None
                }
        
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': "无法连接到Ollama服务，请确保Ollama正在运行",
                'content': None
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': "Ollama请求超时",
                'content': None
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Ollama调用异常: {str(e)}",
                'content': None
            }

    def _ollama_stream_chat(self, messages: List[Dict[str, str]], **kwargs) -> Iterator[str]:
        """Ollama 流式聊天接口"""
        ollama_config = self.config.get('ollama', {})
        base_url = ollama_config.get('base_url', 'http://localhost:11434')
        model = self.get_effective_model(OLLAMA_PROVIDER)

        data = {
            'model': model,
            'messages': messages,
            'stream': True,
            'options': {
                'temperature': kwargs.get('temperature', ollama_config.get('temperature', 0.1)),
                'num_predict': kwargs.get('max_tokens', ollama_config.get('max_tokens', 2048))
            }
        }

        try:
            with requests.post(
                f"{base_url}/api/chat",
                json=data,
                timeout=ollama_config.get('timeout', 60),
                stream=True
            ) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"Ollama API错误: {response.status_code} - {response.text}")

                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    content = payload.get('message', {}).get('content', '')
                    if content:
                        yield content
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError("无法连接到Ollama服务，请确保Ollama正在运行") from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError("Ollama请求超时") from exc
        except Exception as exc:
            raise RuntimeError(f"Ollama调用异常: {str(exc)}") from exc
    
    def _openai_chat(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """OpenAI兼容聊天接口（支持 DeepSeek / Qwen）"""
        provider, provider_label, provider_config = self._get_compatible_provider()
        api_key = provider_config.get('api_key')

        if not api_key:
            return {
                'success': False,
                'error': f"{provider_label} API密钥未配置",
                'content': None
            }

        base_url = (provider_config.get('base_url') or 'https://api.openai.com/v1').rstrip('/')
        model = self.get_effective_model(provider)

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        data = {
            'model': model,
            'messages': messages,
            'temperature': kwargs.get('temperature', provider_config.get('temperature', 0.1)),
            'max_tokens': kwargs.get('max_tokens', provider_config.get('max_tokens', 2048))
        }

        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=provider_config.get('timeout', 60)
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'content': result['choices'][0]['message']['content'],
                    'model': model,
                    'usage': result.get('usage', {}),
                    'provider': provider
                }
            else:
                return {
                    'success': False,
                    'error': f"{provider_label} API错误: {response.status_code} - {response.text}",
                    'content': None
                }

        except Exception as e:
            return {
                'success': False,
                'error': f"{provider_label}调用异常: {str(e)}",
                'content': None
            }

    def _openai_stream_chat(self, messages: List[Dict[str, str]], **kwargs) -> Iterator[str]:
        """OpenAI 兼容流式聊天接口（支持 DeepSeek / Qwen）"""
        provider, provider_label, provider_config = self._get_compatible_provider()
        api_key = provider_config.get('api_key')

        if not api_key:
            raise RuntimeError(f"{provider_label} API密钥未配置")

        base_url = (provider_config.get('base_url') or 'https://api.openai.com/v1').rstrip('/')
        model = self.get_effective_model(provider)
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        data = {
            'model': model,
            'messages': messages,
            'temperature': kwargs.get('temperature', provider_config.get('temperature', 0.1)),
            'max_tokens': kwargs.get('max_tokens', provider_config.get('max_tokens', 2048)),
            'stream': True
        }

        try:
            with requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=provider_config.get('timeout', 60),
                stream=True
            ) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"{provider_label} API错误: {response.status_code} - {response.text}")

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
            raise RuntimeError(f"{provider_label}服务无法连接") from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(f"{provider_label}请求超时") from exc
        except Exception as exc:
            raise RuntimeError(f"{provider_label}调用异常: {str(exc)}") from exc

    
    def enhance_sql_generation(self, user_query: str, context: Dict[str, Any]) -> str:
        """使用大模型增强SQL生成"""
        try:
            # 构建提示词
            prompt = self._build_sql_prompt(user_query, context)
            
            messages = [
                {
                    "role": "system",
                    "content": "你是一个专业的SQL生成助手，专门为股票分析系统生成准确的SQL查询语句。"
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ]
            
            result = self.chat_completion(messages, temperature=0.1)
            
            if result['success']:
                return self._extract_sql_from_response(result['content'])
            else:
                logger.error(f"大模型SQL生成失败: {result['error']}")
                return None
        
        except Exception as e:
            logger.error(f"大模型SQL增强失败: {e}")
            return None
    
    def _build_sql_prompt(self, user_query: str, context: Dict[str, Any]) -> str:
        """构建SQL生成提示词"""
        # 获取表结构信息
        tables_info = context.get('tables_info', {})
        intent = context.get('intent', {})
        entities = context.get('entities', {})
        
        prompt = f"""
请根据用户的自然语言查询生成对应的SQL语句。

用户查询: {user_query}

识别的意图: {intent.get('name', 'unknown')}
提取的实体: {json.dumps(entities, ensure_ascii=False)}

可用的数据表结构:
{self._format_tables_info(tables_info)}

要求:
1. 生成标准的MySQL SQL语句
2. 只返回SQL语句，不要其他解释
3. 确保SQL语法正确
4. 使用适当的WHERE条件和ORDER BY子句
5. 添加合理的LIMIT限制

请生成SQL语句:
"""
        return prompt
    
    def _format_tables_info(self, tables_info: Dict[str, Any]) -> str:
        """格式化表结构信息"""
        if not tables_info:
            return """
stock_business表 (股票基础数据):
- ts_code: 股票代码
- stock_name: 股票名称  
- daily_close: 收盘价
- factor_pct_change: 涨跌幅
- vol: 成交量
- amount: 成交额
- pe_ttm: 市盈率
- pb: 市净率

stock_factor表 (技术指标):
- ts_code: 股票代码
- macd: MACD指标
- macd_dif: MACD DIF线
- macd_dea: MACD DEA线
- rsi_6: RSI指标

stock_moneyflow表 (资金流向):
- ts_code: 股票代码
- net_mf_amount: 净流入金额
- net_mf_vol: 净流入量
"""
        
        formatted = ""
        for table_name, table_info in tables_info.items():
            formatted += f"\n{table_name}表:\n"
            for field_name, field_info in table_info.items():
                formatted += f"- {field_name}: {field_info.get('description', '')}\n"
        
        return formatted
    
    def _extract_sql_from_response(self, response: str) -> str:
        """从大模型响应中提取SQL语句"""
        # 移除markdown代码块标记
        response = response.strip()
        if response.startswith('```sql'):
            response = response[6:]
        elif response.startswith('```'):
            response = response[3:]
        
        if response.endswith('```'):
            response = response[:-3]
        
        # 清理和格式化SQL
        sql = response.strip()
        
        # 确保SQL以分号结尾
        if not sql.endswith(';'):
            sql += ';'
        
        return sql
    
    def check_service_status(self) -> Dict[str, Any]:
        """检查大模型服务状态"""
        provider = self._resolve_provider()
        if provider == OLLAMA_PROVIDER:
            return self._check_ollama_status()
        elif provider in OPENAI_COMPATIBLE_PROVIDERS:
            return self._check_openai_status()
        else:
            return {
                'status': 'error',
                'message': f'不支持的提供商: {provider}'
            }

    
    def _check_ollama_status(self) -> Dict[str, Any]:
        """检查Ollama服务状态"""
        try:
            ollama_config = self.config.get('ollama', {})
            base_url = ollama_config.get('base_url', 'http://localhost:11434')
            
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            
            if response.status_code == 200:
                models = response.json().get('models', [])
                target_model = self.get_effective_model(OLLAMA_PROVIDER)
                
                model_available = any(model.get('name') == target_model for model in models)
                
                return {
                    'status': 'online' if model_available else 'model_not_found',
                    'message': f'Ollama服务正常，模型{"可用" if model_available else "不可用"}',
                    'models': [model.get('name') for model in models],
                    'target_model': target_model
                }
            else:
                return {
                    'status': 'error',
                    'message': f'Ollama服务响应异常: {response.status_code}'
                }
        
        except requests.exceptions.ConnectionError:
            return {
                'status': 'offline',
                'message': 'Ollama服务未启动或无法连接'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'检查Ollama状态失败: {str(e)}'
            }
    
    def _check_openai_status(self) -> Dict[str, Any]:
        """检查 OpenAI 兼容服务状态（支持 DeepSeek / Qwen）"""
        provider, provider_label, provider_config = self._get_compatible_provider()
        api_key = provider_config.get('api_key')

        if not api_key:
            return {
                'status': 'error',
                'message': f'{provider_label} API密钥未配置'
            }

        base_url = (provider_config.get('base_url') or 'https://api.openai.com/v1').rstrip('/')
        target_model = self.get_effective_model(provider)
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.get(
                f"{base_url}/models",
                headers=headers,
                timeout=provider_config.get('timeout', 60)
            )

            if response.status_code == 200:
                payload = response.json()
                models = [item.get('id') for item in payload.get('data', []) if item.get('id')]
                model_available = target_model in models if models else True
                return {
                    'status': 'online' if model_available else 'model_not_found',
                    'message': f'{provider_label}服务正常，模型{"可用" if model_available else "不可用"}',
                    'models': models,
                    'target_model': target_model,
                    'provider': provider
                }

            if provider == 'qwen' and response.status_code in (404, 405):
                return {
                    'status': 'configured',
                    'message': 'Qwen 已完成配置，兼容模式未开放模型列表接口；将在首次对话时验证聊天接口。',
                    'target_model': target_model,
                    'provider': provider
                }

            return {
                'status': 'error',
                'message': f'{provider_label}服务响应异常: {response.status_code}',
                'target_model': target_model,
                'provider': provider
            }
        except requests.exceptions.ConnectionError:
            return {
                'status': 'offline',
                'message': f'{provider_label}服务无法连接',
                'target_model': target_model,
                'provider': provider
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'检查{provider_label}状态失败: {str(e)}',
                'target_model': target_model,
                'provider': provider
            }



# 全局LLM服务实例
_llm_service = None

def get_llm_service() -> LLMService:
    """获取LLM服务实例"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service 

# -*- coding: utf-8 -*-
import json

from flask import Response, g, jsonify, request, stream_with_context
from loguru import logger

from app.api import api_bp
from app.extensions import db
from app.services.ai_conversation_service import AIConversationService
from app.services.llm_service import LLMService
from app.services.user_activity_service import UserActivityService

# 速率限制（生产环境生效，开发环境为空操作）
try:
    from flask_limiter import Limiter as _LimiterCls
    _ai_limiter = _LimiterCls(key_func=lambda: request.remote_addr)
except Exception:
    class _NoOpLimiter:
        def limit(self, *a, **kw):
            def decorator(fn):
                return fn
            return decorator
    _ai_limiter = _NoOpLimiter()


def _require_current_user_id():
    current_user_id = getattr(getattr(g, 'current_user', None), 'id', None)
    if not current_user_id:
        return None, jsonify({'code': 401, 'message': '\u8bf7\u5148\u767b\u5f55\u540e\u518d\u4f7f\u7528 AI \u52a9\u624b\u3002', 'data': None}), 401
    return current_user_id, None, None


def _conversation_payload(conversation, messages=None):
    payload = {'conversation': conversation.to_dict() if conversation else None}
    if messages is not None:
        payload['messages'] = [message.to_dict() for message in messages]
    return payload


@api_bp.route('/ai/conversations', methods=['GET'])
def ai_conversations():
    current_user_id, error_response, status_code = _require_current_user_id()
    if error_response:
        return error_response, status_code

    try:
        AIConversationService.ensure_tables()
        keyword = (request.args.get('keyword') or '').strip()
        conversations = AIConversationService.search_conversations_for_user(current_user_id, keyword)
        return jsonify({
            'code': 200,
            'message': '\u6210\u529f',
            'data': {
                'items': [item.to_dict() for item in conversations],
                'total': len(conversations),
            }
        })
    except Exception as exc:
        logger.error(f'AI conversation list error: {exc}')
        return jsonify({'code': 500, 'message': f'\u52a0\u8f7d\u5bf9\u8bdd\u5217\u8868\u5931\u8d25: {exc}', 'data': None}), 500


@api_bp.route('/ai/conversations', methods=['POST'])
def create_ai_conversation():
    current_user_id, error_response, status_code = _require_current_user_id()
    if error_response:
        return error_response, status_code

    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip() or None

    try:
        AIConversationService.ensure_tables()
        conversation = AIConversationService.create_conversation(current_user_id, title=title)
        return jsonify({
            'code': 200,
            'message': '\u6210\u529f',
            'data': _conversation_payload(conversation, messages=[]),
        })
    except Exception as exc:
        db.session.rollback()
        logger.error(f'AI conversation create error: {exc}')
        return jsonify({'code': 500, 'message': f'\u65b0\u5efa\u5bf9\u8bdd\u5931\u8d25: {exc}', 'data': None}), 500


@api_bp.route('/ai/conversations/<int:conversation_id>/messages', methods=['GET'])
def ai_conversation_messages(conversation_id: int):
    current_user_id, error_response, status_code = _require_current_user_id()
    if error_response:
        return error_response, status_code

    try:
        AIConversationService.ensure_tables()
        conversation, messages = AIConversationService.list_messages(current_user_id, conversation_id)
        return jsonify({
            'code': 200,
            'message': '\u6210\u529f',
            'data': _conversation_payload(conversation, messages=messages),
        })
    except ValueError as exc:
        return jsonify({'code': 404, 'message': str(exc), 'data': None}), 404
    except Exception as exc:
        logger.error(f'AI conversation messages error: {exc}')
        return jsonify({'code': 500, 'message': f'\u52a0\u8f7d\u5bf9\u8bdd\u5931\u8d25: {exc}', 'data': None}), 500


@api_bp.route('/ai/conversations/<int:conversation_id>', methods=['PATCH'])
def rename_ai_conversation(conversation_id: int):
    current_user_id, error_response, status_code = _require_current_user_id()
    if error_response:
        return error_response, status_code

    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'code': 400, 'message': '\u5bf9\u8bdd\u6807\u9898\u4e0d\u80fd\u4e3a\u7a7a\u3002', 'data': None}), 400

    try:
        AIConversationService.ensure_tables()
        conversation = AIConversationService.rename_conversation(current_user_id, conversation_id, title)
        return jsonify({'code': 200, 'message': '\u6210\u529f', 'data': _conversation_payload(conversation)})
    except ValueError as exc:
        return jsonify({'code': 404, 'message': str(exc), 'data': None}), 404
    except Exception as exc:
        db.session.rollback()
        logger.error(f'AI conversation rename error: {exc}')
        return jsonify({'code': 500, 'message': f'\u91cd\u547d\u540d\u5bf9\u8bdd\u5931\u8d25: {exc}', 'data': None}), 500


@api_bp.route('/ai/conversations/<int:conversation_id>', methods=['DELETE'])
def delete_ai_conversation(conversation_id: int):
    current_user_id, error_response, status_code = _require_current_user_id()
    if error_response:
        return error_response, status_code

    try:
        AIConversationService.ensure_tables()
        AIConversationService.delete_conversation(current_user_id, conversation_id)
        return jsonify({'code': 200, 'message': '\u6210\u529f', 'data': {'conversation_id': conversation_id}})
    except ValueError as exc:
        return jsonify({'code': 404, 'message': str(exc), 'data': None}), 404
    except Exception as exc:
        db.session.rollback()
        logger.error(f'AI conversation delete error: {exc}')
        return jsonify({'code': 500, 'message': f'\u5220\u9664\u5bf9\u8bdd\u5931\u8d25: {exc}', 'data': None}), 500


@api_bp.route('/ai/chat', methods=['POST'])
@_ai_limiter.limit("20 per minute")  # AI 聊天接口限流：每分钟 20 次
def ai_chat():
    current_user_id, error_response, status_code = _require_current_user_id()
    if error_response:
        return error_response, status_code

    try:
        AIConversationService.ensure_tables()
        data = request.get_json(silent=True) or {}
        question = (data.get('question') or '').strip()
        conversation_id = data.get('conversation_id')
        stream = bool(data.get('stream', False))

        if not question:
            return jsonify({'code': 400, 'message': '\u8bf7\u6c42\u53c2\u6570\u9519\u8bef\uff0cquestion \u4e0d\u80fd\u4e3a\u7a7a', 'data': None}), 400

        if conversation_id in ('', None):
            conversation_id = None
        elif isinstance(conversation_id, str) and conversation_id.isdigit():
            conversation_id = int(conversation_id)
        elif not isinstance(conversation_id, int):
            return jsonify({'code': 400, 'message': 'conversation_id \u53c2\u6570\u65e0\u6548', 'data': None}), 400

        conversation, user_message = AIConversationService.prepare_conversation_for_question(
            current_user_id,
            question,
            conversation_id=conversation_id,
        )
        conversation_id = conversation.id
        user_message_id = user_message.id
        llm_messages = AIConversationService.build_messages_for_llm_by_id(current_user_id, conversation_id)
        llm = LLMService()

        if stream:
            assistant_message = AIConversationService.create_streaming_reply_placeholder(conversation_id)
            assistant_message_id = assistant_message.id
            initial_payload = {
                'conversation': AIConversationService.require_conversation(current_user_id, conversation_id).to_dict(),
                'user_message': AIConversationService.require_message(user_message_id, conversation_id=conversation_id).to_dict(),
                'assistant_message': AIConversationService.require_message(assistant_message_id, conversation_id=conversation_id).to_dict(),
            }

            def generate():
                full_answer = ''
                chunk_index = 0
                try:
                    yield ': ping\n\n'
                    yield f"data: {json.dumps(initial_payload, ensure_ascii=False)}\n\n"

                    for chunk in llm.stream_chat_completion(llm_messages):
                        if not chunk:
                            continue

                        full_answer += chunk
                        chunk_index += 1
                        AIConversationService.persist_stream_chunk(conversation_id, assistant_message_id, full_answer, chunk_index)
                        yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

                    AIConversationService.finalize_assistant_reply(conversation_id, assistant_message_id, full_answer)
                    try:
                        if full_answer.strip():
                            UserActivityService.record_chat(current_user_id, question, full_answer)
                    except Exception as legacy_exc:
                        db.session.rollback()
                        logger.error(f'Failed to save legacy ai chat history: {legacy_exc}')

                    latest_conversation = AIConversationService.require_conversation(current_user_id, conversation_id)
                    latest_assistant_message = AIConversationService.require_message(
                        assistant_message_id,
                        conversation_id=conversation_id,
                    )
                    yield f"data: {json.dumps({'done': True, 'conversation': latest_conversation.to_dict(), 'assistant_message': latest_assistant_message.to_dict()}, ensure_ascii=False)}\n\n"
                except Exception as exc:
                    try:
                        AIConversationService.mark_stream_failed(conversation_id, assistant_message_id, full_answer)
                    except Exception as save_exc:
                        db.session.rollback()
                        logger.error(f'Failed to mark ai stream error state: {save_exc}')
                    logger.error(f'Streaming response error: {exc}')
                    yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"

            response = Response(stream_with_context(generate()), mimetype='text/event-stream')
            response.headers['Cache-Control'] = 'no-cache'
            response.headers['X-Accel-Buffering'] = 'no'
            return response

        result = llm.chat_completion(llm_messages)
        if not result.get('success'):
            return jsonify({'code': 503, 'message': result.get('error') or 'AI \u670d\u52a1\u6682\u4e0d\u53ef\u7528', 'data': None}), 503

        answer = result.get('content') or ''
        assistant_message = AIConversationService.save_assistant_reply(conversation, answer)
        assistant_message_id = assistant_message.id
        try:
            if answer:
                UserActivityService.record_chat(current_user_id, question, answer)
        except Exception as legacy_exc:
            db.session.rollback()
            logger.error(f'Failed to save legacy ai chat history: {legacy_exc}')

        latest_conversation = AIConversationService.require_conversation(current_user_id, conversation_id)
        latest_user_message = AIConversationService.require_message(user_message_id, conversation_id=conversation_id)
        latest_assistant_message = AIConversationService.require_message(assistant_message_id, conversation_id=conversation_id)

        return jsonify({
            'code': 200,
            'message': '\u6210\u529f',
            'data': {
                'answer': answer,
                'conversation': latest_conversation.to_dict(),
                'user_message': latest_user_message.to_dict(),
                'assistant_message': latest_assistant_message.to_dict(),
            }
        })
    except ValueError as exc:
        return jsonify({'code': 404, 'message': str(exc), 'data': None}), 404
    except Exception as exc:
        db.session.rollback()
        logger.error(f'AI chat API error: {exc}')
        return jsonify({'code': 500, 'message': f'\u670d\u52a1\u5668\u9519\u8bef: {str(exc)}', 'data': None}), 500


@api_bp.route('/ai/status', methods=['GET'])
def ai_status():
    try:
        llm = LLMService()
        status = llm.check_service_status()
        return jsonify({
            'code': 200,
            'message': '\u6210\u529f',
            'data': status
        })
    except Exception as exc:
        logger.error(f'AI status API error: {exc}')
        return jsonify({
            'code': 500,
            'message': f'\u670d\u52a1\u5668\u9519\u8bef: {str(exc)}',
            'data': None
        }), 500

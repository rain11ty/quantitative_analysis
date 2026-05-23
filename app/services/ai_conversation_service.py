# -*- coding: utf-8 -*-
import re
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import or_

from app.extensions import db
from app.models import UserAiConversation, UserAiMessage


class AIConversationService:
    DEFAULT_TITLE = '\u65b0\u5bf9\u8bdd'
    DEFAULT_SUMMARY = '\u5f00\u59cb\u65b0\u7684\u91d1\u878d\u95ee\u7b54'
    SYSTEM_PROMPT = (
        '\u4f60\u662f\u4e00\u4e2a\u8d44\u6df1\u7684\u91d1\u878d\u91cf\u5316\u5206\u6790\u5e08\uff0c\u64c5\u957f\u89e3\u91ca\u91d1\u878d\u672f\u8bed\u3001\u5206\u6790\u5e02\u573a\u903b\u8f91\u548c\u63d0\u4f9b\u91cf\u5316\u6295\u8d44\u601d\u8def\u3002'
        '\u8bf7\u4f7f\u7528\u4e13\u4e1a\u3001\u6e05\u6670\u3001\u7a33\u5065\u4e14\u9002\u5408\u65b0\u624b\u7406\u89e3\u7684\u4e2d\u6587\u56de\u7b54\u7528\u6237\u95ee\u9898\u3002\n\n'
        '\u56de\u7b54\u65f6\u4f18\u5148\u6309\u7167\u201c\u7ed3\u8bba\u6982\u62ec\u3001\u6307\u6807\u89e3\u91ca\u3001\u98ce\u9669\u63d0\u793a\u3001\u5b66\u4e60\u5efa\u8bae\u201d\u7684\u7ed3\u6784\u7ec4\u7ec7\u5185\u5bb9\uff1b'
        '\u5f53\u6d89\u53ca MACD\u3001RSI\u3001KDJ\u3001\u5e03\u6797\u5e26\u3001\u5747\u7ebf\u3001\u6210\u4ea4\u91cf\u3001\u8d44\u91d1\u6d41\u5411\u7b49\u6307\u6807\u65f6\uff0c'
        '\u5e94\u5148\u7528\u901a\u4fd7\u8bed\u8a00\u89e3\u91ca\u6307\u6807\u542b\u4e49\uff0c\u518d\u8bf4\u660e\u5176\u53ef\u80fd\u53cd\u6620\u7684\u5e02\u573a\u72b6\u6001\u3002\n\n'
        '\u5f53\u7528\u6237\u8be2\u95ee\u5177\u4f53\u80a1\u7968\u4e70\u5356\u3001\u4ed3\u4f4d\u3001\u77ed\u7ebf\u64cd\u4f5c\u6216\u6536\u76ca\u5224\u65ad\u65f6\uff0c'
        '\u4e0d\u5f97\u76f4\u63a5\u7ed9\u51fa\u201c\u4e70\u5165\u3001\u5356\u51fa\u3001\u6ee1\u4ed3\u3001\u6e05\u4ed3\u3001\u5fc5\u6da8\u3001\u7a33\u8d5a\u201d\u7b49\u786e\u5b9a\u6027\u64cd\u4f5c\u6307\u4ee4\u6216\u6536\u76ca\u627f\u8bfa\uff0c'
        '\u5e94\u4ece\u8d8b\u52bf\u3001\u98ce\u9669\u3001\u9700\u8fdb\u4e00\u6b65\u89c2\u5bdf\u7684\u6570\u636e\u548c\u7528\u6237\u98ce\u9669\u627f\u53d7\u80fd\u529b\u89d2\u5ea6\u8fdb\u884c\u5206\u6790\u3002\n\n'
        '\u5f53\u7528\u6237\u4e0a\u4f20\u56fe\u7247\u65f6\uff0c\u5e94\u5148\u8bf4\u660e\u56fe\u7247\u4e2d\u80fd\u591f\u8bc6\u522b\u7684\u4fe1\u606f\uff0c\u518d\u7ed9\u51fa\u53ef\u80fd\u7684\u5206\u6790\u65b9\u5411\uff1b'
        '\u5982\u679c\u56fe\u7247\u4e0d\u6e05\u6670\uff0c\u6216\u7f3a\u5c11\u80a1\u7968\u4ee3\u7801\u3001\u65f6\u95f4\u5468\u671f\u3001\u5173\u952e\u6307\u6807\u7b49\u4fe1\u606f\uff0c\u5e94\u660e\u786e\u8bf4\u660e\u4e0d\u786e\u5b9a\u6027\u3002\n\n'
        '\u6d89\u53ca\u5b9e\u65f6\u884c\u60c5\u3001\u4ef7\u683c\u3001\u6da8\u8dcc\u5e45\u3001\u6392\u884c\u548c\u65b0\u95fb\u65f6\uff0c\u5e94\u63d0\u9192\u7528\u6237\u4ee5\u7cfb\u7edf\u9875\u9762\u6700\u65b0\u5c55\u793a\u6570\u636e\u548c\u5b98\u65b9\u62ab\u9732\u4fe1\u606f\u4e3a\u51c6\u3002'
        '\u56de\u7b54\u4ec5\u4f9b\u5b66\u4e60\u7814\u7a76\u548c\u8f85\u52a9\u5206\u6790\uff0c\u4e0d\u6784\u6210\u4efb\u4f55\u6295\u8d44\u5efa\u8bae\u3002'
    )
    MAX_CONTEXT_MESSAGES = 12
    MAX_CONTEXT_CHARS = 12000
    STREAM_SAVE_INTERVAL = 8

    @staticmethod
    def ensure_tables():
        UserAiConversation.__table__.create(bind=db.engine, checkfirst=True)
        UserAiMessage.__table__.create(bind=db.engine, checkfirst=True)

    @staticmethod
    def _normalize_title(title: Optional[str]) -> str:
        raw = re.sub(r'\s+', ' ', (title or '').strip())
        if not raw:
            return AIConversationService.DEFAULT_TITLE
        return raw[:120]

    @staticmethod
    def _build_preview(content: Optional[str], fallback: str = '') -> str:
        text = re.sub(r'\s+', ' ', (content or '').strip())
        if not text:
            text = re.sub(r'\s+', ' ', (fallback or '').strip())
        if len(text) > 90:
            return f'{text[:90]}...'
        return text

    @staticmethod
    def generate_title_from_question(question: str) -> str:
        text = re.sub(r'\s+', ' ', (question or '').strip())
        text = re.sub(r'^[#>*`\-\d\.\s]+', '', text)
        if not text:
            return AIConversationService.DEFAULT_TITLE
        if len(text) > 18:
            return f'{text[:18]}...'
        return text

    @staticmethod
    def _touch_conversation(conversation: UserAiConversation, preview: Optional[str] = None, touch_time: Optional[datetime] = None):
        now = touch_time or datetime.utcnow()
        conversation.last_message_at = now
        conversation.updated_at = now
        if preview is not None:
            conversation.summary = AIConversationService._build_preview(
                preview,
                fallback=conversation.summary or AIConversationService.DEFAULT_SUMMARY,
            )

    @staticmethod
    def _require_stream_entities(conversation_id: int, message_id: int) -> Tuple[UserAiConversation, UserAiMessage]:
        conversation = db.session.get(UserAiConversation, conversation_id)
        if conversation is None:
            conversation = UserAiConversation.query.filter_by(id=conversation_id).first()
        if conversation is None:
            raise ValueError('\u672a\u627e\u5230\u5bf9\u5e94\u7684\u5bf9\u8bdd\u8bb0\u5f55')

        message = db.session.get(UserAiMessage, message_id)
        if message is None or message.conversation_id != conversation_id:
            message = UserAiMessage.query.filter_by(id=message_id, conversation_id=conversation_id).first()
        if message is None:
            raise ValueError('\u672a\u627e\u5230\u5bf9\u5e94\u7684\u56de\u590d\u6d88\u606f')

        return conversation, message

    @staticmethod
    def list_conversations(user_id: int, limit: int = 50) -> List[UserAiConversation]:
        return UserAiConversation.query.filter_by(user_id=user_id).order_by(
            UserAiConversation.last_message_at.desc(),
            UserAiConversation.updated_at.desc(),
            UserAiConversation.id.desc(),
        ).limit(limit).all()

    @staticmethod
    def create_conversation(user_id: int, title: Optional[str] = None) -> UserAiConversation:
        now = datetime.utcnow()
        conversation = UserAiConversation(
            user_id=user_id,
            title=AIConversationService._normalize_title(title),
            summary=AIConversationService.DEFAULT_SUMMARY,
            created_at=now,
            updated_at=now,
            last_message_at=now,
        )
        db.session.add(conversation)
        db.session.commit()
        return conversation

    @staticmethod
    def get_conversation(user_id: int, conversation_id: int) -> Optional[UserAiConversation]:
        return UserAiConversation.query.filter_by(id=conversation_id, user_id=user_id).first()

    @staticmethod
    def require_conversation(user_id: int, conversation_id: int) -> UserAiConversation:
        conversation = AIConversationService.get_conversation(user_id, conversation_id)
        if conversation is None:
            raise ValueError('\u672a\u627e\u5230\u5bf9\u5e94\u7684\u5bf9\u8bdd\u8bb0\u5f55')
        return conversation

    @staticmethod
    def get_message(message_id: int, conversation_id: Optional[int] = None) -> Optional[UserAiMessage]:
        query = UserAiMessage.query.filter_by(id=message_id)
        if conversation_id is not None:
            query = query.filter_by(conversation_id=conversation_id)
        return query.first()

    @staticmethod
    def require_message(message_id: int, conversation_id: Optional[int] = None) -> UserAiMessage:
        message = AIConversationService.get_message(message_id, conversation_id=conversation_id)
        if message is None:
            raise ValueError('\u672a\u627e\u5230\u5bf9\u5e94\u7684\u6d88\u606f\u8bb0\u5f55')
        return message

    @staticmethod
    def list_messages(user_id: int, conversation_id: int) -> Tuple[UserAiConversation, List[UserAiMessage]]:
        conversation = AIConversationService.require_conversation(user_id, conversation_id)
        messages = conversation.messages.order_by(UserAiMessage.created_at.asc(), UserAiMessage.id.asc()).all()
        return conversation, messages

    @staticmethod
    def rename_conversation(user_id: int, conversation_id: int, title: str) -> UserAiConversation:
        conversation = AIConversationService.require_conversation(user_id, conversation_id)
        conversation.title = AIConversationService._normalize_title(title)
        conversation.updated_at = datetime.utcnow()
        db.session.commit()
        return conversation

    @staticmethod
    def delete_conversation(user_id: int, conversation_id: int):
        conversation = AIConversationService.require_conversation(user_id, conversation_id)
        db.session.delete(conversation)
        db.session.commit()

    @staticmethod
    def prepare_conversation_for_question(user_id: int, question: str, conversation_id: Optional[int] = None, images: Optional[List[str]] = None) -> Tuple[UserAiConversation, UserAiMessage]:
        conversation = AIConversationService.require_conversation(user_id, conversation_id) if conversation_id else AIConversationService.create_conversation(user_id)
        question_text = (question or '').strip()
        if not question_text and not images:
            raise ValueError('\u95ee\u9898\u4e0d\u80fd\u4e3a\u7a7a')

        if not conversation.title or conversation.title == AIConversationService.DEFAULT_TITLE:
            conversation.title = AIConversationService.generate_title_from_question(question_text or '[\u56fe\u7247]')

        user_message = UserAiMessage(
            conversation_id=conversation.id,
            role='user',
            content=question_text or '',
            message_images=images if images else None,
            status=UserAiMessage.STATUS_COMPLETED,
        )
        db.session.add(user_message)
        AIConversationService._touch_conversation(conversation, preview=question_text or '[\u56fe\u7247]')
        db.session.commit()
        return conversation, user_message

    @staticmethod
    def build_messages_for_llm(conversation: UserAiConversation) -> List[dict]:
        recent_records = conversation.messages.order_by(UserAiMessage.created_at.desc(), UserAiMessage.id.desc()).limit(
            AIConversationService.MAX_CONTEXT_MESSAGES * 3
        ).all()

        selected = []
        total_chars = 0
        for record in recent_records:
            content = (record.content or '').strip()
            has_images = bool(record.message_images)
            if (not content and not has_images) or record.status == UserAiMessage.STATUS_FAILED:
                continue

            if selected and len(selected) >= AIConversationService.MAX_CONTEXT_MESSAGES:
                break

            projected = total_chars + len(content)
            if selected and projected > AIConversationService.MAX_CONTEXT_CHARS:
                break

            if record.role == 'user' and has_images:
                multimodal_content = []
                if content:
                    multimodal_content.append({'type': 'text', 'text': content})
                for img_url in record.message_images:
                    multimodal_content.append({'type': 'image_url', 'image_url': {'url': img_url}})
                selected.append({'role': 'user', 'content': multimodal_content})
            else:
                selected.append({'role': record.role, 'content': content})
            total_chars = projected

        selected.reverse()
        return [{'role': 'system', 'content': AIConversationService.SYSTEM_PROMPT}, *selected]

    @staticmethod
    def build_messages_for_llm_by_id(user_id: int, conversation_id: int) -> List[dict]:
        conversation = AIConversationService.require_conversation(user_id, conversation_id)
        return AIConversationService.build_messages_for_llm(conversation)

    @staticmethod
    def create_streaming_reply_placeholder(conversation_id: int) -> UserAiMessage:
        conversation = UserAiConversation.query.filter_by(id=conversation_id).first()
        if conversation is None:
            raise ValueError('\u672a\u627e\u5230\u5bf9\u5e94\u7684\u5bf9\u8bdd\u8bb0\u5f55')

        message = UserAiMessage(
            conversation_id=conversation.id,
            role='assistant',
            content='',
            status=UserAiMessage.STATUS_STREAMING,
        )
        db.session.add(message)
        AIConversationService._touch_conversation(conversation)
        db.session.commit()
        return message

    @staticmethod
    def persist_stream_chunk(conversation_id: int, assistant_message_id: int, content: str, chunk_index: int):
        conversation, assistant_message = AIConversationService._require_stream_entities(conversation_id, assistant_message_id)
        assistant_message.content = content
        assistant_message.status = UserAiMessage.STATUS_STREAMING
        AIConversationService._touch_conversation(conversation, preview=content)
        if chunk_index % AIConversationService.STREAM_SAVE_INTERVAL == 0:
            db.session.commit()

    @staticmethod
    def finalize_assistant_reply(conversation_id: int, assistant_message_id: int, content: str) -> Tuple[UserAiConversation, UserAiMessage]:
        conversation, assistant_message = AIConversationService._require_stream_entities(conversation_id, assistant_message_id)
        assistant_message.content = (content or '').strip()
        assistant_message.status = UserAiMessage.STATUS_COMPLETED
        AIConversationService._touch_conversation(conversation, preview=assistant_message.content)
        db.session.commit()
        return conversation, assistant_message

    @staticmethod
    def mark_stream_failed(conversation_id: int, assistant_message_id: int, partial_content: str):
        conversation, assistant_message = AIConversationService._require_stream_entities(conversation_id, assistant_message_id)
        assistant_message.content = (partial_content or '').strip()
        assistant_message.status = UserAiMessage.STATUS_FAILED
        AIConversationService._touch_conversation(
            conversation,
            preview=partial_content or conversation.summary or AIConversationService.DEFAULT_SUMMARY,
        )
        db.session.commit()

    @staticmethod
    def save_assistant_reply(conversation: UserAiConversation, content: str) -> UserAiMessage:
        message = UserAiMessage(
            conversation_id=conversation.id,
            role='assistant',
            content=(content or '').strip(),
            status=UserAiMessage.STATUS_COMPLETED,
        )
        db.session.add(message)
        AIConversationService._touch_conversation(conversation, preview=message.content)
        db.session.commit()
        return message

    @staticmethod
    def search_conversations_for_user(user_id: int, keyword: str) -> List[UserAiConversation]:
        text = (keyword or '').strip()
        if not text:
            return AIConversationService.list_conversations(user_id)
        from app.utils.sql_utils import escape_like
        safe_text = escape_like(text)
        return UserAiConversation.query.filter(
            UserAiConversation.user_id == user_id,
            or_(
                UserAiConversation.title.ilike(f'%{safe_text}%', escape='\\'),
                UserAiConversation.summary.ilike(f'%{safe_text}%', escape='\\'),
            ),
        ).order_by(UserAiConversation.last_message_at.desc(), UserAiConversation.id.desc()).limit(50).all()

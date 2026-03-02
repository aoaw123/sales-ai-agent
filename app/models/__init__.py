"""
数据模型模块 - API 请求/响应的数据结构定义
"""

from app.models.chat import (
    AnalysisParams,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ContractParams,
    DocumentInfo,
    DocumentType,
    IntentAnalysisResult,
    MessageRole,
    PresentationParams,
    ProposalParams,
    QuoteParams,
    UserIntent,
)

__all__ = [
    "AnalysisParams",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ContractParams",
    "DocumentInfo",
    "DocumentType",
    "IntentAnalysisResult",
    "MessageRole",
    "PresentationParams",
    "ProposalParams",
    "QuoteParams",
    "UserIntent",
]

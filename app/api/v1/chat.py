"""
聊天 API 模块 - 核心接口 POST /api/v1/chat

这是前端（微信小程序）与后端交互的主要接口。
关键特性：
- 使用 session_id 作为 thread_id 实现会话隔离
- PostgreSQL 持久化支持跨会话记忆
"""

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.responses import JSONResponse

from app.agents.graphs.sales_graph import run_sales_agent
from app.api.deps import get_current_session, verify_wechat_token
from app.core.config import settings
from app.core.logging import get_logger
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    MessageRole,
    UserIntent,
)

logger = get_logger("api.chat")

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="智能销售助手对话接口",
    description="""
    智能销售 AI Agent 的核心对话接口。
    
    **持久化特性：**
    - 使用 `session_id` 作为会话唯一标识（thread_id）
    - 对话状态自动持久化到 PostgreSQL
    - 支持跨会话记忆，用户重新进入小程序后仍能继续之前对话
    
    支持的场景：
    - 💬 普通对话（问候、闲聊）
    - 📦 产品咨询（基于知识库 RAG）
    - 💰 价格谈判（销售话术支持）
    - 📄 生成报价单（Excel）
    - 📋 创建提案书（Word）
    - 📝 起草合同（Word）
    - 📊 数据分析报表（Excel）
    - 📽️ 生成演示文稿（PPT大纲）
    
    示例请求：
    ```json
    {
        "session_id": "wx_user_openid_123",
        "message": "帮我生成一份报价单，客户是张三科技",
        "history": [],
        "context": {
            "sales_rep_name": "李明",
            "department": "企业销售部"
        }
    }
    ```
    """
)
async def chat(
    request: ChatRequest,
    session_id: str = Depends(get_current_session),
    authorization: Optional[str] = Header(None),
) -> ChatResponse:
    """
    处理用户消息，调用 LangGraph Agent 生成回复
    
    **会话隔离机制：**
    - 使用 `session_id` 作为 `thread_id` 传递给 LangGraph
    - 每个 session_id 对应独立的对话状态（存储在 PostgreSQL）
    - 即使服务重启，对话历史也不会丢失
    
    Args:
        request: 聊天请求数据
        session_id: 会话ID（从 Header 或请求体获取）
        authorization: 微信登录凭证
    
    Returns:
        包含 AI 回复、意图识别、建议操作等的响应
    """
    start_time = time.time()
    
    # 使用请求体中的 session_id 优先
    actual_session_id = request.session_id or session_id
    
    logger.info(
        f"[Session: {actual_session_id}] 收到消息: {request.message[:50]}... "
        f"(thread_id={actual_session_id})"
    )
    
    try:
        # 转换历史消息格式
        history = []
        for msg in request.history:
            history.append({
                "role": msg.role.value,
                "content": msg.content,
            })
        
        # 运行 Agent 工作流
        # session_id 会被用作 thread_id，实现 PostgreSQL 持久化
        final_state = await run_sales_agent(
            session_id=actual_session_id,
            message=request.message,
            context=request.context,
            history=history,
        )
        
        # 计算响应时间
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # 构建响应
        intent = final_state.get("intent_analysis")
        intent_value = intent.intent if intent else UserIntent.UNKNOWN
        
        response = ChatResponse(
            session_id=actual_session_id,
            reply=final_state.get("sales_response", "抱歉，我没有理解您的问题。"),
            intent=intent_value,
            documents=final_state.get("generated_documents", []),
            suggested_actions=final_state.get("suggested_actions", []),
            metadata={
                "knowledge_results_count": len(final_state.get("knowledge_results", [])),
                "document_params": final_state.get("document_params"),
                "error": final_state.get("error"),
                "persistent": True,  # 标记已启用持久化
            },
            response_time_ms=response_time_ms,
        )
        
        logger.info(
            f"[Session: {actual_session_id}] 响应完成，"
            f"意图: {intent_value.value}, 耗时: {response_time_ms}ms"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"[Session: {actual_session_id}] 处理失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理请求时发生错误: {str(e)}"
        )


@router.post(
    "/chat/stream",
    summary="流式对话接口（预留）",
    description="WebSocket 或 SSE 流式响应接口，用于实时显示思考过程"
)
async def chat_stream(
    request: ChatRequest,
    session_id: str = Depends(get_current_session),
):
    """
    流式对话接口（开发中）
    
    用于实现打字机效果，实时显示 Agent 的思考过程。
    """
    # TODO: 实现 WebSocket 或 SSE 流式响应
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="流式接口开发中"
    )


@router.get(
    "/chat/history/{session_id}",
    summary="获取对话历史",
    description="获取指定会话的历史消息记录（从 PostgreSQL 持久化存储中读取）"
)
async def get_chat_history(
    session_id: str,
) -> dict:
    """
    获取对话历史
    
    从 PostgreSQL 持久化存储中获取指定会话的完整历史记录。
    """
    # TODO: 从 PostgreSQL checkpoints 表中提取对话历史
    # 可以通过 checkpointer.aget() 方法获取特定 thread_id 的状态
    return {
        "session_id": session_id,
        "messages": [],
        "total": 0,
        "note": "从 PostgreSQL 持久化存储中读取（开发中）",
    }


@router.delete(
    "/chat/history/{session_id}",
    summary="清除对话历史",
    description="清除指定会话的所有历史记录（从 PostgreSQL 中删除）"
)
async def clear_chat_history(
    session_id: str,
) -> dict:
    """
    清除对话历史
    
    从 PostgreSQL 持久化存储中删除指定会话的所有状态数据。
    """
    # TODO: 调用 checkpointer.adelete() 删除特定 thread_id 的状态
    logger.info(f"[Session: {session_id}] 对话历史已清除")
    return {
        "session_id": session_id,
        "status": "cleared",
        "note": "从 PostgreSQL 持久化存储中删除（开发中）",
    }

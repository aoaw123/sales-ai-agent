"""
销售 AI Agent 主工作流图 - LangGraph 编排（PostgreSQL 持久化版）

更新要点：
1. 使用 psycopg_pool.AsyncConnectionPool + AsyncPostgresSaver 实现持久化
2. 显式管理连接池生命周期，避免 async_generator 协议问题
3. 保留极简流转逻辑：单向、无阻碍、一气呵成
4. 彻底根除 tuple 越界：安全的状态提取
"""

from typing import Dict, Any, Optional, Union

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg_pool import AsyncConnectionPool
from psycopg import AsyncConnection

from app.core.config import settings
from app.core.logging import get_logger
from app.agents.state import SalesState, create_initial_state
from app.agents.nodes.intent_node import intent_recognition_node
from app.agents.nodes.knowledge_node import (
    knowledge_retrieval_node,
    knowledge_synthesis_node,
)
from app.agents.nodes.document_nodes import (
    extract_document_params_node,
    generate_document_node,
)
from app.agents.nodes.response_node import (
    sales_response_node,
    sales_negotiation_node,
    complaint_handler_node,
)

logger = get_logger("sales_graph")


def _create_workflow() -> StateGraph:
    """
    创建工作流图结构（不含 checkpointer）
    
    Returns:
        未编译的 StateGraph 实例
    """
    # 创建工作流图
    workflow = StateGraph(SalesState)
    
    # ═══════════════════════════════════════════════════════════════
    # 添加节点（只保留核心节点，移除 request_missing_params）
    # ═══════════════════════════════════════════════════════════════
    
    # 1. 意图识别节点（入口）
    workflow.add_node("intent_recognition", intent_recognition_node)
    
    # 2. 知识库检索节点
    workflow.add_node("knowledge_retrieval", knowledge_retrieval_node)
    workflow.add_node("knowledge_synthesis", knowledge_synthesis_node)
    
    # 3. 文档生成节点（移除 request_missing_params，直接生成）
    workflow.add_node("extract_document_params", extract_document_params_node)
    workflow.add_node("generate_document", generate_document_node)
    
    # 4. 销售回复节点
    workflow.add_node("sales_response", sales_response_node)
    workflow.add_node("sales_negotiation", sales_negotiation_node)
    workflow.add_node("complaint_handler", complaint_handler_node)
    
    # ═══════════════════════════════════════════════════════════════
    # 设置入口点
    # ═══════════════════════════════════════════════════════════════
    workflow.set_entry_point("intent_recognition")
    
    # ═══════════════════════════════════════════════════════════════
    # 添加边和条件（极简流转，无中断）
    # ═══════════════════════════════════════════════════════════════
    
    # 意图识别后的路由 → 根据 state["next_node"] 决定
    workflow.add_conditional_edges(
        "intent_recognition",
        _route_by_next_node,
        {
            "knowledge_retrieval": "knowledge_retrieval",
            "extract_document_params": "extract_document_params",
            "sales_negotiation": "sales_negotiation",
            "complaint_handler": "complaint_handler",
            "sales_response": "sales_response",
            # 兜底：任何未匹配的都到 sales_response
        }
    )
    
    # 知识库检索后的路由
    workflow.add_conditional_edges(
        "knowledge_retrieval",
        _route_by_knowledge_result,
        {
            "knowledge_synthesis": "knowledge_synthesis",
            "sales_response": "sales_response",
        }
    )
    
    # 知识整合后直接到销售回复
    workflow.add_edge("knowledge_synthesis", "sales_response")
    
    # 文档参数提取后直接生成文档（无中断、无询问）
    workflow.add_edge("extract_document_params", "generate_document")
    
    # 文档生成后结束
    workflow.add_edge("generate_document", END)
    
    # 销售相关节点后结束
    workflow.add_edge("sales_response", END)
    workflow.add_edge("sales_negotiation", END)
    workflow.add_edge("complaint_handler", END)
    
    return workflow


def _route_by_next_node(state: SalesState) -> str:
    """
    根据 state["next_node"] 路由到下一个节点
    
    这是意图识别节点后的统一路由函数。
    直接读取 intent_node 设置的 next_node 值，无额外逻辑。
    """
    next_node = state.get("next_node")
    
    if next_node:
        logger.debug(f"[Router] 路由到节点: {next_node}")
        return next_node
    
    # 默认兜底
    logger.warning("[Router] next_node 未设置，默认路由到 sales_response")
    return "sales_response"


def _route_by_knowledge_result(state: SalesState) -> str:
    """
    根据知识库检索结果路由
    
    如果有检索结果，进入知识整合；否则直接进入回复生成。
    （保留此路由因为需要根据检索结果做业务判断）
    """
    results = state.get("knowledge_results", [])
    
    if results and isinstance(results, list) and len(results) > 0:
        logger.debug(f"[Router] 检索到 {len(results)} 条知识，进入整合节点")
        return "knowledge_synthesis"
    
    logger.debug("[Router] 无知识检索结果，直接生成回复")
    return "sales_response"


# ═══════════════════════════════════════════════════════════════
# 向后兼容的同步 API（使用 MemorySaver）
# ═══════════════════════════════════════════════════════════════

def create_sales_graph():
    """
    创建销售 AI Agent 工作流图（同步版本，向后兼容）
    
    使用 MemorySaver 作为 checkpointer，适用于：
    - 测试环境
    - 不需要持久化的场景
    - 向后兼容旧代码
    
    Returns:
        编译后的 StateGraph 实例（使用 MemorySaver）
    """
    workflow = _create_workflow()
    
    # 使用内存存储（向后兼容）
    checkpointer = MemorySaver()
    compiled_graph = workflow.compile(checkpointer=checkpointer)
    
    logger.info("销售 AI Agent 工作流图编译完成（MemorySaver 版本）")
    
    return compiled_graph


# 全局图实例（使用 MemorySaver，用于向后兼容）
_sales_graph = None


def get_sales_graph():
    """
    获取销售图单例（同步版本，向后兼容）
    
    使用 MemorySaver，适用于测试和不需持久化的场景。
    如果需要 PostgreSQL 持久化，请使用 run_sales_agent()。
    
    Returns:
        编译后的 StateGraph 实例
    """
    global _sales_graph
    if _sales_graph is None:
        _sales_graph = create_sales_graph()
    return _sales_graph


# ═══════════════════════════════════════════════════════════════
# PostgreSQL 持久化 API（使用 psycopg_pool）
# ═══════════════════════════════════════════════════════════════

async def initialize_database() -> bool:
    """
    初始化数据库表结构
    
    在应用启动时调用，确保 LangGraph 所需的 checkpoints 表已创建。
    绕过连接池，使用独占单次连接，强制开启 autocommit 建表，
    以解决 CREATE INDEX CONCURRENTLY 不能在事务块内执行的问题。
    
    Returns:
        初始化是否成功
    """
    if not settings.database_url:
        logger.warning("[Init] 未配置 DATABASE_URL，跳过数据库初始化")
        return False
    
    try:
        logger.info("[Init] 正在初始化 PostgreSQL 数据库表...")
        
        # 绕过连接池，使用独占单次连接，强制开启 autocommit 建表
        # 关键参数：
        # - autocommit=True: 允许 CREATE INDEX CONCURRENTLY 执行
        # - gssencmode="disable": 禁用 GSSAPI 加密，避免连接问题
        # - prepare_threshold=0: 禁用 prepared statement 缓存（解决 Supabase 连接池冲突）
        conn = await AsyncConnection.connect(
            settings.database_url,
            autocommit=True,
            gssencmode="disable",
            prepare_threshold=0,
        )
        try:
            # 配置序列化器，允许反序列化 app.models.chat 模块中的自定义类型
            serde = JsonPlusSerializer(
                allowed_msgpack_modules=[
                    ("app.models.chat", "UserIntent"),
                    ("app.models.chat", "IntentAnalysisResult"),
                ]
            )
            checkpointer = AsyncPostgresSaver(conn, serde=serde)
            await checkpointer.setup()
        finally:
            await conn.close()
        
        logger.info("[Init] PostgreSQL 数据库表初始化完成 ✓")
        return True
        
    except Exception as e:
        logger.error(f"[Init] 数据库初始化失败: {e}")
        import traceback
        logger.debug(f"[Init] 错误详情: {traceback.format_exc()}")
        return False


async def run_sales_agent(
    session_id: str,
    message: str,
    context: dict = None,
    history: list = None
) -> Dict[str, Any]:
    """
    运行销售 AI Agent（PostgreSQL 持久化版）
    
    关键保证：
    1. 使用 PostgreSQL 持久化对话状态（跨会话记忆）
    2. 使用显式 AsyncConnectionPool 管理数据库连接
    3. 无论图怎么结束，都返回纯净 Dict
    4. 绝不触发 tuple index out of range
    5. 所有字段有兜底值
    
    Args:
        session_id: 会话唯一标识（作为 thread_id 用于状态隔离）
        message: 用户消息
        context: 业务上下文
        history: 历史消息
    
    Returns:
        最终状态字典（纯净 Dict，安全访问）
    """
    # 创建初始状态
    initial_state = create_initial_state(
        session_id=session_id,
        user_message=message,
        context=context,
        history=history
    )
    
    # 配置：关键！thread_id 用于会话隔离和持久化
    config = {
        "configurable": {"thread_id": session_id},
        "recursion_limit": settings.max_iterations,
    }
    
    logger.info(f"[Session: {session_id}] 开始执行工作流 (thread_id={session_id})")
    
    # ═══ 安全执行图并提取最终状态 ═══
    final_state: Dict[str, Any] = {}
    
    # 如果没有配置数据库，回退到内存存储
    if not settings.database_url:
        logger.warning("[Session: {session_id}] 未配置 DATABASE_URL，使用 MemorySaver")
        try:
            workflow = _create_workflow()
            checkpointer = MemorySaver()
            graph = workflow.compile(checkpointer=checkpointer)
            
            async for event in graph.astream(initial_state, config):
                if not isinstance(event, dict):
                    continue
                for node_name, state_value in event.items():
                    if isinstance(state_value, dict):
                        final_state = state_value
                    elif isinstance(state_value, (list, tuple)) and len(state_value) > 0:
                        first_item = state_value[0]
                        if isinstance(first_item, dict):
                            final_state = first_item
            
            logger.info(f"[Session: {session_id}] 工作流执行完成（内存模式）")
            
        except Exception as e:
            logger.error(f"[Graph] 工作流执行异常: {e}")
            final_state = {
                "session_id": session_id,
                "sales_response": "抱歉，处理您的请求时出现了问题。请稍后重试。",
                "suggested_actions": ["重新尝试", "联系客服"],
                "error": str(e),
            }
        
        final_state = _sanitize_final_state(final_state, session_id)
        return final_state
    
    # ═══ 使用 PostgreSQL 持久化执行 ═══
    
    try:
        # 创建显式连接池
        # 关键：使用 kwargs 传递 prepare_threshold=None 禁用 prepared statement 缓存
        async with AsyncConnectionPool(
            conninfo=settings.database_url,
            max_size=20,
            min_size=1,
            open=False,
            kwargs={"prepare_threshold": None},  # ← 关键：禁用 prepared statement
        ) as pool:
            await pool.open()
            logger.debug(f"[Session: {session_id}] PostgreSQL 连接池已打开")
            
            # 创建 checkpointer（配置序列化器允许自定义类型）
            serde = JsonPlusSerializer(
                allowed_msgpack_modules=[
                    ("app.models.chat", "UserIntent"),
                    ("app.models.chat", "IntentAnalysisResult"),
                ]
            )
            checkpointer = AsyncPostgresSaver(pool, serde=serde)
            
            # 创建工作流并编译
            workflow = _create_workflow()
            graph = workflow.compile(checkpointer=checkpointer)
            
            # 执行工作流
            async for event in graph.astream(initial_state, config):
                # event 是一个字典，key 是节点名，value 是状态
                # 例如：{"intent_recognition": {...state...}}
                
                if not isinstance(event, dict):
                    logger.warning(f"[Graph] 非预期事件类型: {type(event)}")
                    continue
                
                for node_name, state_value in event.items():
                    logger.debug(f"[Graph] 节点 {node_name} 执行完成")
                    
                    # 安全提取状态（处理各种可能的类型）
                    if isinstance(state_value, dict):
                        final_state = state_value
                    elif isinstance(state_value, (list, tuple)) and len(state_value) > 0:
                        # 如果是列表/元组，取第一个元素
                        first_item = state_value[0]
                        if isinstance(first_item, dict):
                            final_state = first_item
                        else:
                            logger.warning(f"[Graph] 非预期的状态类型在列表中: {type(first_item)}")
                    else:
                        logger.warning(f"[Graph] 非预期的状态类型: {type(state_value)}")
            
            logger.info(f"[Session: {session_id}] 工作流执行完成（PostgreSQL 持久化）")
        
    except Exception as e:
        logger.error(f"[Graph] 工作流执行异常: {e}")
        import traceback
        logger.debug(f"[Graph] 错误详情: {traceback.format_exc()}")
        # 执行失败也返回兜底状态
        final_state = {
            "session_id": session_id,
            "sales_response": "抱歉，处理您的请求时出现了问题。请稍后重试。",
            "suggested_actions": ["重新尝试", "联系客服"],
            "error": str(e),
        }
    
    # ═══ 状态净化：确保所有字段有兜底值 ═══
    final_state = _sanitize_final_state(final_state, session_id)
    
    return final_state


def _sanitize_final_state(state: Any, session_id: str) -> Dict[str, Any]:
    """
    净化最终状态：确保返回纯净 Dict，所有字段有兜底值
    
    这是防御 tuple 越界的核心函数。
    """
    # 如果 state 不是字典，创建新的
    if not isinstance(state, dict):
        logger.warning(f"[Sanitize] 状态非字典类型: {type(state)}，创建默认状态")
        state = {}
    
    # 确保关键字段存在且有有效值
    sanitized = {
        # 会话信息
        "session_id": state.get("session_id") or session_id,
        
        # 回复内容（绝不为 None）
        "sales_response": _safe_get_str(state, "sales_response", "处理完成，请查看相关文档。"),
        
        # 建议操作
        "suggested_actions": _safe_get_list(state, "suggested_actions"),
        
        # 生成的文档列表
        "generated_documents": _safe_get_list(state, "generated_documents"),
        
        # 意图分析（可能为 None，但字典结构安全）
        "intent_analysis": state.get("intent_analysis"),
        
        # 上下文
        "context": state.get("context") or {},
        
        # 知识检索结果
        "knowledge_results": _safe_get_list(state, "knowledge_results"),
        
        # 对话历史
        "messages": _safe_get_list(state, "messages"),
        
        # 元数据
        "metadata": state.get("metadata") or {},
        
        # 错误信息（如果有）
        "error": state.get("error"),
    }
    
    return sanitized


def _safe_get_str(state: Dict, key: str, default: str = "") -> str:
    """安全获取字符串字段"""
    value = state.get(key)
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def _safe_get_list(state: Dict, key: str) -> list:
    """安全获取列表字段"""
    value = state.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


# ═══════════════════════════════════════════════════════════════
# 便捷函数：提取核心响应数据
# ═══════════════════════════════════════════════════════════════

def extract_response_data(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    从最终状态中提取前端需要的核心响应数据
    
    这是 API 层调用的辅助函数，确保字段安全。
    """
    return {
        "session_id": final_state.get("session_id", ""),
        "reply": final_state.get("sales_response", ""),
        "intent": final_state.get("intent_analysis", {}).get("intent", "unknown") if final_state.get("intent_analysis") else "unknown",
        "documents": [
            {
                "filename": doc.get("file_name", ""),
                "path": doc.get("file_path", ""),
                "type": doc.get("doc_type", ""),
                "size": doc.get("file_size", 0),
            }
            for doc in final_state.get("generated_documents", [])
            if isinstance(doc, dict)
        ],
        "suggested_actions": final_state.get("suggested_actions", []),
        "metadata": final_state.get("metadata", {}),
    }

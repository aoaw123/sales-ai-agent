"""
销售 AI Agent 主工作流图 - LangGraph 编排（重构版）

重构要点：
1. 彻底移除中断机制（interrupt_before/after）
2. 极简流转逻辑：单向、无阻碍、一气呵成
3. 彻底根除 tuple 越界：安全的状态提取
"""

from typing import Dict, Any, Optional, Union

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

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


def create_sales_graph() -> StateGraph:
    """
    创建销售 AI Agent 工作流图（极简无中断版）
    
    工作流结构（单向流转，无阻碍）：
    
                         ┌─────────────────┐
                         │ intent_recognition│
                         └────────┬────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
        ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
        │  knowledge    │ │ extract_doc   │ │    sales      │
        │  _retrieval    │ │   _params     │ │  _response    │
        └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
                │                 │                 │
                ▼                 ▼                 │
        ┌───────────────┐ ┌───────────────┐        │
        │  knowledge    │ │  generate     │        │
        │  _synthesis    │ │  _document    │        │
        └───────┬───────┘ └───────┬───────┘        │
                │                 │                │
                └────────┬────────┘                │
                         │                        │
                         ▼                        ▼
                    ┌─────────┐              ┌─────────┐
                    │   END   │◄─────────────│   END   │
                    └─────────┘              └─────────┘
    
    Returns:
        编译后的 StateGraph 实例
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
    
    # ═══════════════════════════════════════════════════════════════
    # 编译图（彻底移除中断机制）
    # ═══════════════════════════════════════════════════════════════
    
    # 添加内存检查点（用于保存对话状态，但不断中断）
    checkpointer = MemorySaver()
    
    compiled_graph = workflow.compile(
        checkpointer=checkpointer,
        # ❌ 移除：interrupt_before=["request_missing_params"]
        # ❌ 移除：interrupt_after=[...]
    )
    
    logger.info("销售 AI Agent 工作流图编译完成（极简无中断版）")
    
    return compiled_graph


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
# 全局图实例
# ═══════════════════════════════════════════════════════════════

_sales_graph = None


def get_sales_graph():
    """获取销售图单例"""
    global _sales_graph
    if _sales_graph is None:
        _sales_graph = create_sales_graph()
    return _sales_graph


# ═══════════════════════════════════════════════════════════════
# 安全的图执行函数（彻底根除 tuple 越界）
# ═══════════════════════════════════════════════════════════════

async def run_sales_agent(
    session_id: str,
    message: str,
    context: dict = None,
    history: list = None
) -> Dict[str, Any]:
    """
    运行销售 AI Agent（安全执行版）
    
    关键保证：
    1. 无论图怎么结束，都返回纯净 Dict
    2. 绝不触发 tuple index out of range
    3. 所有字段有兜底值
    
    Args:
        session_id: 会话唯一标识
        message: 用户消息
        context: 业务上下文
        history: 历史消息
    
    Returns:
        最终状态字典（纯净 Dict，安全访问）
    """
    graph = get_sales_graph()
    
    # 创建初始状态
    initial_state = create_initial_state(
        session_id=session_id,
        user_message=message,
        context=context,
        history=history
    )
    
    # 配置
    config = {
        "configurable": {"thread_id": session_id},
        "recursion_limit": settings.max_iterations,
    }
    
    logger.info(f"[Session: {session_id}] 开始执行工作流")
    
    # ═══ 安全执行图并提取最终状态 ═══
    final_state: Dict[str, Any] = {}
    
    try:
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
        
        logger.info(f"[Session: {session_id}] 工作流执行完成")
        
    except Exception as e:
        logger.error(f"[Graph] 工作流执行异常: {e}")
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

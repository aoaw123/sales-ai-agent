"""
销售 AI Agent 主工作流图 - LangGraph 编排

这是整个 Agent 的核心工作流，定义了节点之间的流转关系。
"""

from typing import Literal

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
    request_missing_params_node,
    generate_document_node,
)
from app.agents.nodes.response_node import (
    sales_response_node,
    sales_negotiation_node,
    complaint_handler_node,
    clarify_document_type_node,
)

logger = get_logger("sales_graph")


def create_sales_graph() -> StateGraph:
    """
    创建销售 AI Agent 工作流图
    
    工作流结构：
    
                         ┌──────────────────┐
                         │  intent_recognition │
                         └────────┬─────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
           ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
           │   knowledge  │ │   document  │ │    sales    │
           │  _retrieval   │ │   _params    │ │  _response   │
           └──────┬──────┘ └──────┬──────┘ └─────────────┘
                  │               │
                  ▼               │
         ┌─────────────┐          │
         │  knowledge  │          │
         │ _synthesis   │          │
         └──────┬──────┘          │
                │                 │
                │   ┌─────────────┘
                │   │
                ▼   ▼
           ┌─────────────┐
           │   generate   │
           │  _document   │
           └─────────────┘
    
    Returns:
        编译后的 StateGraph 实例
    """
    
    # 创建工作流图
    workflow = StateGraph(SalesState)
    
    # ============ 添加节点 ============
    
    # 1. 意图识别节点（入口）
    workflow.add_node("intent_recognition", intent_recognition_node)
    
    # 2. 知识库检索节点
    workflow.add_node("knowledge_retrieval", knowledge_retrieval_node)
    workflow.add_node("knowledge_synthesis", knowledge_synthesis_node)
    
    # 3. 文档生成节点
    workflow.add_node("extract_document_params", extract_document_params_node)
    workflow.add_node("request_missing_params", request_missing_params_node)
    workflow.add_node("generate_document", generate_document_node)
    workflow.add_node("clarify_document_type", clarify_document_type_node)
    
    # 4. 销售回复节点
    workflow.add_node("sales_response", sales_response_node)
    workflow.add_node("sales_negotiation", sales_negotiation_node)
    workflow.add_node("complaint_handler", complaint_handler_node)
    
    # ============ 设置入口点 ============
    workflow.set_entry_point("intent_recognition")
    
    # ============ 添加边和条件 ============
    
    # 意图识别后的路由
    workflow.add_conditional_edges(
        "intent_recognition",
        _route_by_intent,
        {
            "knowledge_retrieval": "knowledge_retrieval",
            "extract_document_params": "extract_document_params",
            "clarify_document_type": "clarify_document_type",
            "sales_negotiation": "sales_negotiation",
            "complaint_handler": "complaint_handler",
            "sales_response": "sales_response",
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
    
    # 文档参数提取后的路由
    workflow.add_conditional_edges(
        "extract_document_params",
        _route_by_params_status,
        {
            "request_missing_params": "request_missing_params",
            "generate_document": "generate_document",
        }
    )
    
    # 参数补充请求后直接结束（等待用户回复）
    workflow.add_edge("request_missing_params", END)
    
    # 文档生成后结束
    workflow.add_edge("generate_document", END)
    
    # 澄清文档类型后结束
    workflow.add_edge("clarify_document_type", END)
    
    # 销售相关节点后结束
    workflow.add_edge("sales_response", END)
    workflow.add_edge("sales_negotiation", END)
    workflow.add_edge("complaint_handler", END)
    
    # ============ 编译图 ============
    
    # 添加内存检查点（用于保存对话状态）
    checkpointer = MemorySaver()
    
    compiled_graph = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["request_missing_params"],  # 在请求参数前可中断
    )
    
    logger.info("销售 AI Agent 工作流图编译完成")
    
    return compiled_graph


def _route_by_intent(state: SalesState) -> str:
    """
    根据意图分析结果路由到下一个节点
    
    这是意图识别节点后的条件路由函数。
    """
    next_node = state.get("next_node")
    
    if next_node:
        logger.debug(f"路由到节点: {next_node}")
        return next_node
    
    # 默认路由
    return "sales_response"


def _route_by_knowledge_result(state: SalesState) -> str:
    """
    根据知识库检索结果路由
    
    如果有检索结果，进入知识整合；否则直接进入回复生成。
    """
    results = state.get("knowledge_results", [])
    
    if results and len(results) > 0:
        logger.debug(f"检索到 {len(results)} 条知识，进入整合节点")
        return "knowledge_synthesis"
    
    logger.debug("无知识检索结果，直接生成回复")
    return "sales_response"


def _route_by_params_status(state: SalesState) -> str:
    """
    根据参数提取状态路由
    
    如果有缺失的关键参数，请求补充；否则直接生成文档。
    """
    doc_params = state.get("document_params", {})
    missing = doc_params.get("missing", [])
    
    # 检查是否有缺失的关键参数
    critical_params = ["customer_name", "party_a", "party_b", "title"]
    missing_critical = [p for p in missing if p in critical_params]
    
    if missing_critical:
        logger.info(f"缺少关键参数: {missing_critical}")
        return "request_missing_params"
    
    logger.info("参数完整，进入文档生成")
    return "generate_document"


# 全局图实例
_sales_graph = None


def get_sales_graph():
    """获取销售图单例"""
    global _sales_graph
    if _sales_graph is None:
        _sales_graph = create_sales_graph()
    return _sales_graph


async def run_sales_agent(
    session_id: str,
    message: str,
    context: dict = None,
    history: list = None
) -> SalesState:
    """
    运行销售 AI Agent
    
    Args:
        session_id: 会话唯一标识
        message: 用户消息
        context: 业务上下文
        history: 历史消息
    
    Returns:
        最终状态
    """
    graph = get_sales_graph()
    
    # 创建初始状态
    initial_state = create_initial_state(
        session_id=session_id,
        user_message=message,
        context=context,
        history=history
    )
    
    # 配置（用于检查点）
    config = {
        "configurable": {"thread_id": session_id},
        "recursion_limit": settings.max_iterations,
    }
    
    logger.info(f"[Session: {session_id}] 开始执行工作流")
    
    # 执行工作流
    final_state = None
    async for event in graph.astream(initial_state, config):
        for key, value in event.items():
            logger.debug(f"节点 {key} 执行完成")
            final_state = value
    
    logger.info(f"[Session: {session_id}] 工作流执行完成")
    
    return final_state

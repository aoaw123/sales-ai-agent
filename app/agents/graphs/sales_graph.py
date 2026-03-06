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
        # 注意：已移除 interrupt_before，确保报价单生成流程一气呵成
        # 不再在 request_missing_params 前中断，所有缺失参数使用默认值填充
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
    
    注意：当前策略是强制生成文档，即使缺少参数也使用默认值直接生成，
    不再反问用户补充参数，确保流程一气呵成。
    """
    doc_params = state.get("document_params", {})
    missing = doc_params.get("missing", [])
    
    # 记录缺失的参数用于日志，但不再阻断流程
    if missing:
        logger.info(f"检测到缺失参数，将使用默认值直接生成: {missing}")
    
    # 强制进入文档生成节点，不再请求补充参数
    logger.info("参数已就绪（含默认值），直接进入文档生成")
    return "generate_document"


# 全局图实例
_sales_graph = None


def get_sales_graph():
    """获取销售图单例"""
    global _sales_graph
    if _sales_graph is None:
        _sales_graph = create_sales_graph()
    return _sales_graph


def _safe_extract_state(value, graph=None, config=None) -> dict:
    """
    安全地从 LangGraph 返回值中提取状态
    
    处理以下情况：
    1. 直接的 state 字典
    2. 元组 (state, config) - 可能为空元组
    3. None 或其他异常值
    
    如果返回空元组且提供了 graph 和 config，
    使用 graph.get_state(config).values 获取当前状态
    """
    # 情况1：已经是字典，直接返回
    if isinstance(value, dict):
        return value
    
    # 情况2：是元组，需要安全提取
    if isinstance(value, tuple):
        if len(value) > 0:
            # 有内容，提取第一个元素
            first_elem = value[0]
            # 如果第一个元素是字典，返回它
            if isinstance(first_elem, dict):
                return first_elem
            # 否则可能是 state 对象，尝试转换为 dict
            elif hasattr(first_elem, '__dict__'):
                return first_elem.__dict__
            else:
                return {"_raw_state": first_elem}
        else:
            # 空元组！说明 LangGraph 被 interrupt 中断了
            logger.warning("LangGraph 返回空元组，尝试从检查点恢复状态")
            if graph is not None and config is not None:
                try:
                    # 使用 get_state 获取当前状态
                    checkpoint_state = graph.get_state(config)
                    if checkpoint_state and hasattr(checkpoint_state, 'values'):
                        return checkpoint_state.values
                    elif isinstance(checkpoint_state, dict):
                        return checkpoint_state
                except Exception as e:
                    logger.error(f"从检查点恢复状态失败: {e}")
            # 无法恢复，返回空字典
            return {}
    
    # 情况3：是 state 对象，有 values 属性（LangGraph 的新版本可能返回这种）
    if hasattr(value, 'values') and isinstance(value.values, dict):
        return value.values
    
    # 情况4：其他类型，尝试转换
    if value is not None:
        if hasattr(value, '__dict__'):
            return value.__dict__
        return {"_raw_state": value}
    
    # 情况5：None，返回空字典
    return {}


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
        最终状态（始终返回字典，不会是元组）
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
    last_valid_state = None
    
    try:
        async for event in graph.astream(initial_state, config):
            for key, value in event.items():
                logger.debug(f"节点 {key} 执行完成")
                # 安全地提取状态
                extracted = _safe_extract_state(value, graph, config)
                if extracted:
                    last_valid_state = extracted
                    final_state = extracted
    except Exception as e:
        logger.error(f"工作流执行异常: {e}")
        # 尝试从检查点获取状态
        final_state = _safe_extract_state((), graph, config)
    
    logger.info(f"[Session: {session_id}] 工作流执行完成")
    
    # 最终安全检查：确保返回的是 dict，不是 tuple 或 None
    final_state = _safe_extract_state(final_state, graph, config)
    
    # 如果最终状态为空但之前有有效状态，使用之前的
    if not final_state and last_valid_state:
        final_state = last_valid_state
        logger.info(f"[Session: {session_id}] 使用最后有效状态")
    
    # 确保至少有基本的字段
    if not final_state:
        final_state = {
            "session_id": session_id,
            "sales_response": "正在处理您的请求，请稍后再试。",
            "error": "无法获取有效状态"
        }
    
    return final_state

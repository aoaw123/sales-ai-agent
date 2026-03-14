"""
工作流图模块 - PostgreSQL 持久化版本

导出内容：
- create_sales_graph: 创建并编译工作流图（同步，MemorySaver，向后兼容）
- get_sales_graph: 获取图单例（同步，MemorySaver，向后兼容）
- initialize_database: 初始化 PostgreSQL 表结构（异步）
- run_sales_agent: 运行销售 Agent（异步，PostgreSQL 持久化）
- extract_response_data: 提取响应数据（同步）
"""

from app.agents.graphs.sales_graph import (
    create_sales_graph,
    get_sales_graph,
    initialize_database,
    run_sales_agent,
    extract_response_data,
    # 路由函数（用于测试）
    _route_by_next_node,
    _route_by_knowledge_result,
    # 状态净化函数（用于测试）
    _sanitize_final_state,
    _safe_get_str,
    _safe_get_list,
)

__all__ = [
    "create_sales_graph",
    "get_sales_graph",
    "initialize_database",
    "run_sales_agent",
    "extract_response_data",
    "_route_by_next_node",
    "_route_by_knowledge_result",
    "_sanitize_final_state",
    "_safe_get_str",
    "_safe_get_list",
]

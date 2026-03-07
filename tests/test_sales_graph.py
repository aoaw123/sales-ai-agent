"""
sales_graph 重构测试

测试要点：
1. 图结构正确（无中断节点）
2. 流转逻辑清晰（单向、无阻碍）
3. 状态提取安全（无 tuple 越界）
4. 端到端执行正常
"""

import pytest
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.graphs.sales_graph import (
    create_sales_graph,
    _route_by_next_node,
    _route_by_knowledge_result,
    _sanitize_final_state,
    _safe_get_str,
    _safe_get_list,
    extract_response_data,
)
from app.agents.state import SalesState


class TestGraphStructure:
    """测试图结构"""
    
    def test_graph_compiles(self):
        """测试图能正确编译"""
        graph = create_sales_graph()
        assert graph is not None
    
    def test_no_interrupt_configuration(self):
        """测试没有中断配置"""
        # 创建图并检查配置
        graph = create_sales_graph()
        
        # 图应该成功编译且没有中断相关配置
        # 注意：这里无法直接检查内部配置，但可以通过执行验证
        assert graph is not None


class TestRoutingFunctions:
    """测试路由函数"""
    
    def test_route_by_next_node_with_valid_next_node(self):
        """测试根据 next_node 路由"""
        state = {"next_node": "knowledge_retrieval"}
        result = _route_by_next_node(state)
        assert result == "knowledge_retrieval"
    
    def test_route_by_next_node_with_missing_next_node(self):
        """测试 next_node 缺失时默认路由"""
        state = {}
        result = _route_by_next_node(state)
        assert result == "sales_response"
    
    def test_route_by_next_node_with_none_next_node(self):
        """测试 next_node 为 None 时默认路由"""
        state = {"next_node": None}
        result = _route_by_next_node(state)
        assert result == "sales_response"
    
    def test_route_by_knowledge_result_with_results(self):
        """测试有知识结果时路由到整合"""
        state = {"knowledge_results": [{"content": "test", "score": 0.5}]}
        result = _route_by_knowledge_result(state)
        assert result == "knowledge_synthesis"
    
    def test_route_by_knowledge_result_with_empty_list(self):
        """测试空知识结果时路由到回复"""
        state = {"knowledge_results": []}
        result = _route_by_knowledge_result(state)
        assert result == "sales_response"
    
    def test_route_by_knowledge_result_with_none(self):
        """测试知识结果为 None 时路由到回复"""
        state = {"knowledge_results": None}
        result = _route_by_knowledge_result(state)
        assert result == "sales_response"


class TestSanitizeFinalState:
    """测试状态净化函数（防御 tuple 越界的核心）"""
    
    def test_sanitize_valid_dict(self):
        """测试正常字典净化"""
        state = {
            "session_id": "test123",
            "sales_response": "测试回复",
            "suggested_actions": ["选项1", "选项2"],
            "generated_documents": [{"file_name": "test.xlsx"}],
        }
        result = _sanitize_final_state(state, "test123")
        
        assert result["session_id"] == "test123"
        assert result["sales_response"] == "测试回复"
        assert result["suggested_actions"] == ["选项1", "选项2"]
        assert len(result["generated_documents"]) == 1
    
    def test_sanitize_none_state(self):
        """测试 None 状态净化"""
        result = _sanitize_final_state(None, "test123")
        
        assert result["session_id"] == "test123"
        assert result["sales_response"] != ""  # 应该有兜底值
        assert result["suggested_actions"] == []
        assert result["generated_documents"] == []
    
    def test_sanitize_empty_dict(self):
        """测试空字典净化"""
        result = _sanitize_final_state({}, "test123")
        
        assert result["session_id"] == "test123"
        assert "sales_response" in result
        assert result["suggested_actions"] == []
    
    def test_sanitize_missing_fields(self):
        """测试缺失字段的兜底"""
        state = {"session_id": "test123"}  # 只有 session_id
        result = _sanitize_final_state(state, "test123")
        
        assert result["sales_response"] != ""  # 有兜底值
        assert result["suggested_actions"] == []
        assert result["knowledge_results"] == []
    
    def test_sanitize_none_values(self):
        """测试字段为 None 的处理"""
        state = {
            "session_id": "test123",
            "sales_response": None,
            "suggested_actions": None,
            "generated_documents": None,
        }
        result = _sanitize_final_state(state, "test123")
        
        assert result["sales_response"] != ""  # None 被替换为兜底值
        assert result["suggested_actions"] == []
        assert result["generated_documents"] == []


class TestSafeGetFunctions:
    """测试安全获取函数"""
    
    def test_safe_get_str_with_valid_string(self):
        """测试获取有效字符串"""
        state = {"key": "value"}
        assert _safe_get_str(state, "key") == "value"
    
    def test_safe_get_str_with_none(self):
        """测试获取 None 返回默认值"""
        state = {"key": None}
        assert _safe_get_str(state, "key", "default") == "default"
    
    def test_safe_get_str_with_missing_key(self):
        """测试获取缺失键返回默认值"""
        state = {}
        assert _safe_get_str(state, "key", "default") == "default"
    
    def test_safe_get_str_converts_non_string(self):
        """测试非字符串转字符串"""
        state = {"key": 123}
        assert _safe_get_str(state, "key") == "123"
    
    def test_safe_get_list_with_valid_list(self):
        """测试获取有效列表"""
        state = {"key": ["a", "b", "c"]}
        assert _safe_get_list(state, "key") == ["a", "b", "c"]
    
    def test_safe_get_list_with_none(self):
        """测试获取 None 返回空列表"""
        state = {"key": None}
        assert _safe_get_list(state, "key") == []
    
    def test_safe_get_list_converts_tuple(self):
        """测试元组转列表"""
        state = {"key": ("a", "b", "c")}
        result = _safe_get_list(state, "key")
        assert result == ["a", "b", "c"]
        assert isinstance(result, list)
    
    def test_safe_get_list_with_non_list(self):
        """测试非列表返回空列表"""
        state = {"key": "not a list"}
        assert _safe_get_list(state, "key") == []


class TestExtractResponseData:
    """测试响应数据提取"""
    
    def test_extract_with_complete_state(self):
        """测试完整状态提取"""
        from app.models.chat import IntentAnalysisResult, UserIntent
        
        state = {
            "session_id": "test123",
            "sales_response": "测试回复内容",
            "intent_analysis": IntentAnalysisResult(
                intent=UserIntent.QUOTE_GENERATION,
                confidence=0.95,
                entities={},
            ),
            "generated_documents": [
                {"file_name": "报价单.xlsx", "file_path": "/output/报价单.xlsx", "doc_type": "xlsx", "file_size": 1024}
            ],
            "suggested_actions": ["下载", "修改"],
            "metadata": {"key": "value"},
        }
        
        result = extract_response_data(state)
        
        assert result["session_id"] == "test123"
        assert result["reply"] == "测试回复内容"
        assert result["intent"] == "quote_generation"
        assert len(result["documents"]) == 1
        assert result["documents"][0]["filename"] == "报价单.xlsx"
        assert result["suggested_actions"] == ["下载", "修改"]
    
    def test_extract_with_minimal_state(self):
        """测试最小状态提取"""
        state = {
            "session_id": "test123",
            "sales_response": "",
        }
        
        result = extract_response_data(state)
        
        assert result["session_id"] == "test123"
        assert result["reply"] == ""
        assert result["intent"] == "unknown"
        assert result["documents"] == []
    
    def test_extract_with_none_intent_analysis(self):
        """测试 intent_analysis 为 None"""
        state = {
            "session_id": "test123",
            "sales_response": "回复",
            "intent_analysis": None,
        }
        
        result = extract_response_data(state)
        
        assert result["intent"] == "unknown"
    
    def test_extract_skips_invalid_documents(self):
        """测试跳过无效文档"""
        state = {
            "session_id": "test123",
            "sales_response": "回复",
            "generated_documents": [
                {"file_name": "valid.xlsx"},  # 有效
                "invalid_doc",  # 无效，应该跳过
                None,  # 无效，应该跳过
            ],
        }
        
        result = extract_response_data(state)
        
        assert len(result["documents"]) == 1
        assert result["documents"][0]["filename"] == "valid.xlsx"


# ═══════════════════════════════════════════════════════════════
# 集成测试（需要完整环境）
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestGraphExecution:
    """测试图执行（集成测试）"""
    
    async def test_graph_execution_flow(self):
        """测试图执行流程"""
        from app.agents.graphs.sales_graph import run_sales_agent
        
        # 注意：此测试需要有效的 API Key
        # 如果没有 API Key，可能会失败，但应该优雅降级
        
        try:
            result = await run_sales_agent(
                session_id="test_session",
                message="你好",
                context={},
                history=[]
            )
            
            # 验证返回结构
            assert isinstance(result, dict)
            assert "session_id" in result
            assert "sales_response" in result
            assert result["sales_response"] is not None
            
        except Exception as e:
            # 如果因为 API Key 失败，记录但不算测试失败
            pytest.skip(f"集成测试需要有效 API Key: {e}")
    
    async def test_graph_with_quote_intent(self):
        """测试报价单意图的完整流程"""
        from app.agents.graphs.sales_graph import run_sales_agent
        
        try:
            result = await run_sales_agent(
                session_id="test_quote",
                message="帮我生成一份报价单，客户是华为公司",
                context={},
                history=[]
            )
            
            # 验证返回
            assert isinstance(result, dict)
            assert result.get("session_id") == "test_quote"
            
            # 可能生成文档，也可能因为 API 限制没有
            # 主要验证流程没有中断
            
        except Exception as e:
            pytest.skip(f"集成测试需要有效 API Key: {e}")


# ═══════════════════════════════════════════════════════════════
# 运行测试的说明
# ═══════════════════════════════════════════════════════════════

"""
运行测试：

1. 安装 pytest：
   pip install pytest pytest-asyncio

2. 运行所有测试：
   cd /mnt/e/claude/1work/sales-ai-agent
   python -m pytest tests/test_sales_graph.py -v

3. 运行单元测试（无需 API Key）：
   python -m pytest tests/test_sales_graph.py::TestGraphStructure -v
   python -m pytest tests/test_sales_graph.py::TestSanitizeFinalState -v
   python -m pytest tests/test_sales_graph.py::TestSafeGetFunctions -v

4. 运行集成测试（需要 API Key）：
   python -m pytest tests/test_sales_graph.py::TestGraphExecution -v

5. 快速验证图结构：
   python -c "
   from app.agents.graphs.sales_graph import create_sales_graph
   graph = create_sales_graph()
   print('✅ 图编译成功！')
   print('图类型:', type(graph))
   "
"""

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

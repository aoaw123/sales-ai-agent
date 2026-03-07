"""
intent_node 重构测试

测试要点：
1. 三层 JSON 回退解析（标准 → Markdown → 正则）
2. Pydantic 兜底（解析失败返回默认意图）
3. 状态字典净化（不放入 missing_params）
4. LLM 调用失败有兜底
"""

import pytest
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.nodes.intent_node import (
    safe_parse_json,
    parse_intent_from_dict,
    _fallback_keyword_intent,
    _extract_entities_from_message,
    determine_next_node,
    DEFAULT_INTENT_ANALYSIS,
    INTENT_PROMPT,
)
from app.models.chat import UserIntent, IntentAnalysisResult


class TestSafeParseJson:
    """测试三层 JSON 回退解析"""
    
    def test_standard_json(self):
        """测试标准 JSON 解析"""
        raw = '{"intent": "quote_generation", "confidence": 0.95, "entities": {}}'
        result = safe_parse_json(raw)
        assert result == {"intent": "quote_generation", "confidence": 0.95, "entities": {}}
    
    def test_markdown_code_block_json(self):
        """测试 Markdown 代码块解析"""
        raw = '''```json
{
    "intent": "product_inquiry",
    "confidence": 0.88,
    "entities": {"product_name": "至尊钻石版"}
}
```'''
        result = safe_parse_json(raw)
        assert result["intent"] == "product_inquiry"
        assert result["confidence"] == 0.88
        assert result["entities"]["product_name"] == "至尊钻石版"
    
    def test_markdown_no_language_json(self):
        """测试无语言标记的 Markdown 代码块"""
        raw = '''```
{
    "intent": "general_chat",
    "confidence": 0.75
}
```'''
        result = safe_parse_json(raw)
        assert result["intent"] == "general_chat"
    
    def test_bare_json_in_text(self):
        """测试夹杂在废话中的 JSON"""
        raw = '好的，我来分析您的意图。\n\n{"intent": "quote_generation", "confidence": 0.92, "entities": {}}\n\n希望这能帮到您！'
        result = safe_parse_json(raw)
        assert result["intent"] == "quote_generation"
    
    def test_nested_json_extraction(self):
        """测试嵌套结构的 JSON 提取"""
        raw = '分析结果：{"intent": "proposal_creation", "confidence": 0.85, "entities": {"customer_name": "华为"}, "reasoning": "用户提到方案"}'
        result = safe_parse_json(raw)
        assert result["intent"] == "proposal_creation"
        assert result["entities"]["customer_name"] == "华为"
    
    def test_invalid_json_returns_empty(self):
        """测试无效 JSON 返回空字典"""
        raw = "这不是有效的 JSON"
        result = safe_parse_json(raw)
        assert result == {}
    
    def test_empty_input(self):
        """测试空输入"""
        assert safe_parse_json("") == {}
        assert safe_parse_json(None) == {}
        assert safe_parse_json(123) == {}  # 非字符串
    
    def test_malformed_json_partial_recovery(self):
        """测试部分损坏的 JSON"""
        raw = '{"intent": "quote_generation", "confidence": 0.9, "entities": {invalid}}'
        result = safe_parse_json(raw)
        # 应该返回空字典或尽可能解析的部分
        assert isinstance(result, dict)


class TestParseIntentFromDict:
    """测试字典到 Pydantic 模型的解析"""
    
    def test_valid_dict(self):
        """测试有效字典解析"""
        data = {
            "intent": "quote_generation",
            "confidence": 0.95,
            "entities": {"customer_name": "测试公司"},
            "reasoning": "用户要求报价"
        }
        result = parse_intent_from_dict(data)
        
        assert result.intent == UserIntent.QUOTE_GENERATION
        assert result.confidence == 0.95
        assert result.entities["customer_name"] == "测试公司"
        assert result.reasoning == "用户要求报价"
    
    def test_missing_fields_use_defaults(self):
        """测试缺失字段使用默认值"""
        data = {"intent": "product_inquiry"}  # 缺少 confidence, entities, reasoning
        result = parse_intent_from_dict(data)
        
        assert result.intent == UserIntent.PRODUCT_INQUIRY
        assert result.confidence == 0.5  # 默认值
        assert result.entities == {}  # 默认空字典
        assert result.reasoning == ""  # 默认空字符串
    
    def test_invalid_intent_uses_fallback(self):
        """测试无效 intent 使用回退匹配"""
        data = {
            "intent": "invalid_intent_name",
            "entities": {"报价": "something"}  # 含有报价关键词
        }
        result = parse_intent_from_dict(data)
        
        # 应该回退到 quote_generation（因为 entities 中有"报价"关键词）
        assert result.intent == UserIntent.QUOTE_GENERATION
    
    def test_confidence_out_of_range_clamped(self):
        """测试 confidence 越界被限制在 0-1"""
        data_high = {"intent": "general_chat", "confidence": 1.5}
        result_high = parse_intent_from_dict(data_high)
        assert result_high.confidence == 1.0
        
        data_low = {"intent": "general_chat", "confidence": -0.5}
        result_low = parse_intent_from_dict(data_low)
        assert result_low.confidence == 0.0
    
    def test_non_dict_input_returns_default(self):
        """测试非字典输入返回默认意图"""
        result = parse_intent_from_dict("not a dict")
        assert result == DEFAULT_INTENT_ANALYSIS
        
        result = parse_intent_from_dict(None)
        assert result == DEFAULT_INTENT_ANALYSIS
    
    def test_entities_not_dict(self):
        """测试 entities 非字典类型"""
        data = {
            "intent": "general_chat",
            "entities": "invalid_entities"
        }
        result = parse_intent_from_dict(data)
        assert result.entities == {}


class TestFallbackKeywordIntent:
    """测试关键词回退意图识别"""
    
    def test_quote_keywords(self):
        """测试报价关键词"""
        result = _fallback_keyword_intent("我要一份报价单，多少钱？")
        assert result.intent == UserIntent.QUOTE_GENERATION
        assert result.confidence > 0.5
    
    def test_product_inquiry_keywords(self):
        """测试产品咨询关键词"""
        result = _fallback_keyword_intent("你们产品有什么功能？")
        assert result.intent == UserIntent.PRODUCT_INQUIRY
    
    def test_contract_keywords(self):
        """测试合同关键词"""
        result = _fallback_keyword_intent("请起草一份合同")
        assert result.intent == UserIntent.CONTRACT_DRAFTING
    
    def test_complaint_keywords(self):
        """测试投诉关键词"""
        result = _fallback_keyword_intent("我要投诉，服务太差了")
        assert result.intent == UserIntent.COMPLAINT_HANDLING
    
    def test_no_match_defaults_to_general_chat(self):
        """测试无匹配默认为 general_chat"""
        result = _fallback_keyword_intent("今天天气怎么样")
        assert result.intent == UserIntent.GENERAL_CHAT
    
    def test_reasoning_includes_match_count(self):
        """测试 reasoning 包含匹配数量"""
        result = _fallback_keyword_intent("报价 价格 多少钱")
        assert "匹配" in result.reasoning


class TestExtractEntitiesFromMessage:
    """测试从消息中提取实体"""
    
    def test_extract_customer_name(self):
        """测试提取客户名称"""
        context = {}
        context = _extract_entities_from_message(context, "我是华为公司的，想咨询产品")
        assert context.get("customer_name") == "华为"
    
    def test_extract_product_name(self):
        """测试提取产品名称"""
        context = {}
        context = _extract_entities_from_message(context, "至尊钻石版有什么功能")
        assert context.get("product_name") == "至尊钻石版"
    
    def test_extract_amount_wan(self):
        """测试提取金额（万元）"""
        context = {}
        context = _extract_entities_from_message(context, "预算大概10万元左右")
        assert context.get("amount") == 10.0
    
    def test_extract_amount_yuan(self):
        """测试提取金额（元）"""
        context = {}
        context = _extract_entities_from_message(context, "价格是5000元")
        assert context.get("amount") == 5000.0
    
    def test_extract_quantity(self):
        """测试提取数量"""
        context = {}
        context = _extract_entities_from_message(context, "需要5套系统")
        assert context.get("quantity") == 5
    
    def test_preserve_existing_context(self):
        """测试保留已有 context 值"""
        context = {"customer_name": "已有公司", "other_key": "value"}
        context = _extract_entities_from_message(context, "我是新公司的")
        # 已有值不应被覆盖（因为提取逻辑检查 not context.get）
        assert context.get("customer_name") == "已有公司"
        assert context.get("other_key") == "value"


class TestDetermineNextNode:
    """测试路由决策"""
    
    def test_product_inquiry_routes_to_knowledge(self):
        """测试产品咨询路由到知识库"""
        result = determine_next_node(UserIntent.PRODUCT_INQUIRY)
        assert result == "knowledge_retrieval"
    
    def test_quote_generation_routes_to_document_params(self):
        """测试报价单路由到文档参数提取"""
        result = determine_next_node(UserIntent.QUOTE_GENERATION)
        assert result == "extract_document_params"
    
    def test_proposal_creation_routes_to_document_params(self):
        """测试提案书路由到文档参数提取"""
        result = determine_next_node(UserIntent.PROPOSAL_CREATION)
        assert result == "extract_document_params"
    
    def test_contract_drafting_routes_to_document_params(self):
        """测试合同路由到文档参数提取"""
        result = determine_next_node(UserIntent.CONTRACT_DRAFTING)
        assert result == "extract_document_params"
    
    def test_price_negotiation_routes_to_sales(self):
        """测试价格谈判路由到销售话术"""
        result = determine_next_node(UserIntent.PRICE_NEGOTIATION)
        assert result == "sales_negotiation"
    
    def test_general_chat_routes_to_response(self):
        """测试闲聊路由到直接响应"""
        result = determine_next_node(UserIntent.GENERAL_CHAT)
        assert result == "sales_response"
    
    def test_unknown_intent_defaults_to_response(self):
        """测试未知意图默认到直接响应"""
        result = determine_next_node(UserIntent.UNKNOWN)
        assert result == "sales_response"


class TestDefaultIntentAnalysis:
    """测试默认意图配置"""
    
    def test_default_values(self):
        """测试默认值"""
        assert DEFAULT_INTENT_ANALYSIS.intent == UserIntent.GENERAL_CHAT
        assert DEFAULT_INTENT_ANALYSIS.confidence == 0.5
        assert DEFAULT_INTENT_ANALYSIS.entities == {}
        assert DEFAULT_INTENT_ANALYSIS.reasoning == "解析失败，使用默认意图"


class TestIntentPrompt:
    """测试 Intent Prompt 内容"""
    
    def test_prompt_contains_all_intents(self):
        """测试 Prompt 包含所有意图类型"""
        assert "general_chat" in INTENT_PROMPT
        assert "quote_generation" in INTENT_PROMPT
        assert "product_inquiry" in INTENT_PROMPT
        assert "contract_drafting" in INTENT_PROMPT
    
    def test_prompt_contains_json_format(self):
        """测试 Prompt 包含 JSON 格式说明"""
        assert "intent" in INTENT_PROMPT
        assert "confidence" in INTENT_PROMPT
        assert "entities" in INTENT_PROMPT


# ═══════════════════════════════════════════════════════════════
# 集成测试（需要部分环境）
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestIntentRecognitionNode:
    """测试完整的意图识别节点"""
    
    async def test_node_with_empty_state(self):
        """测试空 state 处理"""
        from app.agents.nodes.intent_node import intent_recognition_node
        
        state = {
            "session_id": "test_session",
            "messages": [],
            "context": {},
        }
        
        result = await intent_recognition_node(state)
        
        # 验证返回结构
        assert "intent_analysis" in result
        assert "next_node" in result
        assert result["next_node"] == "sales_response"  # 空消息应该路由到直接响应
    
    async def test_node_with_message(self):
        """测试带消息的节点"""
        from app.agents.nodes.intent_node import intent_recognition_node
        from langchain_core.messages import HumanMessage
        
        state = {
            "session_id": "test_session",
            "messages": [HumanMessage(content="生成一份报价单")],
            "context": {},
        }
        
        result = await intent_recognition_node(state)
        
        # 验证返回结构
        assert "intent_analysis" in result
        assert "next_node" in result
        assert isinstance(result["intent_analysis"], IntentAnalysisResult)
        
        # 如果成功解析，应该路由到文档参数提取
        # 注意：实际路由取决于 LLM 返回或关键词回退
        assert result["next_node"] in ["extract_document_params", "sales_response"]


# ═══════════════════════════════════════════════════════════════
# 运行测试的说明
# ═══════════════════════════════════════════════════════════════

"""
运行测试：

1. 安装 pytest：
   pip install pytest pytest-asyncio

2. 运行所有测试：
   cd /mnt/e/claude/1work/sales-ai-agent
   python -m pytest tests/test_intent_node.py -v

3. 运行特定测试类：
   python -m pytest tests/test_intent_node.py::TestSafeParseJson -v
   python -m pytest tests/test_intent_node.py::TestParseIntentFromDict -v

4. 运行集成测试（需要 API Key）：
   python -m pytest tests/test_intent_node.py::TestIntentRecognitionNode -v

5. 查看测试覆盖率：
   pip install pytest-cov
   python -m pytest tests/test_intent_node.py --cov=app.agents.nodes.intent_node -v
"""

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

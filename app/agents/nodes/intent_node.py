"""
意图识别节点 - 分析用户输入，确定销售场景

这是工作流的第一个节点，决定了后续的执行路径。
"""

import json
from typing import Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.agents.state import SalesState
from app.models.chat import IntentAnalysisResult, UserIntent

logger = get_logger("intent_node")


INTENT_PROMPT = """你是一个专业的销售 AI 助手，负责分析客户的意图。

请仔细分析用户的消息，识别其意图类别，并提取关键实体信息。

可选的意图类别：
- general_chat: 普通闲聊（问候、感谢、告别等）
- product_inquiry: 产品咨询（询问产品功能、规格、适用场景等）
- price_negotiation: 价格谈判（询问价格、要求折扣、比较价格等）
- document_request: 请求生成文档（未明确具体类型）
- quote_generation: 生成报价单（明确提到报价、报价单、价格清单）
- proposal_creation: 创建提案书/方案（提到方案、提案、项目建议书）
- contract_drafting: 起草合同（提到合同、协议、条款）
- data_analysis: 数据分析/报表（提到报表、分析、数据统计）
- presentation_request: 请求演示文稿（提到PPT、演示、幻灯片、pitch）
- complaint_handling: 投诉处理（表达不满、投诉、退款要求）
- follow_up: 跟进提醒（询问进度、催促回复）
- unknown: 无法识别的意图

请输出 JSON 格式：
{
    "intent": "意图类别",
    "confidence": 0.95,
    "entities": {
        "customer_name": "客户名称（如有）",
        "product_name": "产品名称（如有）",
        "amount": "金额数字（如有）",
        "deadline": "时间期限（如有）",
        ...其他提取的实体
    },
    "reasoning": "简要的推理过程"
}

注意：
1. confidence 必须在 0-1 之间
2. 如果用户消息涉及生成文档，请尽可能识别具体文档类型
3. 提取所有可能有用的实体信息"""


async def intent_recognition_node(state: SalesState) -> SalesState:
    """
    意图识别节点
    
    使用 LLM 分析用户消息，识别销售场景意图。
    """
    logger.info(f"[Session: {state['session_id']}] 开始意图识别")
    
    try:
        # 初始化 LLM
        llm = ChatOpenAI(
            model=settings.default_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.2,  # 低温度以获得更确定的结果
        )
        
        # 获取最后一条用户消息
        user_message = state["messages"][-1].content if state["messages"] else ""
        
        # 构建消息
        messages = [
            SystemMessage(content=INTENT_PROMPT),
            HumanMessage(content=f"请分析以下客户消息：\n\n{user_message}")
        ]
        
        # 调用 LLM
        response = await llm.ainvoke(messages)
        
        # 解析 JSON 响应
        try:
            result = json.loads(response.content)
            intent_analysis = IntentAnalysisResult(
                intent=UserIntent(result.get("intent", "unknown")),
                confidence=result.get("confidence", 0.5),
                entities=result.get("entities", {}),
                reasoning=result.get("reasoning", "")
            )
        except json.JSONDecodeError:
            # 如果 LLM 没有返回有效的 JSON，进行回退处理
            logger.warning("LLM 返回非 JSON 格式，使用回退解析")
            intent_analysis = _fallback_intent_parsing(response.content, user_message)
        
        logger.info(f"意图识别结果: {intent_analysis.intent.value}, 置信度: {intent_analysis.confidence}")
        
        # 更新状态
        state["intent_analysis"] = intent_analysis
        
        # 根据意图决定下一个节点
        state["next_node"] = _determine_next_node(intent_analysis.intent)
        
        return state
        
    except Exception as e:
        logger.error(f"意图识别失败: {str(e)}")
        state["error"] = f"意图识别失败: {str(e)}"
        state["intent_analysis"] = IntentAnalysisResult(
            intent=UserIntent.UNKNOWN,
            confidence=0.0,
            entities={},
            reasoning="识别过程发生错误"
        )
        state["next_node"] = "sales_response"
        return state


def _fallback_intent_parsing(raw_response: str, user_message: str) -> IntentAnalysisResult:
    """
    回退意图解析 - 当 LLM 不返回 JSON 时使用
    
    使用关键词匹配进行简单的意图识别。
    """
    message_lower = user_message.lower()
    raw_lower = raw_response.lower()
    combined = message_lower + " " + raw_lower
    
    # 关键词映射
    intent_keywords = {
        UserIntent.QUOTE_GENERATION: ["报价", "报价单", "价格清单", "quotation", "quote"],
        UserIntent.PROPOSAL_CREATION: ["提案", "方案", "建议书", "proposal", "方案书"],
        UserIntent.CONTRACT_DRAFTING: ["合同", "协议", "contract", "agreement"],
        UserIntent.PRESENTATION_REQUEST: ["ppt", "演示", "幻灯片", "presentation", "pitch"],
        UserIntent.DATA_ANALYSIS: ["报表", "分析", "统计", "excel", "数据"],
        UserIntent.PRICE_NEGOTIATION: ["折扣", "优惠", "便宜", "降价", "价格太贵"],
        UserIntent.COMPLAINT_HANDLING: ["投诉", "不满意", "退款", "问题", "糟糕"],
        UserIntent.PRODUCT_INQUIRY: ["产品", "功能", "怎么用", "规格", "介绍"],
    }
    
    # 匹配意图
    best_intent = UserIntent.GENERAL_CHAT
    max_matches = 0
    
    for intent, keywords in intent_keywords.items():
        matches = sum(1 for kw in keywords if kw in combined)
        if matches > max_matches:
            max_matches = matches
            best_intent = intent
    
    # 计算置信度
    confidence = min(0.5 + max_matches * 0.1, 0.8)
    
    return IntentAnalysisResult(
        intent=best_intent,
        confidence=confidence,
        entities={},
        reasoning=f"基于关键词匹配 ({max_matches} 个匹配)"
    )


def _determine_next_node(intent: UserIntent) -> str:
    """
    根据意图决定下一个节点
    
    路由规则：
    - 产品咨询 -> 知识库检索
    - 文档相关 -> 参数提取
    - 价格谈判 -> 销售话术
    - 其他 -> 直接响应
    """
    routing_map = {
        UserIntent.PRODUCT_INQUIRY: "knowledge_retrieval",
        UserIntent.QUOTE_GENERATION: "extract_document_params",
        UserIntent.PROPOSAL_CREATION: "extract_document_params",
        UserIntent.CONTRACT_DRAFTING: "extract_document_params",
        UserIntent.DATA_ANALYSIS: "extract_document_params",
        UserIntent.PRESENTATION_REQUEST: "extract_document_params",
        UserIntent.PRICE_NEGOTIATION: "sales_negotiation",
        UserIntent.COMPLAINT_HANDLING: "complaint_handler",
        UserIntent.DOCUMENT_REQUEST: "clarify_document_type",
    }
    
    return routing_map.get(intent, "sales_response")

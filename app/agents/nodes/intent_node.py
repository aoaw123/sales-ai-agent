"""
意图识别节点 - 分析用户输入，确定销售场景

重构要点：
1. 三层 JSON 回退解析（标准 → Markdown代码块 → 正则提取）
2. Pydantic 兜底：任何解析失败返回默认意图，绝不 500
3. 状态字典净化：不放入 missing_params，下游节点直接赋默认值
4. 防御性编程：LLM 调用失败有兜底，空消息有处理
"""

import json
import re
from typing import Dict, Any, Optional

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.agents.state import SalesState
from app.models.chat import IntentAnalysisResult, UserIntent

logger = get_logger("intent_node")


# ═══════════════════════════════════════════════════════════════
# 默认意图配置（Pydantic 兜底用）
# ═══════════════════════════════════════════════════════════════

DEFAULT_INTENT_ANALYSIS = IntentAnalysisResult(
    intent=UserIntent.GENERAL_CHAT,
    confidence=0.5,
    entities={},
    reasoning="解析失败，使用默认意图"
)


# ═══════════════════════════════════════════════════════════════
# 三层 JSON 回退解析（核心防御机制）
# ═══════════════════════════════════════════════════════════════

def safe_parse_json(raw_text: str) -> Dict[str, Any]:
    """
    三层 JSON 回退解析函数
    
    无论 LLM 返回什么格式，都尝试提取有效 JSON：
    1. 标准 JSON 解析
    2. Markdown 代码块提取（```json ... ```）
    3. 裸 JSON 对象正则提取
    4. 兜底返回默认结构
    
    Args:
        raw_text: LLM 返回的原始文本
        
    Returns:
        解析后的字典（绝不抛异常）
    """
    if not raw_text or not isinstance(raw_text, str):
        logger.warning("[JSON Parse] 输入为空或非字符串")
        return {}
    
    raw_text = raw_text.strip()
    if not raw_text:
        return {}
    
    # ═══ 第一层：标准 JSON 解析 ═══
    try:
        result = json.loads(raw_text)
        if isinstance(result, dict):
            logger.debug("[JSON Parse] 标准解析成功")
            return result
    except json.JSONDecodeError:
        pass
    
    # ═══ 第二层：Markdown 代码块提取 ═══
    # 匹配 ```json ... ``` 或 ``` ... ```
    md_patterns = [
        r'```json\s*(.*?)\s*```',  # 带 json 标记
        r'```\s*(.*?)\s*```',       # 无语言标记
    ]
    
    for pattern in md_patterns:
        matches = re.findall(pattern, raw_text, re.DOTALL | re.IGNORECASE)
        for match in matches:
            try:
                result = json.loads(match.strip())
                if isinstance(result, dict):
                    logger.debug(f"[JSON Parse] Markdown代码块解析成功 (pattern: {pattern[:20]}...)")
                    return result
            except json.JSONDecodeError:
                continue
    
    # ═══ 第三层：裸 JSON 对象正则提取 ═══
    # 匹配最外层的大括号结构（支持嵌套）
    # 使用非贪婪匹配，但要处理嵌套情况
    json_patterns = [
        # 匹配 { ... }，支持嵌套一层
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
        # 更宽松的模式：从第一个 { 到最后一个 }
        r'\{.*\}',
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, raw_text, re.DOTALL)
        # 按长度降序，优先尝试更长的匹配（更可能是完整 JSON）
        matches.sort(key=len, reverse=True)
        
        for match in matches:
            try:
                result = json.loads(match.strip())
                if isinstance(result, dict):
                    logger.debug(f"[JSON Parse] 正则提取成功 (长度: {len(match)})")
                    return result
            except json.JSONDecodeError:
                continue
    
    # ═══ 兜底：返回空字典 ═══
    logger.warning(f"[JSON Parse] 所有解析方式失败，返回空字典。原始文本前100字符: {raw_text[:100]}...")
    return {}


def parse_intent_from_dict(data: Dict[str, Any]) -> IntentAnalysisResult:
    """
    将字典解析为 IntentAnalysisResult
    
    防御性处理：
    - 字段缺失使用默认值
    - 类型错误使用默认值
    - 无效枚举值使用默认值
    
    Args:
        data: 解析后的字典
        
    Returns:
        IntentAnalysisResult（绝不抛异常）
    """
    if not isinstance(data, dict):
        logger.warning(f"[Intent Parse] 输入非字典: {type(data)}")
        return DEFAULT_INTENT_ANALYSIS
    
    try:
        # 提取 intent（防御性）
        intent_raw = data.get("intent", "general_chat")
        intent_str = str(intent_raw).lower().strip() if intent_raw else "general_chat"
        
        # 验证 intent 是否在枚举中
        try:
            intent = UserIntent(intent_str)
        except ValueError:
            # 无效的 intent 值，使用关键词回退匹配
            intent = _fallback_intent_matching(intent_str, data)
        
        # 提取 confidence（防御性）
        confidence_raw = data.get("confidence", 0.5)
        try:
            confidence = float(confidence_raw)
            confidence = max(0.0, min(1.0, confidence))  # 限制在 0-1 范围
        except (ValueError, TypeError):
            confidence = 0.5
        
        # 提取 entities（防御性）
        entities_raw = data.get("entities", {})
        if isinstance(entities_raw, dict):
            entities = entities_raw
        else:
            entities = {}
        
        # 提取 reasoning（防御性）
        reasoning_raw = data.get("reasoning", "")
        reasoning = str(reasoning_raw) if reasoning_raw else ""
        
        return IntentAnalysisResult(
            intent=intent,
            confidence=confidence,
            entities=entities,
            reasoning=reasoning
        )
        
    except Exception as e:
        logger.error(f"[Intent Parse] 解析异常: {e}")
        return DEFAULT_INTENT_ANALYSIS


def _fallback_intent_matching(intent_str: str, data: Dict) -> UserIntent:
    """
    意图回退匹配 - 当 LLM 返回的 intent 不在枚举中时
    
    使用关键词匹配进行兜底
    """
    intent_keywords = {
        UserIntent.QUOTE_GENERATION: ["报价", "quotation", "quote", "价格清单", "报价单"],
        UserIntent.PROPOSAL_CREATION: ["提案", "proposal", "方案", "建议书", "项目建议"],
        UserIntent.CONTRACT_DRAFTING: ["合同", "contract", "协议", "agreement", "条款"],
        UserIntent.PRESENTATION_REQUEST: ["ppt", "演示", "presentation", "幻灯片", "pitch", "讲演"],
        UserIntent.DATA_ANALYSIS: ["报表", "分析", "统计", "excel", "数据", "analytics"],
        UserIntent.PRICE_NEGOTIATION: ["折扣", "优惠", "便宜", "降价", "价格太贵", "negotiation"],
        UserIntent.COMPLAINT_HANDLING: ["投诉", "不满意", "退款", "complaint", "糟糕", "问题"],
        UserIntent.PRODUCT_INQUIRY: ["产品", "功能", "怎么用", "规格", "介绍", "inquiry"],
        UserIntent.FOLLOW_UP: ["跟进", "进度", "催促", "follow", "status"],
        UserIntent.GENERAL_CHAT: ["聊天", "问候", "你好", "chat", "hello", "hi"],
    }
    
    combined_text = intent_str.lower()
    
    # 检查 entities 中是否有线索
    entities = data.get("entities", {})
    if isinstance(entities, dict):
        for key in entities.keys():
            combined_text += " " + str(key).lower()
    
    best_intent = UserIntent.GENERAL_CHAT
    max_matches = 0
    
    for intent, keywords in intent_keywords.items():
        matches = sum(1 for kw in keywords if kw in combined_text)
        if matches > max_matches:
            max_matches = matches
            best_intent = intent
    
    logger.debug(f"[Intent Fallback] 关键词匹配: {intent_str} -> {best_intent.value} ({max_matches} 个匹配)")
    return best_intent


# ═══════════════════════════════════════════════════════════════
# 意图识别 Prompt
# ═══════════════════════════════════════════════════════════════

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

请输出 JSON 格式（不要添加 Markdown 标记，直接输出纯 JSON）：
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
3. 提取所有可能有用的实体信息
4. 直接输出 JSON，不要添加 ```json 标记"""


# ═══════════════════════════════════════════════════════════════
# 路由决策函数
# ═══════════════════════════════════════════════════════════════

def determine_next_node(intent: UserIntent) -> str:
    """
    根据意图决定下一个节点
    
    路由规则：
    - 产品咨询 -> 知识库检索
    - 文档相关 -> 文档生成参数提取（强制跳过询问，下游赋默认值）
    - 价格谈判 -> 销售话术
    - 其他 -> 直接响应
    
    Args:
        intent: 识别到的用户意图
        
    Returns:
        下一个节点名称
    """
    routing_map = {
        UserIntent.PRODUCT_INQUIRY: "knowledge_retrieval",
        UserIntent.QUOTE_GENERATION: "extract_document_params",
        UserIntent.PROPOSAL_CREATION: "extract_document_params",
        UserIntent.CONTRACT_DRAFTING: "extract_document_params",
        UserIntent.DATA_ANALYSIS: "extract_document_params",
        UserIntent.PRESENTATION_REQUEST: "extract_document_params",
        UserIntent.DOCUMENT_REQUEST: "extract_document_params",
        UserIntent.PRICE_NEGOTIATION: "sales_negotiation",
        UserIntent.COMPLAINT_HANDLING: "complaint_handler",
    }
    
    next_node = routing_map.get(intent, "sales_response")
    logger.info(f"[Routing] 意图 {intent.value} -> 节点 {next_node}")
    return next_node


# ═══════════════════════════════════════════════════════════════
# LangGraph 节点函数
# ═══════════════════════════════════════════════════════════════

async def intent_recognition_node(state: SalesState) -> SalesState:
    """
    意图识别节点 - 防御性增强版
    
    核心流程：
    1. 获取用户消息（防御性处理空消息）
    2. 调用 LLM 进行意图识别
    3. 三层 JSON 解析
    4. Pydantic 验证 + 兜底
    5. 输出纯净 State（含 next_node 路由决策）
    
    保证：
    - 绝不抛出异常
    - 返回的 State 总是有效字典
    - intent_analysis 总是 IntentAnalysisResult 类型
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[Session: {session_id}] 开始意图识别")
    
    # ═══ 防御性：获取用户消息 ═══
    user_message = ""
    try:
        messages = state.get("messages", [])
        if messages and isinstance(messages, list):
            last_message = messages[-1]
            if hasattr(last_message, 'content'):
                user_message = last_message.content or ""
            elif isinstance(last_message, dict):
                user_message = last_message.get('content', '')
            else:
                user_message = str(last_message)
    except Exception as e:
        logger.warning(f"[Intent] 获取用户消息失败: {e}")
        user_message = ""
    
    user_message = user_message.strip() if user_message else ""
    
    # 空消息处理
    if not user_message:
        logger.warning("[Intent] 用户消息为空，使用默认意图")
        state["intent_analysis"] = DEFAULT_INTENT_ANALYSIS
        state["next_node"] = "sales_response"
        state["context"] = state.get("context", {})
        return state
    
    # ═══ 调用 LLM 进行意图识别 ═══
    try:
        llm = ChatOpenAI(
            model=settings.default_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.2,  # 低温度以获得更确定的结果
        )
        
        messages = [
            SystemMessage(content=INTENT_PROMPT),
            HumanMessage(content=f"请分析以下客户消息：\n\n{user_message}")
        ]
        
        response = await llm.ainvoke(messages)
        raw_response = response.content if hasattr(response, 'content') else str(response)
        
        logger.debug(f"[Intent] LLM 原始响应: {raw_response[:200]}...")
        
    except Exception as e:
        logger.error(f"[Intent] LLM 调用失败: {e}")
        # LLM 调用失败，使用兜底解析
        state["intent_analysis"] = _fallback_keyword_intent(user_message)
        state["next_node"] = determine_next_node(state["intent_analysis"].intent)
        state["context"] = _extract_entities_from_message(state.get("context", {}), user_message)
        return state
    
    # ═══ 三层 JSON 解析 ═══
    parsed_dict = safe_parse_json(raw_response)
    
    # ═══ Pydantic 验证（带兜底）═══
    if parsed_dict:
        intent_analysis = parse_intent_from_dict(parsed_dict)
    else:
        # 解析彻底失败，使用关键词回退
        intent_analysis = _fallback_keyword_intent(user_message)
    
    logger.info(f"[Intent] 识别结果: {intent_analysis.intent.value}, 置信度: {intent_analysis.confidence:.2f}")
    
    # ═══ 提取实体到 context（纯净字典）═══
    context = state.get("context", {})
    if not isinstance(context, dict):
        context = {}
    
    # 合并识别到的实体
    if intent_analysis.entities and isinstance(intent_analysis.entities, dict):
        context.update(intent_analysis.entities)
    
    # 额外提取：从消息中提取可能的客户名、产品名等
    context = _extract_entities_from_message(context, user_message)
    
    # ═══ 组装输出 State（纯净字典）═══
    state["intent_analysis"] = intent_analysis
    state["context"] = context
    state["next_node"] = determine_next_node(intent_analysis.intent)
    
    # 确保 metadata 存在
    if "metadata" not in state or not isinstance(state["metadata"], dict):
        state["metadata"] = {}
    
    # 记录调试信息
    state["metadata"]["intent_recognition"] = {
        "raw_response_preview": raw_response[:200] if len(raw_response) > 200 else raw_response,
        "parsed_success": bool(parsed_dict),
        "confidence": intent_analysis.confidence,
    }
    
    return state


def _fallback_keyword_intent(user_message: str) -> IntentAnalysisResult:
    """
    关键词回退意图识别 - 当 LLM 完全失败时使用
    """
    message_lower = user_message.lower()
    
    intent_keywords = {
        UserIntent.QUOTE_GENERATION: ["报价", "报价单", "价格清单", "quotation", "quote", "多少钱", "费用"],
        UserIntent.PROPOSAL_CREATION: ["提案", "方案", "建议书", "proposal", "项目建议", "解决方案"],
        UserIntent.CONTRACT_DRAFTING: ["合同", "协议", "contract", "agreement", "条款", "签约"],
        UserIntent.PRESENTATION_REQUEST: ["ppt", "演示", "幻灯片", "presentation", "pitch", "讲演", "汇报"],
        UserIntent.DATA_ANALYSIS: ["报表", "分析", "统计", "excel", "数据", "analytics", "报表"],
        UserIntent.PRICE_NEGOTIATION: ["折扣", "优惠", "便宜", "降价", "价格太贵", "negotiation", "能不能便宜"],
        UserIntent.COMPLAINT_HANDLING: ["投诉", "不满意", "退款", "complaint", "糟糕", "问题", "差评"],
        UserIntent.PRODUCT_INQUIRY: ["产品", "功能", "怎么用", "规格", "介绍", "inquiry", "有什么功能"],
        UserIntent.FOLLOW_UP: ["跟进", "进度", "催促", "follow", "status", "怎么样了"],
    }
    
    best_intent = UserIntent.GENERAL_CHAT
    max_matches = 0
    
    for intent, keywords in intent_keywords.items():
        matches = sum(1 for kw in keywords if kw in message_lower)
        if matches > max_matches:
            max_matches = matches
            best_intent = intent
    
    confidence = min(0.5 + max_matches * 0.1, 0.7)
    
    logger.info(f"[Intent Fallback] 关键词匹配: {best_intent.value} (置信度: {confidence:.2f})")
    
    return IntentAnalysisResult(
        intent=best_intent,
        confidence=confidence,
        entities={},
        reasoning=f"基于关键词回退匹配 ({max_matches} 个匹配)"
    )


def _extract_entities_from_message(context: Dict[str, Any], user_message: str) -> Dict[str, Any]:
    """
    从用户消息中直接提取实体信息
    
    作为 LLM 实体提取的补充/兜底
    """
    if not isinstance(context, dict):
        context = {}
    
    message = user_message.lower()
    
    # 提取客户名称（常见的"我是XX"、"XX公司"等模式）
    if "customer_name" not in context or not context["customer_name"]:
        # 尝试匹配 "我是XX"、"XX公司的"
        name_patterns = [
            r'我是(\S+?)(?:的|公司|先生|女士|$)',
            r'(\S+?)(?:公司|集团|科技|网络)(?:的|需要|想|请)',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, message)
            if match:
                context["customer_name"] = match.group(1).strip()
                break
    
    # 提取产品名称
    if "product_name" not in context or not context["product_name"]:
        product_keywords = ["至尊钻石版", "ai服务", "获客服务", "数据安全网关"]
        for kw in product_keywords:
            if kw in message:
                context["product_name"] = kw
                break
    
    # 提取金额数字
    if "amount" not in context or not context["amount"]:
        # 匹配 XX元、XX万元等
        amount_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:万元|万)',
            r'(\d+(?:\.\d+)?)\s*(?:元|块)',
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, message)
            if match:
                try:
                    amount = float(match.group(1))
                    context["amount"] = amount
                    break
                except ValueError:
                    pass
    
    # 提取数量
    if "quantity" not in context or not context["quantity"]:
        qty_pattern = r'(\d+)\s*(?:个|套|份|台|件)'
        match = re.search(qty_pattern, message)
        if match:
            try:
                context["quantity"] = int(match.group(1))
            except ValueError:
                pass
    
    return context


# ═══════════════════════════════════════════════════════════════
# 兼容导出（旧代码可能依赖的函数）
# ═══════════════════════════════════════════════════════════════

# 保留旧函数名兼容性
_fallback_intent_parsing = _fallback_keyword_intent
_determine_next_node = determine_next_node

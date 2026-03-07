"""
销售回复节点 - 生成最终回复内容（重构版）

这是工作流的最后一个节点，负责整合所有信息生成最终回复。
防御性设计：无论前面节点输出什么，都生成有效的回复。
"""

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.agents.state import SalesState
from app.models.chat import UserIntent

logger = get_logger("response_node")


# 销售话术系统提示
SALES_RESPONSE_PROMPT = """你是「智销云」的智能销售助手，专门为销售团队提供高效、专业的客户沟通支持。

## 你的角色定位
- 专业的销售顾问，熟悉产品知识和销售技巧
- 高效的文档助手，能快速生成报价单、提案书、合同等
- 耐心的沟通者，善于倾听客户需求并提供解决方案

## 回复原则

1. **专业友好**
   - 使用礼貌、积极的语气
   - 避免过于生硬的技术术语
   - 展现专业性和可信度

2. **简洁明了**
   - 直接回答客户问题
   - 避免冗长的铺垫
   - 重点信息突出

3. **行动导向**
   - 每次回复都包含下一步建议
   - 引导客户向成交推进
   - 提供具体的行动选项

4. **个性化**
   - 根据客户上下文调整回复
   - 记住之前的对话历史
   - 提供针对性的建议

## 生成回复时请参考
- 客户的原始问题
- 识别到的意图类型
- 相关的知识库信息（如果有）
- 已生成的文档（如果有）
- 对话历史上下文

请生成自然、专业、有针对性的销售回复。"""


def _get_default_reply(intent: UserIntent = None) -> str:
    """获取默认回复（兜底）"""
    intent_replies = {
        UserIntent.QUOTE_GENERATION: "已为您生成报价单，请查看下载链接。如有任何调整需求请随时告诉我。",
        UserIntent.PROPOSAL_CREATION: "提案书已生成完成，包含详细的项目方案和实施计划。",
        UserIntent.CONTRACT_DRAFTING: "合同草案已准备就绪，请审阅条款内容。",
        UserIntent.PRODUCT_INQUIRY: "感谢您的咨询！我们的产品可以帮助您提升销售效率。如需了解更多详情或安排演示，请随时告诉我。",
        UserIntent.PRICE_NEGOTIATION: "关于价格问题，我们可以根据您的具体需求提供灵活的方案。请告诉我您的预算范围，我为您推荐最合适的配置。",
        UserIntent.COMPLAINT_HANDLING: "非常抱歉给您带来了不好的体验。我们会认真对待您的反馈，并尽快为您解决问题。",
        UserIntent.FOLLOW_UP: "感谢您的耐心等待，我会立即为您跟进此事，并在有进展后第一时间通知您。",
    }
    
    if intent and intent in intent_replies:
        return intent_replies[intent]
    
    return "您好！我是您的智能销售助手。请问有什么可以帮助您的？"


async def sales_response_node(state: SalesState) -> SalesState:
    """
    销售回复节点 - 生成标准销售回复
    
    防御性设计：
    - 如果已有 sales_response，直接返回
    - 如果没有，使用 LLM 生成
    - LLM 失败时使用兜底回复
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[Session: {session_id}] 生成销售回复")
    
    # 如果已有回复，直接返回（可能由前面节点生成）
    existing_reply = state.get("sales_response")
    if existing_reply and isinstance(existing_reply, str) and len(existing_reply.strip()) > 0:
        logger.debug("[Response] 使用已有回复")
        state["next_node"] = "end"
        return state
    
    # 获取意图信息
    intent_analysis = state.get("intent_analysis")
    intent = UserIntent.GENERAL_CHAT
    if intent_analysis and hasattr(intent_analysis, 'intent'):
        intent = intent_analysis.intent
    
    try:
        # 准备上下文
        knowledge_response = state.get("metadata", {}).get("knowledge_response", "")
        generated_docs = state.get("generated_documents", [])
        
        # 构建提示
        context_parts = []
        
        if knowledge_response:
            context_parts.append(f"[知识库信息]\n{knowledge_response}")
        
        if generated_docs and len(generated_docs) > 0:
            doc_names = []
            for doc in generated_docs:
                if isinstance(doc, dict):
                    doc_names.append(doc.get("file_name", "文档"))
                elif hasattr(doc, 'file_name'):
                    doc_names.append(doc.file_name)
            if doc_names:
                context_parts.append(f"[已生成文档]\n{', '.join(doc_names)}")
        
        context_str = "\n\n".join(context_parts) if context_parts else "无额外上下文"
        
        # 获取用户消息
        messages = state.get("messages", [])
        user_message = ""
        if messages and len(messages) > 0:
            last_msg = messages[-1]
            if hasattr(last_msg, 'content'):
                user_message = last_msg.content
            elif isinstance(last_msg, dict):
                user_message = last_msg.get("content", "")
        
        # 调用 LLM 生成回复
        llm = ChatOpenAI(
            model=settings.default_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.7,
        )
        
        prompt = f"""{SALES_RESPONSE_PROMPT}

用户消息：{user_message}
识别意图：{intent.value if hasattr(intent, 'value') else str(intent)}

上下文信息：
{context_str}

请生成专业的销售回复："""

        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content="请生成回复")
        ])
        
        reply = response.content if hasattr(response, 'content') else str(response)
        
        # 如果没有生成文档，添加建议
        suggested_actions = ["了解产品详情", "获取报价", "预约演示"]
        if generated_docs and len(generated_docs) > 0:
            suggested_actions = ["下载文档", "修改内容", "生成其他格式"]
        
        state["sales_response"] = reply
        state["suggested_actions"] = suggested_actions
        
        logger.info(f"[Response] 回复生成完成，长度: {len(reply)}")
        
    except Exception as e:
        logger.error(f"[Response] 生成回复失败: {e}")
        # 兜底回复
        state["sales_response"] = _get_default_reply(intent)
        state["suggested_actions"] = ["重新尝试", "联系人工客服"]
    
    state["next_node"] = "end"
    return state


async def sales_negotiation_node(state: SalesState) -> SalesState:
    """
    价格谈判节点 - 处理价格相关对话
    
    防御性设计：任何情况下都返回有效的谈判话术
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[Session: {session_id}] 处理价格谈判")
    
    # 如果已有回复，直接返回
    existing_reply = state.get("sales_response")
    if existing_reply and isinstance(existing_reply, str) and len(existing_reply.strip()) > 0:
        state["next_node"] = "end"
        return state
    
    # 价格谈判专用话术
    negotiation_reply = (
        "感谢您的关注！关于价格，我们可以为您提供灵活的方案：\n\n"
        "1. **标准报价**：根据官方定价执行\n"
        "2. **批量优惠**：购买3套以上享受9折\n"
        "3. **长期合作**：签订2年合同享85折\n\n"
        "请告诉我您的具体需求和预算范围，我为您定制最优方案。"
    )
    
    state["sales_response"] = negotiation_reply
    state["suggested_actions"] = ["获取正式报价", "了解优惠政策", "预约详细沟通"]
    state["next_node"] = "end"
    
    return state


async def complaint_handler_node(state: SalesState) -> SalesState:
    """
    投诉处理节点 - 处理客户投诉
    
    防御性设计：任何情况下都返回安抚性回复
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[Session: {session_id}] 处理客户投诉")
    
    # 如果已有回复，直接返回
    existing_reply = state.get("sales_response")
    if existing_reply and isinstance(existing_reply, str) and len(existing_reply.strip()) > 0:
        state["next_node"] = "end"
        return state
    
    # 投诉处理专用话术
    complaint_reply = (
        "非常抱歉给您带来了不好的体验，我深表歉意。\n\n"
        "我们非常重视您的反馈，会立即采取以下措施：\n"
        "1. 记录您的问题并升级给相关部门\n"
        "2. 安排专人在2小时内与您联系\n"
        "3. 确保问题得到妥善解决\n\n"
        "您的满意是我们最大的追求，再次致歉！"
    )
    
    state["sales_response"] = complaint_reply
    state["suggested_actions"] = ["联系客服经理", "提交详细反馈", "了解售后政策"]
    state["next_node"] = "end"
    
    return state


# 兼容性导出（旧代码可能依赖）
clarify_document_type_node = sales_response_node

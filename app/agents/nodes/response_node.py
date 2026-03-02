"""
销售回复节点 - 生成最终回复内容

这是工作流的最后一个节点，负责整合所有信息生成最终回复。
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
   - 提及客户关心的具体点
   - 展现对客户需求的理解

## 不同场景的回复风格

- **产品咨询**：详细介绍功能，强调价值，提供案例
- **价格谈判**：强调性价比，提供方案选择，说明投资回报
- **文档生成**：确认需求细节，说明交付时间，提供修改选项
- **投诉处理**：表达理解，诚恳道歉，提供解决方案
- **日常沟通**：友好亲切，保持联系，适时推进

## 输出格式

请直接输出回复内容，不要包含任何元信息或标签。
如果提供了知识库信息，请自然地整合到回复中。"""


NEGOTIATION_PROMPT = """你是一位经验丰富的销售谈判专家。客户正在就价格进行谈判。

## 谈判原则

1. **价值导向**
   - 不要直接降价，而是强调产品价值
   - 说明价格背后的成本构成
   - 提供投资回报率分析

2. **灵活方案**
   - 提供多个价格选项（基础版/专业版/企业版）
   - 考虑非价格让步（延保、培训、优先支持等）
   - 创造双赢方案

3. **限时优惠**
   - 适当使用限时优惠创造紧迫感
   - 强调当前报价的特殊性
   - 避免过度让步

4. **客户成功**
   - 强调客户使用产品后的成功案例
   - 说明长期合作的价值
   - 建立信任关系

请基于以上原则，为客户提供一个专业且有说服力的回复。"""


COMPLAINT_PROMPT = """你是一位专业的客户服务专家，正在处理客户的投诉或不满。

## 处理原则

1. **倾听理解**
   - 首先表达理解和同情
   - 确认客户的感受是合理的
   - 避免辩解或推卸责任

2. **诚恳道歉**
   - 为给客户带来的困扰真诚道歉
   - 不找借口，直接承认问题
   - 表达改进的决心

3. **解决方案**
   - 提供具体的解决方案
   - 说明解决时间表
   - 给予适当补偿（如适用）

4. **预防未来**
   - 说明如何避免类似问题
   - 提供额外的保障措施
   - 建立更紧密的沟通渠道

请基于以上原则，为客户提供一个真诚、专业的回复。"""


async def sales_response_node(state: SalesState) -> SalesState:
    """
    销售回复节点
    
    生成最终的客户回复内容。
    """
    logger.info(f"[Session: {state['session_id']}] 生成销售回复")
    
    try:
        # 如果已经通过其他节点生成了回复，直接返回
        if state.get("sales_response"):
            logger.info("回复已生成，跳过")
            return state
        
        # 选择适当的提示
        intent = state["intent_analysis"].intent if state["intent_analysis"] else UserIntent.GENERAL_CHAT
        
        if intent == UserIntent.PRICE_NEGOTIATION:
            system_prompt = NEGOTIATION_PROMPT
        elif intent == UserIntent.COMPLAINT_HANDLING:
            system_prompt = COMPLAINT_PROMPT
        else:
            system_prompt = SALES_RESPONSE_PROMPT
        
        # 准备上下文信息
        context_parts = []
        
        # 添加知识库结果
        if state["knowledge_results"]:
            kb_content = state["metadata"].get("knowledge_response", "")
            if kb_content:
                context_parts.append(f"【基于知识库的回答】\n{kb_content}")
        
        # 添加业务上下文
        if state["context"]:
            context_parts.append(f"【客户信息】\n{state['context']}")
        
        context_str = "\n\n".join(context_parts)
        
        # 构建消息
        llm = ChatOpenAI(
            model=settings.default_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.7,
        )
        
        messages = [
            SystemMessage(content=system_prompt),
        ]
        
        # 添加对话历史（最近 3 轮）
        for msg in state["messages"][-6:]:
            if msg.type == "human":
                messages.append(HumanMessage(content=msg.content))
            elif msg.type == "ai":
                messages.append(SystemMessage(content=f"助手：{msg.content}"))
        
        # 添加上下文
        if context_str:
            messages.append(SystemMessage(content=f"参考信息：\n{context_str}"))
        
        # 添加最终提示
        messages.append(HumanMessage(content="请基于以上信息，为客户生成一个专业、友好的回复。"))
        
        # 生成回复
        response = await llm.ainvoke(messages)
        
        state["sales_response"] = response.content
        
        # 生成建议操作
        state["suggested_actions"] = _generate_suggested_actions(intent, state)
        
        logger.info("销售回复生成完成")
        
    except Exception as e:
        logger.error(f"生成回复失败: {str(e)}")
        state["error"] = f"生成回复失败: {str(e)}"
        state["sales_response"] = "抱歉，我暂时遇到了一些技术问题。请稍后再试，或联系我们的客服团队。"
    
    state["next_node"] = "end"
    return state


def _generate_suggested_actions(intent: UserIntent, state: SalesState) -> list:
    """生成建议的下一步操作"""
    
    # 通用建议
    common_actions = ["继续咨询", "转人工客服"]
    
    # 根据意图生成特定建议
    intent_actions = {
        UserIntent.PRODUCT_INQUIRY: ["查看产品详情", "预约演示", "获取报价"],
        UserIntent.PRICE_NEGOTIATION: ["申请特殊折扣", "了解付款方式", "查看套餐方案"],
        UserIntent.QUOTE_GENERATION: ["修改报价内容", "导出 PDF", "发送邮件"],
        UserIntent.PROPOSAL_CREATION: ["修改方案", "生成 PPT", "预约讲解"],
        UserIntent.CONTRACT_DRAFTING: ["查看合同条款", "预约法务咨询", "电子签约"],
        UserIntent.GENERAL_CHAT: ["了解产品", "查看案例", "联系销售"],
        UserIntent.COMPLAINT_HANDLING: ["提交工单", "联系客服经理", "查看处理进度"],
    }
    
    specific = intent_actions.get(intent, ["了解更多"])
    
    # 如果已经生成了文档，添加相关操作
    if state["generated_documents"]:
        specific = ["下载文档", "重新生成"] + specific
    
    return specific[:3] + common_actions  # 最多返回 5 个建议


async def sales_negotiation_node(state: SalesState) -> SalesState:
    """
    价格谈判节点
    
    专门处理价格谈判场景。
    """
    logger.info(f"[Session: {state['session_id']}] 进入价格谈判流程")
    
    # 直接调用销售回复节点，但使用谈判专用提示
    return await sales_response_node(state)


async def complaint_handler_node(state: SalesState) -> SalesState:
    """
    投诉处理节点
    
    专门处理客户投诉场景。
    """
    logger.info(f"[Session: {state['session_id']}] 进入投诉处理流程")
    
    return await sales_response_node(state)


async def clarify_document_type_node(state: SalesState) -> SalesState:
    """
    澄清文档类型节点
    
    当用户模糊地说"生成文档"但未指定类型时使用。
    """
    logger.info(f"[Session: {state['session_id']}] 需要澄清文档类型")
    
    state["sales_response"] = (
        "我可以帮您生成以下类型的销售文档：\n\n"
        "📄 **报价单** - 产品价格清单\n"
        "📋 **提案书** - 项目解决方案\n"
        "📝 **合同** - 合作协议\n"
        "📊 **数据分析报表** - 销售数据统计\n"
        "📽️ **演示文稿** - 产品演示 PPT\n\n"
        "请告诉我您需要哪种文档？"
    )
    state["suggested_actions"] = [
        "生成报价单",
        "创建提案书",
        "起草合同",
        "制作报表",
        "生成 PPT"
    ]
    state["next_node"] = "end"
    
    return state

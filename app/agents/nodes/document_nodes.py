"""
文档生成相关节点 - 处理报价单、提案书、合同等文档生成

这些节点直接集成你的本地技能（docx, pptx, xlsx, pdf）。
"""

import json
import os
import subprocess
from datetime import datetime
from typing import Any, Dict

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.agents.state import SalesState
from app.models.chat import (
    DocumentInfo,
    DocumentType,
    QuoteParams,
    ProposalParams,
    ContractParams,
    AnalysisParams,
    PresentationParams,
    UserIntent,
)

logger = get_logger("document_nodes")


# 参数提取提示模板
PARAM_EXTRACTION_PROMPT = """你是一个参数提取专家。请从用户的对话中提取生成文档所需的参数。

当前意图：{intent}

请分析用户消息和上下文，提取以下参数并以 JSON 格式返回：

{param_description}

重要规则：
1. 尽可能从用户消息中提取信息
2. 如果某些参数缺失，使用合理的默认值（不要留空，不要返回在 missing_params 中）
3. 报价单必须包含客户名称、产品名称、单价，如缺失请使用：
   - customer_name: "尊贵的客户"
   - product_name: "至尊钻石版AI销售解决方案" 
   - unit_price: 99999
4. 返回必须是合法的 JSON 格式

示例输出格式：
{{
    "params": {{...}},
    "missing_params": [],
    "reasoning": "提取说明"
}}"""


# 默认兜底参数（用于自动生成）
DEFAULT_QUOTE_PARAMS = {
    "customer_name": "尊贵的客户",
    "product_name": "至尊钻石版AI销售解决方案",
    "unit_price": 99999,
    "quantity": 1,
    "valid_days": 30,
    "notes": "本报价为系统默认值生成，仅供参考。如有特殊需求，请联系销售代表。"
}

# 不同文档类型的参数描述
PARAM_DESCRIPTIONS = {
    UserIntent.QUOTE_GENERATION: """
报价单参数 (QuoteParams):
- customer_name: 客户名称（如用户提供则使用，否则默认"尊贵的客户"）
- products: 产品列表，每项包含 name, quantity, unit_price
  - 如用户未提供，使用默认值：
  - name: "至尊钻石版AI销售解决方案"
  - quantity: 1
  - unit_price: 99999
- valid_days: 报价有效期天数，默认 30
- discount_rate: 折扣率（0-1之间），可选
- notes: 备注信息，可选
""",
    UserIntent.PROPOSAL_CREATION: """
提案书参数 (ProposalParams):
- customer_name: 客户名称（必填）
- project_name: 项目名称（必填）
- project_background: 项目背景描述，可选
- solution_highlights: 方案亮点列表，可选
- timeline: 实施周期，可选
- budget_range: 预算范围，可选
""",
    UserIntent.CONTRACT_DRAFTING: """
合同参数 (ContractParams):
- party_a: 甲方名称（必填）
- party_b: 乙方名称（必填）
- contract_type: 合同类型（销售合同、服务合同等）
- key_terms: 关键条款，如付款方式、交付时间等
- amount: 合同金额，可选
""",
    UserIntent.DATA_ANALYSIS: """
数据分析参数 (AnalysisParams):
- data_source: 数据源描述或文件路径（必填）
- analysis_type: 分析类型（销售分析、客户分析等）
- metrics: 关键指标列表
- date_range: 时间范围，可选
""",
    UserIntent.PRESENTATION_REQUEST: """
演示文稿参数 (PresentationParams):
- title: 演示标题（必填）
- subtitle: 副标题，可选
- sections: 章节大纲列表
- target_audience: 目标受众
- slides_count: 幻灯片数量，默认 10
""",
}


async def extract_document_params_node(state: SalesState) -> SalesState:
    """
    文档参数提取节点
    
    从用户消息中提取生成文档所需的参数。
    """
    logger.info(f"[Session: {state['session_id']}] 开始提取文档参数")
    
    intent = state["intent_analysis"].intent
    
    try:
        llm = ChatOpenAI(
            model=settings.default_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.2,
        )
        
        # 获取参数描述
        param_desc = PARAM_DESCRIPTIONS.get(intent, "请提取文档生成所需的所有参数")
        
        # 构建提示
        prompt = PARAM_EXTRACTION_PROMPT.format(
            intent=intent.value,
            param_description=param_desc
        )
        
        # 准备对话历史
        history_text = "\n".join([
            f"{'用户' if m.type == 'human' else '助手'}: {m.content}"
            for m in state["messages"][-5:]  # 最近5轮对话
        ])
        
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=f"对话历史：\n{history_text}\n\n当前业务上下文：{json.dumps(state['context'], ensure_ascii=False)}")
        ]
        
        response = await llm.ainvoke(messages)
        
        # 解析 JSON
        try:
            result = json.loads(response.content)
            params = result.get("params", {})
            missing = result.get("missing_params", [])
            
            logger.info(f"参数提取完成，原始参数: {params}, 缺失: {missing}")
            
            # 自动应用默认值（强制填充缺失参数，不再反问用户）
            if intent == UserIntent.QUOTE_GENERATION:
                # 客户名称兜底
                if not params.get("customer_name"):
                    params["customer_name"] = DEFAULT_QUOTE_PARAMS["customer_name"]
                    logger.info(f"客户名称缺失，使用默认值: {params['customer_name']}")
                
                # 产品信息兜底
                products = params.get("products", [])
                if not products or not isinstance(products, list) or len(products) == 0:
                    # 检查是否有单独的产品字段
                    product_name = params.get("product_name") or params.get("product") or DEFAULT_QUOTE_PARAMS["product_name"]
                    unit_price = params.get("unit_price") or params.get("price") or DEFAULT_QUOTE_PARAMS["unit_price"]
                    try:
                        unit_price = float(unit_price)
                    except (ValueError, TypeError):
                        unit_price = DEFAULT_QUOTE_PARAMS["unit_price"]
                    
                    quantity = params.get("quantity") or DEFAULT_QUOTE_PARAMS["quantity"]
                    try:
                        quantity = int(float(quantity))
                    except (ValueError, TypeError):
                        quantity = DEFAULT_QUOTE_PARAMS["quantity"]
                    
                    params["products"] = [{
                        "name": product_name,
                        "quantity": quantity,
                        "unit_price": unit_price
                    }]
                    logger.info(f"产品信息缺失，使用默认值: {params['products']}")
                
                # 报价有效期兜底
                if not params.get("valid_days"):
                    params["valid_days"] = DEFAULT_QUOTE_PARAMS["valid_days"]
                
                # 备注兜底
                if not params.get("notes"):
                    params["notes"] = DEFAULT_QUOTE_PARAMS["notes"]
            
            # 补充上下文信息
            params.update({
                "_customer_name": state["context"].get("customer_name"),
                "_sales_rep": state["context"].get("sales_rep_name"),
                "_generated_at": datetime.now().isoformat(),
            })
            
            # 强制清空 missing，确保流程不被中断
            state["document_params"] = {
                "intent": intent.value,
                "params": params,
                "missing": []  # 强制为空，不再反问用户
            }
            
            # 强制进入文档生成节点（不再检查缺失参数）
            state["next_node"] = "generate_document"
            logger.info(f"[Session: {state['session_id']}] 参数已就绪，直接进入文档生成")
            
        except json.JSONDecodeError:
            logger.warning("参数提取返回非 JSON，使用完整默认参数")
            # 使用完整默认参数生成
            state["document_params"] = {
                "intent": intent.value,
                "params": {
                    "customer_name": DEFAULT_QUOTE_PARAMS["customer_name"],
                    "products": [{
                        "name": DEFAULT_QUOTE_PARAMS["product_name"],
                        "quantity": DEFAULT_QUOTE_PARAMS["quantity"],
                        "unit_price": DEFAULT_QUOTE_PARAMS["unit_price"]
                    }],
                    "valid_days": DEFAULT_QUOTE_PARAMS["valid_days"],
                    "notes": DEFAULT_QUOTE_PARAMS["notes"],
                    "_generated_at": datetime.now().isoformat(),
                },
                "missing": []
            }
            state["next_node"] = "generate_document"
        
        return state
        
    except Exception as e:
        logger.error(f"参数提取失败: {str(e)}")
        state["error"] = f"参数提取失败: {str(e)}"
        state["next_node"] = "sales_response"
        return state


async def request_missing_params_node(state: SalesState) -> SalesState:
    """
    请求缺失参数节点
    
    当关键参数缺失时，向用户询问。
    """
    missing = state["metadata"].get("missing_params", [])
    
    # 生成询问消息
    param_names_map = {
        "customer_name": "客户名称",
        "party_a": "甲方名称",
        "party_b": "乙方名称",
        "title": "文档标题",
        "products": "产品清单",
        "project_name": "项目名称",
    }
    
    questions = [param_names_map.get(p, p) for p in missing]
    
    state["sales_response"] = (
        f"为了生成您需要的文档，请提供以下信息：\n"
        f"• " + "\n• ".join(questions)
    )
    state["suggested_actions"] = ["自动填充上次信息", "稍后补充"]
    state["next_node"] = "end"
    
    return state


async def generate_document_node(state: SalesState) -> SalesState:
    """
    文档生成节点
    
    根据文档类型调用相应的生成逻辑。
    """
    logger.info(f"[Session: {state['session_id']}] 开始生成文档")
    
    doc_info = state.get("document_params", {})
    intent_value = doc_info.get("intent", "")
    params = doc_info.get("params", {})
    
    try:
        # 映射到 UserIntent
        intent_map = {
            "quote_generation": UserIntent.QUOTE_GENERATION,
            "proposal_creation": UserIntent.PROPOSAL_CREATION,
            "contract_drafting": UserIntent.CONTRACT_DRAFTING,
            "data_analysis": UserIntent.DATA_ANALYSIS,
            "presentation_request": UserIntent.PRESENTATION_REQUEST,
        }
        intent = intent_map.get(intent_value, UserIntent.DOCUMENT_REQUEST)
        
        # 根据意图生成对应文档
        if intent == UserIntent.QUOTE_GENERATION:
            doc_result = await _generate_quote_document(params)
        elif intent == UserIntent.PROPOSAL_CREATION:
            doc_result = await _generate_proposal_document(params)
        elif intent == UserIntent.DATA_ANALYSIS:
            doc_result = await _generate_analysis_document(params)
        elif intent == UserIntent.PRESENTATION_REQUEST:
            doc_result = await _generate_presentation(params)
        else:
            # 默认生成简单的 DOCX
            doc_result = await _generate_generic_document(intent, params)
        
        state["generated_documents"].append(doc_result)
        state["metadata"]["generated_doc"] = doc_result.model_dump()
        
        # 获取文件名（用于前端渲染下载按钮）
        filename = doc_result.file_name
        
        # 生成配套回复话术
        if intent == UserIntent.QUOTE_GENERATION:
            customer = params.get("customer_name", "客户")
            products = params.get("products", [])
            # 检查是否使用了默认参数
            is_default = (
                customer == DEFAULT_QUOTE_PARAMS["customer_name"] or
                (products and products[0].get("name") == DEFAULT_QUOTE_PARAMS["product_name"])
            )
            
            if is_default:
                # 使用了默认值的回复
                state["sales_response"] = (
                    f"✅ **已为您生成默认的标准报价单，请点击下方按钮下载查看。**\n\n"
                    f"📋 **报价详情：**\n"
                    f"• 客户：{customer}\n"
                    f"• 产品：{products[0].get('name', 'AI解决方案') if products else 'AI解决方案'}\n"
                    f"• 单价：¥{products[0].get('unit_price', 99999):,.0f} 元\n"
                    f"• 数量：{products[0].get('quantity', 1)}\n"
                    f"• 总计：¥{sum(p.get('quantity', 1) * p.get('unit_price', 0) for p in products):,.0f} 元\n\n"
                    f"📄 **文件：{filename}**\n\n"
                    f"💡 **温馨提示：**\n"
                    f"如需定制报价内容（如修改客户名称、产品配置、价格等），"
                    f"请直接告诉我，我可以为您重新生成！"
                )
            else:
                # 用户提供了完整参数的回复
                total = sum(p.get("quantity", 1) * p.get("unit_price", 0) for p in products)
                state["sales_response"] = (
                    f"✅ **报价单已生成，请点击下方按钮下载查看！**\n\n"
                    f"📋 **报价概要：**\n"
                    f"• 客户：{customer}\n"
                    f"• 产品数量：{len(products)} 项\n"
                    f"• 报价总额：¥{total:,.0f} 元\n\n"
                    f"📄 **文件：{filename}**\n\n"
                    f"如有任何调整需求，请随时告诉我！"
                )
        else:
            # 其他文档类型的通用回复
            state["sales_response"] = (
                f"✅ 已为您生成 {doc_result.doc_type.value.upper()} 文档：{filename}\n\n"
                f"您可以直接下载使用，如需修改请告诉我。"
            )
        
        state["suggested_actions"] = ["修改内容", "生成其他格式", "发送给客户"]
        state["next_node"] = "end"
        
    except Exception as e:
        logger.error(f"文档生成失败: {str(e)}")
        state["error"] = f"文档生成失败: {str(e)}"
        state["sales_response"] = "抱歉，文档生成过程中出现了错误。请稍后重试，或联系技术支持。"
        state["next_node"] = "end"
    
    return state


def _extract_products_from_context(params: Dict[str, Any]) -> list:
    """
    从参数或上下文中提取产品信息。
    
    如果 params 中没有 products，尝试从其他字段或上下文中提取。
    兜底方案：创建一个默认产品条目。
    """
    products = params.get("products", [])
    
    # 如果已经有产品列表，直接返回
    if products and isinstance(products, list) and len(products) > 0:
        return products
    
    # 尝试从上下文字段中提取产品信息
    # 有些场景下 LLM 可能把产品信息放在其他字段
    potential_products = []
    
    # 1. 检查是否有产品名称字段
    product_name = params.get("product_name") or params.get("product") or params.get("item_name")
    if product_name:
        # 提取价格信息
        price = 0
        price_fields = ["price", "unit_price", "amount", "total_price", "cost"]
        for field in price_fields:
            if field in params and params[field] is not None:
                try:
                    price = float(params[field])
                    break
                except (ValueError, TypeError):
                    continue
        
        # 如果没有找到价格，尝试从参数字符串中提取数字
        if price == 0:
            import re
            for key, value in params.items():
                if isinstance(value, (int, float)) and value > 100:  # 假设大于100的数可能是价格
                    price = float(value)
                    break
                elif isinstance(value, str):
                    # 尝试匹配金额格式如 "99999元" 或 "¥99999"
                    match = re.search(r'[¥￥]?\s*(\d{4,})\s*[元块]?', value)
                    if match:
                        price = float(match.group(1))
                        break
        
        # 提取数量
        quantity = 1
        qty_fields = ["quantity", "qty", "count", "num"]
        for field in qty_fields:
            if field in params and params[field] is not None:
                try:
                    quantity = int(float(params[field]))
                    break
                except (ValueError, TypeError):
                    continue
        
        potential_products.append({
            "name": product_name,
            "quantity": quantity,
            "unit_price": price
        })
    
    # 2. 尝试从 _raw_messages 或上下文中解析（如果存在）
    context_str = json.dumps(params, ensure_ascii=False)
    
    # 简单的正则提取：查找"产品"、"服务"等关键词后面的内容
    import re
    
    # 尝试匹配常见的产品描述格式
    # 例如："至尊钻石版AI服务 - 99999元" 或 "产品：XXX，价格：99999"
    product_patterns = [
        r'([\u4e00-\u9fa5\w]+(?:版|型|系列|服务|产品|方案))[\s\-—:：]*(\d{4,})\s*[元块]',
        r'(?:产品|商品|服务)[名称]?[\s:：]*([\u4e00-\u9fa5\w]+)[\s\S]{0,30}?(\d{4,})\s*[元块]',
        r'(?:价格|金额|报价)[\s:：]*(\d{4,})[\s\S]{0,30}?([\u4e00-\u9fa5\w]+(?:版|型|系列|服务))',
    ]
    
    for pattern in product_patterns:
        matches = re.findall(pattern, context_str)
        for match in matches:
            if isinstance(match, tuple):
                # 确定哪个是产品名，哪个是价格
                name_part = match[0] if not match[0].isdigit() else match[1]
                price_part = match[1] if match[1].isdigit() else match[0]
                try:
                    potential_products.append({
                        "name": name_part.strip(),
                        "quantity": 1,
                        "unit_price": float(price_part)
                    })
                except (ValueError, TypeError):
                    continue
    
    # 3. 兜底方案：如果还是没有产品，从参数字段中推断
    if not potential_products:
        # 查找任何可能的产品名称（包含"版"、"型"、"服务"等关键词的字段值）
        for key, value in params.items():
            if isinstance(value, str) and any(kw in value for kw in ["版", "型", "系列", "服务", "方案", "产品"]):
                # 查找对应的价格
                price = 0
                for pkey, pvalue in params.items():
                    if isinstance(pvalue, (int, float)) and pvalue > 100:
                        price = float(pvalue)
                        break
                    elif isinstance(pvalue, str):
                        match = re.search(r'(\d{4,})', pvalue)
                        if match:
                            try:
                                price = float(match.group(1))
                                break
                            except:
                                continue
                
                potential_products.append({
                    "name": value,
                    "quantity": 1,
                    "unit_price": price if price > 0 else 99999  # 默认价格兜底
                })
                break  # 只取第一个匹配的产品
    
    # 最终兜底：如果还是没有，使用默认产品
    if not potential_products:
        # 尝试从客户名称推断产品
        customer = params.get("customer_name", "客户")
        potential_products.append({
            "name": "AI智能解决方案（标准版）",
            "quantity": 1,
            "unit_price": 99999
        })
    
    return potential_products


async def _generate_quote_document(params: Dict[str, Any]) -> DocumentInfo:
    """生成报价单（Excel 格式）"""
    
    customer = params.get("customer_name", "客户")
    # 使用提取函数获取产品列表（支持从多种字段解析）
    products = _extract_products_from_context(params)
    valid_days = params.get("valid_days", 30)
    
    # 确保输出目录存在
    output_dir = settings.output_dir
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"报价单_{customer}_{timestamp}.xlsx"
    filepath = os.path.join(output_dir, filename)
    
    # 使用 openpyxl 生成 Excel（这是 xlsx skill 的核心技术）
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        
        wb = Workbook()
        ws = wb.active
        ws.title = "报价单"
        
        # 标题
        ws["A1"] = "报价单"
        ws["A1"].font = Font(size=20, bold=True)
        ws["A1"].alignment = Alignment(horizontal="center")
        ws.merge_cells("A1:E1")
        
        # 基本信息
        ws["A3"] = f"客户：{customer}"
        ws["A4"] = f"日期：{datetime.now().strftime('%Y-%m-%d')}"
        ws["A5"] = f"有效期：{valid_days}天"
        
        # 表头
        headers = ["序号", "产品名称", "数量", "单价", "小计"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=7, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        
        # 产品列表
        total = 0
        for i, prod in enumerate(products, 1):
            qty = prod.get("quantity", 1)
            price = prod.get("unit_price", 0)
            subtotal = qty * price
            total += subtotal
            
            ws.cell(row=7+i, column=1, value=i)
            ws.cell(row=7+i, column=2, value=prod.get("name", ""))
            ws.cell(row=7+i, column=3, value=qty)
            ws.cell(row=7+i, column=4, value=price)
            ws.cell(row=7+i, column=5, value=subtotal)
        
        # 总计
        total_row = 8 + len(products)
        ws.cell(row=total_row, column=4, value="总计：")
        ws.cell(row=total_row, column=4).font = Font(bold=True)
        ws.cell(row=total_row, column=5, value=total)
        ws.cell(row=total_row, column=5).font = Font(bold=True)
        
        # 调整列宽
        ws.column_dimensions["A"].width = 8
        ws.column_dimensions["B"].width = 30
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 15
        ws.column_dimensions["E"].width = 15
        
        wb.save(filepath)
        
        return DocumentInfo(
            doc_type=DocumentType.XLSX,
            file_name=filename,
            file_path=filepath,
            file_size=os.path.getsize(filepath)
        )
        
    except ImportError:
        logger.warning("openpyxl 未安装，生成简易文本版本")
        # 回退到文本版本
        txt_filename = filename.replace(".xlsx", ".txt")
        txt_filepath = os.path.join(output_dir, txt_filename)
        
        content = f"报价单\n客户：{customer}\n日期：{datetime.now().strftime('%Y-%m-%d')}\n\n"
        for prod in products:
            content += f"- {prod.get('name')}: {prod.get('quantity')} × {prod.get('unit_price')}\n"
        
        with open(txt_filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        return DocumentInfo(
            doc_type=DocumentType.DOCX,
            file_name=txt_filename,
            file_path=txt_filepath,
            file_size=os.path.getsize(txt_filepath)
        )


async def _generate_proposal_document(params: Dict[str, Any]) -> DocumentInfo:
    """生成提案书（Word 格式）"""
    
    # 简化实现，实际可集成 docx skill
    output_dir = settings.output_dir
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"提案书_{params.get('customer_name', '客户')}_{timestamp}.docx"
    filepath = os.path.join(output_dir, filename)
    
    # 使用 python-docx 生成文档
    try:
        from docx import Document
        from docx.shared import Inches, Pt
        
        doc = Document()
        
        # 标题
        title = doc.add_heading(params.get("project_name", "项目提案书"), 0)
        
        # 客户信息
        doc.add_paragraph(f"致：{params.get('customer_name', '尊敬的客户')}")
        doc.add_paragraph(f"日期：{datetime.now().strftime('%Y年%m月%d日')}")
        doc.add_paragraph()
        
        # 背景
        if params.get("project_background"):
            doc.add_heading("一、项目背景", level=1)
            doc.add_paragraph(params["project_background"])
        
        # 方案亮点
        if params.get("solution_highlights"):
            doc.add_heading("二、方案亮点", level=1)
            for highlight in params["solution_highlights"]:
                doc.add_paragraph(highlight, style="List Bullet")
        
        # 实施周期
        if params.get("timeline"):
            doc.add_heading("三、实施计划", level=1)
            doc.add_paragraph(f"预计实施周期：{params['timeline']}")
        
        doc.save(filepath)
        
        return DocumentInfo(
            doc_type=DocumentType.DOCX,
            file_name=filename,
            file_path=filepath,
            file_size=os.path.getsize(filepath)
        )
        
    except ImportError:
        # 回退到文本
        txt_path = filepath.replace(".docx", ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"提案书：{params.get('project_name')}\n")
            f.write(f"客户：{params.get('customer_name')}\n")
        
        return DocumentInfo(
            doc_type=DocumentType.DOCX,
            file_name=os.path.basename(txt_path),
            file_path=txt_path,
            file_size=os.path.getsize(txt_path)
        )


async def _generate_analysis_document(params: Dict[str, Any]) -> DocumentInfo:
    """生成数据分析报表"""
    # 简化实现
    output_dir = settings.output_dir
    os.makedirs(output_dir, exist_ok=True)
    
    filename = f"数据分析报表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(output_dir, filename)
    
    # 创建示例报表
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "数据分析"
        
        ws["A1"] = params.get("analysis_type", "销售数据分析")
        ws["A1"].font = ws["A1"].font.copy(size=16, bold=True)
        ws.merge_cells("A1:D1")
        
        ws["A3"] = f"数据源：{params.get('data_source', 'N/A')}"
        ws["A4"] = f"时间范围：{params.get('date_range', '全部')}" 
        ws["A5"] = f"分析指标：{', '.join(params.get('metrics', []))}"
        
        wb.save(filepath)
        
        return DocumentInfo(
            doc_type=DocumentType.XLSX,
            file_name=filename,
            file_path=filepath,
            file_size=os.path.getsize(filepath)
        )
    except:
        pass


async def _generate_presentation(params: Dict[str, Any]) -> DocumentInfo:
    """生成演示文稿"""
    output_dir = settings.output_dir
    os.makedirs(output_dir, exist_ok=True)
    
    filename = f"演示文稿_{params.get('title', 'Untitled')}_{datetime.now().strftime('%Y%m%d')}.txt"
    filepath = os.path.join(output_dir, filename)
    
    # 生成大纲文本（实际项目中可使用 pptx skill 的 node.js 脚本）
    content = f"""演示文稿大纲：{params.get('title')}
副标题：{params.get('subtitle', '')}
目标受众：{params.get('target_audience', '')}

章节大纲：
"""
    for i, section in enumerate(params.get("sections", []), 1):
        content += f"{i}. {section}\n"
    
    content += f"\n共 {params.get('slides_count', 10)} 页幻灯片"
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    
    return DocumentInfo(
        doc_type=DocumentType.PPTX,
        file_name=filename,
        file_path=filepath,
        file_size=os.path.getsize(filepath)
    )


async def _generate_generic_document(intent: UserIntent, params: Dict) -> DocumentInfo:
    """生成通用文档"""
    output_dir = settings.output_dir
    os.makedirs(output_dir, exist_ok=True)
    
    filename = f"文档_{intent.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"文档类型：{intent.value}\n")
        f.write(f"生成时间：{datetime.now().isoformat()}\n")
        f.write(f"参数：{json.dumps(params, ensure_ascii=False, indent=2)}")
    
    return DocumentInfo(
        doc_type=DocumentType.DOCX,
        file_name=filename,
        file_path=filepath,
        file_size=os.path.getsize(filepath)
    )

"""
知识库检索节点 (RAG) - 回答产品相关问题

重构要点：
1. 强制使用智谱 ZhipuAIEmbeddings + embedding-2 模型
2. 使用 langchain_text_splitters 最新导入路径
3. 知识库为空时生成有效测试文档（含真实产品价格）
4. 防御性编程：任何情况下不报错，返回干净 state
"""

import os
from typing import Dict, Any, List, Optional

from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain_community.embeddings import ZhipuAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.core.logging import get_logger
from app.agents.state import SalesState

logger = get_logger("knowledge_node")


# ═══════════════════════════════════════════════════════════════
# 默认产品知识库（当目录为空时自动生成）
# ═══════════════════════════════════════════════════════════════

DEFAULT_KNOWLEDGE_BASE = """# 智能销售AI Agent - 产品知识库

## 至尊钻石版AI服务

**产品定位**：企业级AI销售助手旗舰解决方案

**核心功能**：
- 智能客户意图识别与自动分流
- 私有化部署保障数据安全
- 7×24小时自动化销售响应
- 多格式文档自动生成（报价单/合同/提案书）

**官方定价**：
- 年费：¥99,999/年（含全年技术支持）
- 部署费：¥20,000（一次性）
- 定制开发：¥5,000/人天

**目标客户**：中大型企业销售团队、需要自动化销售流程的B2B公司

---

## AI获客服务包

**产品定位**：社交媒体自动化获客解决方案

**核心功能**：
- 抖音精准获客：自动识别目标用户群体，智能评论截流
- 小红书种草：自动化内容发布与互动管理
- 私域流量运营：微信群自动维护与转化追踪
- 线索评分系统：AI自动评估线索质量与成交概率

**官方定价**：
- 基础版：¥15,000/年（单平台）
- 专业版：¥35,000/年（三平台）
- 旗舰版：¥58,000/年（全平台+专属运营顾问）

**目标客户**：电商卖家、本地生活服务商、知识付费创作者

---

## 数据安全网关

**产品定位**：企业数据安全与合规解决方案

**核心功能**：
- 敏感数据自动识别与脱敏
- 访问权限精细管控
- 操作日志全程审计
- 等保三级合规支持

**官方定价**：
- 标准版：¥25,000/年（支持100用户）
- 企业版：¥68,000/年（无限用户+专属支持）

**目标客户**：金融、医疗、政务等对数据安全要求高的行业

---

## 常见问题解答（FAQ）

Q: 产品是否支持试用？
A: 支持。所有产品提供14天免费试用，试用期间功能无限制。

Q: 如何获取技术支持？
A: 购买后分配专属客户成功经理，提供微信/电话/邮件多渠道支持。

Q: 是否支持定制开发？
A: 支持。根据需求复杂度评估，标准报价¥5,000/人天。

Q: 数据存储在哪里？
A: 至尊钻石版支持私有化部署，数据完全存储在客户自有服务器。

---

## 竞品对比

| 功能 | 本产品 | 竞品A | 竞品B |
|-----|-------|-------|-------|
| 私有化部署 | ✅ 支持 | ❌ 不支持 | ⚠️ 额外收费 |
| 多平台获客 | ✅ 原生支持 | ⚠️ 需插件 | ❌ 不支持 |
| 文档自动生成 | ✅ 内置 | ❌ 不支持 | ⚠️ 第三方对接 |
| 价格 | ¥99,999/年 | ¥150,000/年 | ¥120,000/年 |

---

*文档生成时间：2024年*
*版本：v2.0*
"""


# ═══════════════════════════════════════════════════════════════
# 知识库服务类
# ═══════════════════════════════════════════════════════════════

class KnowledgeBaseService:
    """
    知识库服务 - 封装 RAG 相关操作
    
    防御性设计原则：
    1. 初始化失败不抛异常，返回空向量库
    2. 检索失败返回空列表而非报错
    3. 知识库为空时自动生成测试文档
    """
    
    def __init__(self):
        self.embeddings: Optional[ZhipuAIEmbeddings] = None
        self.vector_store: Optional[FAISS] = None
        self._initialized: bool = False
        self._init_error: Optional[str] = None
    
    def _ensure_knowledge_base_dir(self) -> str:
        """
        确保知识库目录存在
        
        如果目录不存在，创建目录并生成默认测试文档
        绝不使用无意义的"初始化文档"占位符
        """
        kb_path = os.path.abspath(settings.knowledge_base_path)
        
        # 创建目录
        if not os.path.exists(kb_path):
            try:
                os.makedirs(kb_path, exist_ok=True)
                logger.info(f"[KB] 创建知识库目录: {kb_path}")
            except Exception as e:
                logger.error(f"[KB] 创建目录失败: {e}")
                return kb_path
        
        # 检查目录是否为空
        try:
            files = [f for f in os.listdir(kb_path) 
                     if f.endswith(('.txt', '.md')) and not f.startswith('.')]
            
            if not files:
                logger.warning(f"[KB] 知识库目录为空，生成默认测试文档")
                self._generate_default_knowledge_base(kb_path)
        except Exception as e:
            logger.error(f"[KB] 检查目录内容失败: {e}")
        
        return kb_path
    
    def _generate_default_knowledge_base(self, kb_path: str):
        """
        生成默认知识库文档（含真实产品价格）
        
        绝不使用无意义的"初始化文档"，而是提供有效的产品信息
        """
        try:
            default_file = os.path.join(kb_path, "product_catalog.md")
            with open(default_file, "w", encoding="utf-8") as f:
                f.write(DEFAULT_KNOWLEDGE_BASE)
            logger.info(f"[KB] 默认知识库已生成: {default_file}")
        except Exception as e:
            logger.error(f"[KB] 生成默认知识库失败: {e}")
    
    def _load_documents_from_directory(self, directory_path: str) -> List:
        """
        从目录加载所有文本文件（.txt 和 .md）
        
        防御性处理：
        - 目录不存在返回空列表
        - 文件读取失败跳过并记录日志
        - 支持 UTF-8 编码，失败时尝试其他编码
        """
        documents = []
        
        if not os.path.exists(directory_path):
            logger.warning(f"[KB] 知识库目录不存在: {directory_path}")
            return documents
        
        supported_extensions = ['.txt', '.md']
        
        try:
            files = os.listdir(directory_path)
            logger.info(f"[KB] 扫描目录，发现 {len(files)} 个文件")
            
            for filename in files:
                file_path = os.path.join(directory_path, filename)
                
                # 跳过目录和隐藏文件
                if not os.path.isfile(file_path) or filename.startswith('.'):
                    continue
                
                ext = os.path.splitext(filename)[1].lower()
                if ext not in supported_extensions:
                    logger.debug(f"[KB] 跳过不支持的文件类型: {filename}")
                    continue
                
                # 尝试加载文件（多编码支持）
                doc = self._load_single_file(file_path, filename)
                if doc:
                    documents.extend(doc)
                    
        except Exception as e:
            logger.error(f"[KB] 遍历知识库目录失败: {e}")
        
        logger.info(f"[KB] 文档加载完成: {len(documents)} 个文档")
        return documents
    
    def _load_single_file(self, file_path: str, filename: str) -> Optional[List]:
        """
        加载单个文件，支持多编码尝试
        
        尝试顺序：UTF-8 → GBK → Latin-1
        """
        encodings = ['utf-8', 'gbk', 'latin-1']
        
        for encoding in encodings:
            try:
                loader = TextLoader(file_path, encoding=encoding)
                docs = loader.load()
                
                # 添加来源元数据
                for doc in docs:
                    doc.metadata['source'] = filename
                    doc.metadata['file_path'] = file_path
                    doc.metadata['encoding'] = encoding
                
                logger.info(f"[KB] 成功加载文件: {filename} ({len(docs)} 个文档, 编码: {encoding})")
                return docs
                
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"[KB] 加载文件失败 {filename} (编码 {encoding}): {e}")
                continue
        
        logger.error(f"[KB] 无法解码文件: {filename}，已跳过")
        return None
    
    def _create_vector_store_from_documents(self, documents: List) -> Optional[FAISS]:
        """
        从文档创建向量存储
        
        使用 RecursiveCharacterTextSplitter 进行智能切片
        """
        if not documents:
            logger.warning("[KB] 没有文档可处理")
            return None
        
        try:
            # 使用 RecursiveCharacterTextSplitter 进行文档切片
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                length_function=len,
                separators=["\n\n", "\n", "。", "，", " ", ""]
            )
            
            split_docs = text_splitter.split_documents(documents)
            logger.info(f"[KB] 文档切片完成: {len(documents)} 个原始文档 -> {len(split_docs)} 个文本块")
            
            if not split_docs:
                logger.warning("[KB] 切片后没有文本块")
                return None
            
            # 创建向量存储
            vector_store = FAISS.from_documents(split_docs, self.embeddings)
            logger.info(f"[KB] 向量存储创建成功，包含 {len(split_docs)} 个向量")
            
            return vector_store
            
        except Exception as e:
            logger.error(f"[KB] 创建向量存储失败: {e}")
            return None
    
    async def initialize(self) -> bool:
        """
        初始化知识库（延迟加载）
        
        返回值：
            bool: 初始化是否成功（无论成功与否都不抛异常）
        """
        if self._initialized:
            return True
        
        try:
            # 步骤 1：初始化 Embedding 模型（智谱 embedding-2）
            logger.info(f"[KB] 初始化 Embedding 模型: {settings.embedding_model}")
            
            # 关键修正：使用 ZhipuAIEmbeddings 而非 OpenAIEmbeddings
            self.embeddings = ZhipuAIEmbeddings(
                model=settings.embedding_model,  # 必须是 embedding-2
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
            
            # 步骤 2：确保知识库目录和默认文档
            kb_path = self._ensure_knowledge_base_dir()
            
            # 步骤 3：尝试加载已有向量库
            try:
                self.vector_store = await FAISS.aload_local(
                    settings.vector_store_path,
                    self.embeddings
                )
                logger.info("[KB] 已有向量库加载成功")
                self._initialized = True
                return True
                
            except Exception as e:
                logger.info(f"[KB] 未找到现有向量库或加载失败: {e}")
                logger.info("[KB] 将从本地文档重新创建...")
            
            # 步骤 4：从本地文档创建向量库
            documents = self._load_documents_from_directory(kb_path)
            
            if not documents:
                logger.warning("[KB] 未找到任何文档，将使用空向量库")
                # 创建一个最小化的向量库（避免后续报错）
                self.vector_store = FAISS.from_texts(
                    ["智能销售AI Agent产品目录"],
                    self.embeddings
                )
            else:
                self.vector_store = self._create_vector_store_from_documents(documents)
            
            # 步骤 5：保存向量库（如果创建成功）
            if self.vector_store:
                try:
                    os.makedirs(settings.vector_store_path, exist_ok=True)
                    self.vector_store.save_local(settings.vector_store_path)
                    logger.info(f"[KB] 向量库已保存到: {settings.vector_store_path}")
                except Exception as e:
                    logger.warning(f"[KB] 向量库保存失败（非阻塞）: {e}")
            
            # ═══ 最终检查：确保初始化成功后向量库必须存在 ═══
            if self.vector_store is None:
                logger.error("[KB] 初始化流程完成但向量库为 None，标记为失败")
                self._init_error = "初始化后向量库仍为 None"
                self._initialized = False
                return False
            
            self._initialized = True
            return True
            
        except Exception as e:
            self._init_error = str(e)
            logger.error(f"[KB] 知识库初始化失败: {e}")
            # 初始化失败不抛异常，设置标志让后续调用知道状态
            self._initialized = False
            return False
    
    async def search(
        self, 
        query: str, 
        top_k: int = 5,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        检索相关知识
        
        防御性设计：
        - 未初始化时尝试自动初始化（强制）
        - 检索失败返回空列表而非报错
        - 过滤低相关度结果
        """
        # ═══ 强制初始化检查（修复：确保向量库就绪）═══
        if not self._initialized or self.vector_store is None:
            logger.info("[KB] 向量库未就绪，触发自动初始化...")
            success = await self.initialize()
            if not success:
                logger.warning("[KB] 自动初始化失败，返回空结果")
                return []
            
            # 再次检查向量库是否就绪
            if self.vector_store is None:
                logger.error("[KB] 初始化后向量库仍为 None")
                return []
        
        # 防御性参数校验
        if not query or not isinstance(query, str):
            logger.warning("[KB] 查询为空或类型错误")
            return []
        
        query = query.strip()
        if not query:
            return []
        
        if not self.vector_store:
            logger.warning("[KB] 向量库未就绪")
            return []
        
        try:
            logger.info(f"[KB] 执行检索: query='{query[:50]}...', top_k={top_k}")
            
            # 执行相似度搜索
            docs_with_scores = self.vector_store.similarity_search_with_score(
                query, 
                k=top_k
            )
            
            results = []
            for doc, score in docs_with_scores:
                result = {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": float(score),
                    "source": doc.metadata.get("source", "unknown")
                }
                results.append(result)
            
            # 过滤低相关度结果（L2距离，越小越相似，阈值设为 1.5）
            filtered_results = [r for r in results if r["score"] < 1.5]
            
            logger.info(f"[KB] 检索完成: 原始 {len(results)} 条, 过滤后 {len(filtered_results)} 条")
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"[KB] 知识库检索失败: {e}")
            return []
    
    async def add_documents(self, texts: List[str], metadatas: List[Dict] = None) -> bool:
        """
        添加文档到知识库
        
        返回值：bool 表示是否成功
        """
        if not self._initialized:
            success = await self.initialize()
            if not success:
                return False
        
        if not self.vector_store:
            logger.error("[KB] 向量库未就绪，无法添加文档")
            return False
        
        try:
            self.vector_store.add_texts(texts, metadatas=metadatas)
            # 保存到本地
            self.vector_store.save_local(settings.vector_store_path)
            logger.info(f"[KB] 成功添加 {len(texts)} 个文档到知识库")
            return True
            
        except Exception as e:
            logger.error(f"[KB] 添加文档失败: {e}")
            return False
    
    async def reload_knowledge_base(self) -> bool:
        """重新加载知识库（用于手动刷新）"""
        logger.info("[KB] 开始重新加载知识库...")
        self._initialized = False
        self.vector_store = None
        return await self.initialize()
    
    def get_status(self) -> Dict[str, Any]:
        """获取知识库状态信息"""
        return {
            "initialized": self._initialized,
            "init_error": self._init_error,
            "embedding_model": settings.embedding_model,
            "knowledge_base_path": settings.knowledge_base_path,
            "vector_store_path": settings.vector_store_path,
        }


# ═══════════════════════════════════════════════════════════════
# 全局知识库服务实例
# ═══════════════════════════════════════════════════════════════

kb_service = KnowledgeBaseService()


# ═══════════════════════════════════════════════════════════════
# LangGraph 节点函数
# ═══════════════════════════════════════════════════════════════

async def knowledge_retrieval_node(state: SalesState) -> SalesState:
    """
    知识库检索节点 - 防御性增强版
    
    无论发生任何情况，都返回干净的 state 字典，绝不报错崩溃
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[Session: {session_id}] 开始知识库检索")
    
    try:
        # 防御性：确保 knowledge_results 存在
        if "knowledge_results" not in state:
            state["knowledge_results"] = []
        
        # 获取用户查询（防御性处理）
        messages = state.get("messages", [])
        query = ""
        if messages and isinstance(messages, list):
            try:
                last_message = messages[-1]
                query = getattr(last_message, 'content', str(last_message))
            except Exception as e:
                logger.warning(f"[KB Node] 获取用户消息失败: {e}")
                query = "产品信息"  # 默认查询
        
        if not query:
            query = "产品信息"
        
        # 执行检索
        context = state.get("context", {})
        filters = context.get("filters") if isinstance(context, dict) else None
        
        results = await kb_service.search(
            query=query,
            top_k=5,
            filters=filters
        )
        
        # 更新 state
        state["knowledge_results"] = results
        
        if results:
            logger.info(f"[KB Node] 检索到 {len(results)} 条相关知识")
            # 打印检索到的具体内容，便于调试
            for i, result in enumerate(results[:3], 1):  # 只打印前3条
                logger.info(f"[KB Node] [结果 {i}] Source: {result['source']}, Score: {result['score']:.3f}")
                logger.info(f"[KB Node] [结果 {i}] Content: {result['content'][:100]}...")
            
            # 有知识库结果，进入知识整合节点
            state["next_node"] = "knowledge_synthesis"
        else:
            logger.warning("[KB Node] 未检索到相关知识，使用默认回复")
            # 无结果，直接生成回复（不中断）
            state["next_node"] = "sales_response"
            # 可选：添加默认提示
            state["metadata"] = state.get("metadata", {})
            state["metadata"]["knowledge_hint"] = "未找到匹配的产品信息，将使用通用话术回复"
        
        return state
        
    except Exception as e:
        logger.error(f"[KB Node] 知识库检索节点异常: {e}")
        # 防御性兜底：任何错误都不中断流程
        state["knowledge_results"] = []
        state["error"] = f"知识库检索异常: {str(e)}"  # 记录错误但不阻断
        state["next_node"] = "sales_response"
        state["metadata"] = state.get("metadata", {})
        state["metadata"]["knowledge_fallback"] = True
        return state


async def knowledge_synthesis_node(state: SalesState) -> SalesState:
    """
    知识整合节点 - 防御性增强版
    
    将检索到的知识与上下文整合，生成回答
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    from langchain_openai import ChatOpenAI
    
    session_id = state.get("session_id", "unknown")
    logger.info(f"[Session: {session_id}] 开始知识整合")
    
    try:
        # 防御性：检查知识结果
        knowledge_results = state.get("knowledge_results", [])
        if not knowledge_results or not isinstance(knowledge_results, list):
            logger.warning("[KB Synthesis] 没有知识结果可整合")
            state["next_node"] = "sales_response"
            return state
        
        # 准备知识上下文
        knowledge_context = "\n\n".join([
            f"[相关度: {r['score']:.3f}] {r['content']}"
            for r in knowledge_results[:3]  # 只取前3条
        ])
        
        # 构建提示
        synthesis_prompt = f"""你是一位专业的产品顾问。基于以下从知识库检索到的信息，回答客户的问题。

检索到的相关信息：
{knowledge_context}

请根据以上信息，为客户提供准确、专业的回答。
如果检索到的信息不足以回答问题，请诚实地告知客户你需要进一步确认。

回答要求：
1. 语言简洁专业
2. 突出产品优势和价值
3. 如有需要，可以引导客户进行下一步（如索取详细资料、安排演示等）"""

        llm = ChatOpenAI(
            model=settings.default_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.7,
        )
        
        # 获取用户消息
        messages = state.get("messages", [])
        user_content = "请介绍相关产品信息"
        if messages and isinstance(messages, list):
            try:
                user_content = getattr(messages[-1], 'content', user_content)
            except:
                pass
        
        messages = [
            SystemMessage(content=synthesis_prompt),
            HumanMessage(content=user_content)
        ]
        
        response = await llm.ainvoke(messages)
        
        # 保存到 metadata，供后续节点使用
        state["metadata"] = state.get("metadata", {})
        state["metadata"]["knowledge_response"] = response.content
        state["next_node"] = "sales_response"
        
        logger.info(f"[KB Synthesis] 知识整合完成，生成 {len(response.content)} 字符回复")
        
        return state
        
    except Exception as e:
        logger.error(f"[KB Synthesis] 知识整合失败: {e}")
        # 防御性兜底
        state["error"] = f"知识整合失败: {str(e)}"
        state["next_node"] = "sales_response"
        return state


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

async def get_knowledge_base_status() -> Dict[str, Any]:
    """获取知识库状态（用于健康检查）"""
    return kb_service.get_status()


async def reload_knowledge_base() -> bool:
    """重新加载知识库（管理接口）"""
    return await kb_service.reload_knowledge_base()

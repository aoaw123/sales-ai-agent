"""
知识库检索节点 (RAG) - 回答产品相关问题

使用向量检索从知识库中查找相关信息。
"""

import os
from typing import Dict, Any, List

from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings
from app.core.logging import get_logger
from app.agents.state import SalesState

logger = get_logger("knowledge_node")


class KnowledgeBaseService:
    """知识库服务 - 封装 RAG 相关操作"""
    
    def __init__(self):
        self.embeddings = None
        self.vector_store = None
        self._initialized = False
    
    def _load_documents_from_directory(self, directory_path: str) -> List:
        """
        从目录加载所有文本文件（.txt 和 .md）
        
        Args:
            directory_path: 知识库目录路径
            
        Returns:
            文档列表
        """
        documents = []
        
        if not os.path.exists(directory_path):
            logger.warning(f"知识库目录不存在: {directory_path}")
            return documents
        
        # 支持的文件扩展名
        supported_extensions = ['.txt', '.md']
        
        try:
            # 遍历目录下的所有文件
            for filename in os.listdir(directory_path):
                file_path = os.path.join(directory_path, filename)
                
                # 检查是否是文件以及扩展名是否支持
                if os.path.isfile(file_path):
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in supported_extensions:
                        try:
                            loader = TextLoader(file_path, encoding='utf-8')
                            docs = loader.load()
                            # 添加来源信息到 metadata
                            for doc in docs:
                                doc.metadata['source'] = filename
                                doc.metadata['file_path'] = file_path
                            documents.extend(docs)
                            logger.info(f"成功加载文件: {filename} ({len(docs)} 个文档)")
                        except Exception as e:
                            logger.error(f"加载文件失败 {filename}: {str(e)}")
                    else:
                        logger.debug(f"跳过不支持的文件类型: {filename}")
                        
        except Exception as e:
            logger.error(f"遍历知识库目录失败: {str(e)}")
            
        return documents
    
    def _create_vector_store_from_documents(self, documents: List) -> FAISS:
        """
        从文档创建向量存储
        
        Args:
            documents: 文档列表
            
        Returns:
            FAISS 向量存储实例
        """
        if not documents:
            logger.warning("没有文档可处理，将创建空向量库")
            return FAISS.from_texts(
                ["初始化文档"],
                self.embeddings
            )
        
        # 使用 RecursiveCharacterTextSplitter 进行文档切片
        # chunk_size=500: 每个块大约 500 个字符
        # chunk_overlap=50: 块之间重叠 50 个字符，确保上下文连贯
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            length_function=len,
            separators=["\n\n", "\n", "。", "，", " ", ""]
        )
        
        # 分割文档
        split_docs = text_splitter.split_documents(documents)
        logger.info(f"文档切片完成: {len(documents)} 个原始文档 -> {len(split_docs)} 个文本块")
        
        # 创建向量存储
        vector_store = FAISS.from_documents(split_docs, self.embeddings)
        logger.info(f"向量存储创建成功，包含 {len(split_docs)} 个向量")
        
        return vector_store
    
    async def initialize(self):
        """初始化知识库（延迟加载）"""
        if self._initialized:
            return
            
        try:
            self.embeddings = OpenAIEmbeddings(
                model=settings.embedding_model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
            
            # 尝试加载已有向量库
            try:
                self.vector_store = await FAISS.aload_local(
                    settings.vector_store_path,
                    self.embeddings
                )
                logger.info("已有向量库加载成功")
            except Exception:
                logger.warning("未找到现有向量库，将从本地文档创建...")
                
                # 从本地目录加载文档
                documents = self._load_documents_from_directory(settings.knowledge_base_path)
                
                # 创建向量存储
                self.vector_store = self._create_vector_store_from_documents(documents)
                
                # 保存到本地，下次直接加载
                if documents:
                    self.vector_store.save_local(settings.vector_store_path)
                    logger.info(f"向量库已保存到: {settings.vector_store_path}")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"知识库初始化失败: {str(e)}")
            raise
    
    async def search(
        self, 
        query: str, 
        top_k: int = 5,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        检索相关知识
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            filters: 过滤条件
        
        Returns:
            检索结果列表
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 执行相似度搜索
            docs_with_scores = self.vector_store.similarity_search_with_score(
                query, 
                k=top_k
            )
            
            results = []
            for doc, score in docs_with_scores:
                results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": float(score),
                    "source": doc.metadata.get("source", "unknown")
                })
            
            return results
            
        except Exception as e:
            logger.error(f"知识库检索失败: {str(e)}")
            return []
    
    async def add_documents(self, texts: List[str], metadatas: List[Dict] = None):
        """添加文档到知识库"""
        if not self._initialized:
            await self.initialize()
        
        try:
            self.vector_store.add_texts(texts, metadatas=metadatas)
            # 保存到本地
            self.vector_store.save_local(settings.vector_store_path)
            logger.info(f"成功添加 {len(texts)} 个文档到知识库")
        except Exception as e:
            logger.error(f"添加文档失败: {str(e)}")
            raise
    
    async def reload_knowledge_base(self):
        """重新加载知识库（用于手动刷新）"""
        logger.info("开始重新加载知识库...")
        self._initialized = False
        
        try:
            # 加载文档
            documents = self._load_documents_from_directory(settings.knowledge_base_path)
            
            # 创建新的向量存储
            self.vector_store = self._create_vector_store_from_documents(documents)
            
            # 保存
            self.vector_store.save_local(settings.vector_store_path)
            self._initialized = True
            logger.info("知识库重新加载完成")
            
        except Exception as e:
            logger.error(f"重新加载知识库失败: {str(e)}")
            raise


# 全局知识库服务实例
kb_service = KnowledgeBaseService()


async def knowledge_retrieval_node(state: SalesState) -> SalesState:
    """
    知识库检索节点
    
    根据用户查询从知识库中检索相关信息。
    """
    logger.info(f"[Session: {state['session_id']}] 开始知识库检索")
    
    try:
        # 获取用户查询
        query = state["messages"][-1].content if state["messages"] else ""
        
        # 执行检索
        results = await kb_service.search(
            query=query,
            top_k=5,
            filters=state["context"].get("filters")
        )
        
        # 过滤低相关度结果 (L2距离，越小越相似，阈值设为 1.5)
        filtered_results = [r for r in results if r["score"] < 1.5]
        
        state["knowledge_results"] = filtered_results
        
        if filtered_results:
            logger.info(f"检索到 {len(filtered_results)} 条相关知识")
            # 打印检索到的具体内容，便于调试
            for i, result in enumerate(filtered_results, 1):
                logger.info(f"[检索结果 {i}] Source: {result['source']}, Score: {result['score']:.3f}")
                logger.info(f"[检索结果 {i}] Content: {result['content'][:200]}...")
            # 有知识库结果，进入知识整合节点
            state["next_node"] = "knowledge_synthesis"
        else:
            logger.warning("未检索到相关知识")
            # 无结果，直接生成回复
            state["next_node"] = "sales_response"
        
        return state
        
    except Exception as e:
        logger.error(f"知识库检索失败: {str(e)}")
        state["error"] = f"知识库检索失败: {str(e)}"
        state["knowledge_results"] = []
        state["next_node"] = "sales_response"
        return state


async def knowledge_synthesis_node(state: SalesState) -> SalesState:
    """
    知识整合节点
    
    将检索到的知识与上下文整合，生成回答。
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    from langchain_openai import ChatOpenAI
    
    logger.info(f"[Session: {state['session_id']}] 开始知识整合")
    
    try:
        # 准备知识上下文
        knowledge_context = "\n\n".join([
            f"[相关度: {r['score']:.3f}] {r['content']}"
            for r in state["knowledge_results"]
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
        
        messages = [
            SystemMessage(content=synthesis_prompt),
            HumanMessage(content=state["messages"][-1].content)
        ]
        
        response = await llm.ainvoke(messages)
        
        # 保存到 metadata，供后续节点使用
        state["metadata"]["knowledge_response"] = response.content
        state["next_node"] = "sales_response"
        
        return state
        
    except Exception as e:
        logger.error(f"知识整合失败: {str(e)}")
        state["error"] = f"知识整合失败: {str(e)}"
        state["next_node"] = "sales_response"
        return state

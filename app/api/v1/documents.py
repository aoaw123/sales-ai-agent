"""
文档 API 模块 - 文档下载和管理
"""

import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.models.chat import DocumentInfo

logger = get_logger("api.documents")

router = APIRouter()


@router.get(
    "/documents/{filename}",
    summary="下载生成的文档",
    description="下载 Agent 生成的文档文件（报价单、提案书等）"
)
async def download_document(filename: str):
    """
    下载文档文件
    
    Args:
        filename: 文件名
    
    Returns:
        文件下载响应
    """
    # 安全检查：防止目录遍历攻击
    if ".." in filename or "/" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的文件名"
        )
    
    file_path = os.path.join(settings.output_dir, filename)
    
    if not os.path.exists(file_path):
        logger.warning(f"请求的文件不存在: {file_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # 确定 MIME 类型
    mime_types = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
    }
    
    ext = os.path.splitext(filename)[1].lower()
    media_type = mime_types.get(ext, "application/octet-stream")
    
    logger.info(f"下载文件: {filename}")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
    )


@router.get(
    "/documents",
    summary="列出所有生成的文档",
    description="获取输出目录中所有生成的文档列表"
)
async def list_documents(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[DocumentInfo]:
    """
    列出文档
    
    Args:
        limit: 返回数量限制
        offset: 偏移量
    
    Returns:
        文档信息列表
    """
    output_dir = settings.output_dir
    
    if not os.path.exists(output_dir):
        return []
    
    documents = []
    
    try:
        files = sorted(
            os.listdir(output_dir),
            key=lambda x: os.path.getmtime(os.path.join(output_dir, x)),
            reverse=True
        )
        
        files = files[offset:offset + limit]
        
        for filename in files:
            file_path = os.path.join(output_dir, filename)
            
            if os.path.isfile(file_path):
                ext = os.path.splitext(filename)[1].lower()
                
                from app.models.chat import DocumentType
                doc_type_map = {
                    ".docx": DocumentType.DOCX,
                    ".xlsx": DocumentType.XLSX,
                    ".pptx": DocumentType.PPTX,
                    ".pdf": DocumentType.PDF,
                }
                doc_type = doc_type_map.get(ext, DocumentType.DOCX)
                
                documents.append(DocumentInfo(
                    doc_type=doc_type,
                    file_name=filename,
                    file_path=file_path,
                    file_size=os.path.getsize(file_path),
                ))
        
        return documents
        
    except Exception as e:
        logger.error(f"列出文档失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档列表失败: {str(e)}"
        )


@router.delete(
    "/documents/{filename}",
    summary="删除文档",
    description="删除指定的生成文档"
)
async def delete_document(filename: str):
    """
    删除文档
    """
    # 安全检查
    if ".." in filename or "/" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的文件名"
        )
    
    file_path = os.path.join(settings.output_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    try:
        os.remove(file_path)
        logger.info(f"删除文件: {filename}")
        return {"status": "deleted", "filename": filename}
    except Exception as e:
        logger.error(f"删除文件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}"
        )

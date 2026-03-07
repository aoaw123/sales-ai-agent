/**
 * MessageBubble 组件 - 消息气泡与下载区域
 * 
 * 核心功能：
 * - 渲染用户和 AI 消息
 * - 防御性提取和显示下载文件
 * - 支持 Markdown 渲染
 * 
 * 防御性编程：
 * - 可选链操作符 ?. 防止白屏
 * - 严格类型检查
 * - 空值兜底
 * - Set 去重
 * 
 * 中文支持：
 * - 正则表达式 [一-龥] 匹配中文文件名
 */

import { useMemo, useCallback } from 'react';
import { User, Bot, Loader2 } from 'lucide-react';
import { DownloadButton } from './DownloadButton';
import type { MessageBubbleProps, DocumentInfo } from '../types';

/**
 * 从消息内容中提取文件名
 * 支持中文文件名 [一-龥]
 * 
 * @param content - 消息内容
 * @returns 提取的文件名数组
 */
const extractFilenamesFromContent = (content: string | undefined): string[] => {
  // 防御性检查
  if (!content || typeof content !== 'string') {
    return [];
  }

  /**
   * 关键：支持中文的正则表达式
   * [一-龥] - 匹配中文字符
   * \w - 匹配单词字符（字母、数字、下划线）
   * \- - 匹配连字符
   * 
   * 这样可以匹配：
   * - 报价单_华为公司_20260306.xlsx
   * - product_list_v2.xlsx
   * - 测试文档-2024.md
   */
  const filenameRegex = /[\w\-\u4e00-\u9fa5]+\.(?:xlsx|xls|docx|doc|pdf|txt|md|pptx)/gi;
  
  const matches = content.match(filenameRegex);
  
  if (!matches || !Array.isArray(matches)) {
    return [];
  }
  
  // 过滤并清理
  return matches
    .map(name => name.trim())
    .filter(name => name.length > 0);
};

/**
 * 提取文档列表（防御性 + 去重）
 * 
 * @param message - 消息对象
 * @returns 处理后的文档列表
 */
const useExtractDocuments = (message: MessageBubbleProps['message']): DocumentInfo[] => {
  return useMemo(() => {
    // 防御性检查：确保 message 有效
    if (!message || typeof message !== 'object') {
      return [];
    }

    const extractedDocs: DocumentInfo[] = [];
    const filenameSet = new Set<string>(); // 用于去重

    // 1. 从 documents 数组提取（优先）
    // 使用可选链 ?. 防止白屏
    const docList = message.documents;
    
    if (docList && Array.isArray(docList) && docList.length > 0) {
      docList.forEach((doc) => {
        // 防御性检查：确保 doc 是对象且有 filename
        if (doc && typeof doc === 'object' && 'filename' in doc && doc.filename) {
          const filename = String(doc.filename).trim();
          
          // Set 去重
          if (filename && !filenameSet.has(filename)) {
            filenameSet.add(filename);
            extractedDocs.push({
              filename,
              path: doc.path || `/output/${filename}`,
              type: doc.type || filename.split('.').pop() || 'unknown',
              size: doc.size,
            });
          }
        }
      });
    }

    // 2. 从 content 文本中提取（兜底）
    const contentFilenames = extractFilenamesFromContent(message.content);
    
    contentFilenames.forEach((filename) => {
      // Set 去重：检查是否已存在
      if (!filenameSet.has(filename)) {
        filenameSet.add(filename);
        extractedDocs.push({
          filename,
          path: `/output/${filename}`,
          type: filename.split('.').pop() || 'unknown',
        });
      }
    });

    return extractedDocs;
  }, [message]);
};

/**
 * Markdown 渲染函数（简化版）
 */
const renderMarkdown = (text: string | undefined): string => {
  if (!text || typeof text !== 'string') {
    return '';
  }

  return text
    // 转义 HTML 特殊字符
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // 代码块
    .replace(/```([\s\S]*?)```/g, '<pre class="bg-slate-900 text-slate-200 p-3 rounded-lg overflow-x-auto my-2"><code>$1</code></pre>')
    // 行内代码
    .replace(/`([^`]+)`/g, '<code class="bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded text-sm">$1</code>')
    // 标题
    .replace(/^### (.*$)/gim, '<h3 class="text-lg font-semibold mt-4 mb-2">$1</h3>')
    .replace(/^## (.*$)/gim, '<h2 class="text-xl font-semibold mt-5 mb-3">$1</h2>')
    .replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold mt-6 mb-4">$1</h1>')
    // 粗体
    .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold">$1</strong>')
    // 斜体
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    // 列表
    .replace(/^[-*] (.*$)/gim, '<li class="ml-4">$1</li>')
    // 链接
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:underline">$1</a>')
    // 换行
    .replace(/\n/g, '<br />');
};

/**
 * 格式化时间
 */
const formatTime = (date: Date | undefined): string => {
  if (!date || !(date instanceof Date) || isNaN(date.getTime())) {
    return '';
  }
  
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });
};

/**
 * 消息气泡组件
 * 
 * 视觉特点：
 * - 用户消息：蓝色渐变，右侧对齐
 * - AI 消息：玻璃拟态浅色，左侧对齐
 * - 下载区域：科技感深色卡片
 */
export function MessageBubble({ message, isLoading = false }: MessageBubbleProps) {
  // 防御性检查
  if (!message || typeof message !== 'object') {
    return null;
  }

  const isUser = message.role === 'user';
  const documents = useExtractDocuments(message);
  const hasDocuments = documents.length > 0;
  
  // 处理下载
  // 修复：使用正确的后端下载路径 /api/v1/docs/documents/{filename}
  const handleDownload = useCallback((filename: string) => {
    const downloadUrl = `http://127.0.0.1:8000/api/v1/docs/documents/${encodeURIComponent(filename)}`;
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, []);

  return (
    <div 
      className={`
        flex gap-3 max-w-4xl mx-auto
        ${isUser ? 'flex-row-reverse' : 'flex-row'}
      `}
    >
      {/* 头像 */}
      <div
        className={`
          w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0
          shadow-lg
          ${isUser 
            ? 'bg-gradient-to-br from-blue-500 to-blue-600 shadow-blue-500/20' 
            : 'bg-gradient-to-br from-violet-500 to-purple-600 shadow-violet-500/20'}
        `}
      >
        {isUser ? (
          <User className="w-5 h-5 text-white" />
        ) : (
          <Bot className="w-5 h-5 text-white" />
        )}
      </div>
      
      {/* 消息内容区域 */}
      <div 
        className={`
          flex flex-col max-w-[calc(100vw-5rem)] lg:max-w-2xl
          ${isUser ? 'items-end' : 'items-start'}
        `}
      >
        {/* 消息气泡 */}
        <div
          className={`
            px-5 py-3 rounded-2xl
            ${isUser
              ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-br-md shadow-lg shadow-blue-500/20'
              : 'bg-white/80 backdrop-blur-sm border border-white/50 text-slate-800 rounded-bl-md shadow-md'}
          `}
        >
          {/* 用户消息直接显示文本 */}
          {isUser ? (
            <p className="text-sm leading-relaxed whitespace-pre-wrap">
              {message.content || ''}
            </p>
          ) : (
            /* AI 消息使用 Markdown 渲染 */
            <div
              className="markdown-content text-sm leading-relaxed prose prose-slate max-w-none"
              dangerouslySetInnerHTML={{ 
                __html: renderMarkdown(message.content) 
              }}
            />
          )}
        </div>
        
        {/* 时间戳 */}
        <span className="text-xs text-slate-400 mt-1.5 px-1">
          {formatTime(message.timestamp)}
        </span>
        
        {/* 
          下载区域 - 科技感设计
          
          防御性编程：
          - 只有在 hasDocuments 为 true 时才渲染
          - 静默隐藏，不显示"无文件"等提示
        */}
        {hasDocuments && !isUser && (
          <div 
            className="mt-4 w-full max-w-md"
            style={{
              background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.05) 0%, rgba(30, 41, 59, 0.08) 100%)',
              borderRadius: '16px',
              padding: '16px',
              border: '1px solid rgba(56, 189, 248, 0.15)',
            }}
          >
            {/* 下载区域标题 */}
            <div className="flex items-center gap-2 mb-3">
              <div 
                className="w-1.5 h-4 rounded-full"
                style={{
                  background: 'linear-gradient(to bottom, #38bdf8, #0ea5e9)',
                }}
              />
              <h4 className="text-sm font-semibold text-slate-700">
                生成文件 ({documents.length})
              </h4>
            </div>
            
            {/* 文件列表 */}
            <div className="space-y-2">
              {documents.map((doc, index) => (
                <DownloadButton
                  key={`${doc.filename}-${index}`}
                  filename={doc.filename}
                  onDownload={handleDownload}
                  className="w-full"
                />
              ))}
            </div>
            
            {/* 底部装饰线 */}
            <div 
              className="mt-4 h-px w-full"
              style={{
                background: 'linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.3), transparent)',
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * 加载状态消息气泡
 */
export function LoadingBubble() {
  return (
    <div className="flex gap-3 max-w-4xl mx-auto">
      {/* AI 头像 */}
      <div 
        className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0
                   bg-gradient-to-br from-violet-500 to-purple-600 shadow-lg shadow-violet-500/20"
      >
        <Bot className="w-5 h-5 text-white" />
      </div>
      
      {/* 加载状态 */}
      <div 
        className="bg-white/80 backdrop-blur-sm border border-white/50 
                   rounded-2xl rounded-bl-md px-5 py-4 shadow-md"
      >
        <div className="flex items-center gap-3">
          <Loader2 className="w-5 h-5 text-slate-400 animate-spin" />
          <div className="flex gap-1">
            <span 
              className="w-2 h-2 rounded-full bg-slate-300 animate-bounce"
              style={{ animationDelay: '0ms' }}
            />
            <span 
              className="w-2 h-2 rounded-full bg-slate-300 animate-bounce"
              style={{ animationDelay: '150ms' }}
            />
            <span 
              className="w-2 h-2 rounded-full bg-slate-300 animate-bounce"
              style={{ animationDelay: '300ms' }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default MessageBubble;

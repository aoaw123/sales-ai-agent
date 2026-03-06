/**
 * AI 销售助手 - 主应用组件
 * 
 * 这是一个基于 React + TypeScript + Tailwind CSS 构建的现代化聊天界面
 * 功能包括：
 * - 左侧边栏显示历史会话和 Logo
 * - 右侧聊天区域（消息列表 + 输入框）
 * - 支持 Markdown 渲染
 * - 支持文件下载（Excel 报价单等）
 * - 与 FastAPI 后端对接
 */

import { useState, useRef, useEffect } from 'react';
import type { Message, ChatRequest, ChatResponse, DocumentFile } from './types';
import { 
  Send, 
  MessageSquare, 
  Plus, 
  Bot, 
  User, 
  Loader2,
  Trash2,
  Menu,
  X,
  Download,
  FileText,
  FileSpreadsheet
} from 'lucide-react';

/**
 * API 基础配置
 * BACKEND_URL: 后端服务地址
 * DOCUMENTS_URL: 文件下载基础地址
 * SESSION_ID: 当前会话标识（实际应用中可动态生成或使用用户 ID）
 */
const BACKEND_URL = 'http://127.0.0.1:8000/api/v1/chat';
const DOCUMENTS_URL = 'http://127.0.0.1:8000/api/v1/docs/documents';
const SESSION_ID = 'web_user_001';

/**
 * 安全的类型检查工具函数
 */

/** 检查值是否为非空字符串 */
const isNonEmptyString = (value: unknown): value is string => {
  return typeof value === 'string' && value.length > 0;
};

/** 检查值是否为有效的数组 */
const isValidArray = <T,>(value: unknown): value is T[] => {
  return Array.isArray(value) && value.length > 0;
};

/** 安全地获取字符串值，如果无效则返回默认值 */
const safeString = (value: unknown, defaultValue = ''): string => {
  return isNonEmptyString(value) ? value : defaultValue;
};

/**
 * 简单的 Markdown 渲染函数
 * 将 Markdown 文本转换为 HTML（简化版，支持常用语法）
 * 添加了空值安全检查
 */
const renderMarkdown = (text: unknown): string => {
  // 防御性编程：确保输入是字符串
  if (!isNonEmptyString(text)) {
    return '';
  }
  
  try {
    let html = text
      // 转义 HTML 特殊字符，防止 XSS
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      
      // 代码块 (```code```)
      .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
      
      // 行内代码 (`code`)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      
      // 标题 (# ## ###)
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      
      // 粗体 (**text**)
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      
      // 斜体 (*text*)
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      
      // 无序列表 (- item)
      .replace(/^- (.*$)/gim, '<li>$1</li>')
      
      // 有序列表 (1. item)
      .replace(/^\d+\. (.*$)/gim, '<li>$1</li>')
      
      // 链接 [text](url)
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
      
      // 引用 (> text)
      .replace(/^&gt; (.*$)/gim, '<blockquote>$1</blockquote>')
      
      // 水平线 (---)
      .replace(/^---$/gim, '<hr>')
      
      // 换行符处理
      .replace(/\n/g, '<br>');
    
    return html;
  } catch (error) {
    console.error('Markdown 渲染错误:', error);
    // 如果渲染失败，返回转义后的原始文本
    return isNonEmptyString(text) 
      ? text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      : '';
  }
};

/**
 * 从消息内容中提取文件名（备用方案）
 * 匹配格式："报价单_xxx.xlsx" 或 "XXX.xlsx"
 * 支持中文字符：\u4e00-\u9fa5 匹配常用汉字
 * 添加了空值安全检查和 try-catch
 */
const extractFilenamesFromText = (text: unknown): string[] => {
  // 防御性编程：确保输入是字符串
  if (!isNonEmptyString(text)) {
    return [];
  }
  
  try {
    const filenames: string[] = [];
    
    // 定义文件名中允许的字符：
    // [\w\u4e00-\u9fa5-] = 英文字母数字下划线 + 中文字符 + 连字符
    // 注意：\w 等价于 [A-Za-z0-9_]，不包含中文
    const filenameChars = '[\\w\\u4e00-\u9fa5\\-]+';
    
    // 匹配常见的文件名格式（支持中文）
    const patterns = [
      // 匹配"报价单_xxx.xlsx"格式（支持中文前缀）
      new RegExp(`报价单_${filenameChars}\\.(xlsx|xls|pdf|doc|docx)`, 'gi'),
      // 匹配"xxx_20260101_120000.xlsx"格式（支持中文主体）
      new RegExp(`${filenameChars}_\\d{8}_\\d{6}\\.(xlsx|xls|pdf|doc|docx)`, 'gi'),
      // 通用匹配：任意由中文、英文、数字、下划线、连字符组成的文件名
      new RegExp(`\\b${filenameChars}\\.(xlsx|xls|pdf|doc|docx)\\b`, 'gi')
    ];
    
    for (const pattern of patterns) {
      const matches = text.match(pattern);
      if (matches && Array.isArray(matches)) {
        filenames.push(...matches);
      }
    }
    
    // 严格去重：使用 Set 去除完全相同的文件名
    // 同时过滤掉可能是部分匹配的空字符串或无效名称
    const uniqueFilenames = Array.from(new Set(filenames))
      .filter(name => isNonEmptyString(name) && name.includes('.'));
    
    // 额外去重：如果一个文件名是另一个文件名的子串，保留较长的那个
    // 例如：如果同时匹配到 "报价单_客户.xlsx" 和 "客户.xlsx"，保留完整的 "报价单_客户.xlsx"
    const cleanedFilenames: string[] = [];
    for (const name of uniqueFilenames) {
      // 检查是否已经被更长的文件名包含
      const isSubstring = uniqueFilenames.some(other => 
        other !== name && other.includes(name)
      );
      if (!isSubstring) {
        cleanedFilenames.push(name);
      }
    }
    
    return cleanedFilenames;
  } catch (error) {
    console.error('提取文件名时出错:', error);
    return [];
  }
};

/**
 * 获取文件图标组件
 * 添加了空值安全检查
 */
const getFileIcon = (filename: unknown) => {
  // 防御性编程：确保文件名是有效字符串
  if (!isNonEmptyString(filename)) {
    return <FileText className="w-5 h-5 text-gray-400" />;
  }
  
  try {
    const extension = filename.split('.').pop()?.toLowerCase();
    switch (extension) {
      case 'xlsx':
      case 'xls':
        return <FileSpreadsheet className="w-5 h-5 text-green-400" />;
      case 'pdf':
        return <FileText className="w-5 h-5 text-red-400" />;
      case 'doc':
      case 'docx':
        return <FileText className="w-5 h-5 text-blue-400" />;
      default:
        return <FileText className="w-5 h-5 text-gray-400" />;
    }
  } catch (error) {
    console.error('获取文件图标时出错:', error);
    return <FileText className="w-5 h-5 text-gray-400" />;
  }
};

/**
 * 安全地处理文档列表
 * 将各种可能的输入格式转换为标准化的 DocumentFile 数组
 */
const normalizeDocuments = (documents: unknown): DocumentFile[] | undefined => {
  // 如果不是数组，直接返回 undefined
  if (!Array.isArray(documents)) {
    return undefined;
  }
  
  // 过滤并映射为有效的 DocumentFile 对象
  const validDocs = documents
    .filter((doc): doc is { filename?: unknown } => {
      // 确保每个元素是对象且有 filename 属性
      return doc !== null && typeof doc === 'object' && 'filename' in doc;
    })
    .map((doc) => ({
      filename: safeString(doc.filename)
    }))
    .filter((doc) => doc.filename.length > 0); // 过滤掉空文件名的
  
  return validDocs.length > 0 ? validDocs : undefined;
};

/**
 * 文件下载卡片组件
 * 独立的组件便于管理和错误隔离
 */
interface FileDownloadCardProps {
  filename: string;
  onDownload: (filename: string) => void;
  index: number;
}

const FileDownloadCard: React.FC<FileDownloadCardProps> = ({ filename, onDownload, index }) => {
  // 防御性编程：如果文件名无效，不渲染任何内容
  if (!isNonEmptyString(filename)) {
    return null;
  }
  
  return (
    <div
      key={index}
      onClick={() => onDownload(filename)}
      className="group relative overflow-hidden cursor-pointer"
    >
      {/* 主卡片容器 */}
      <div className="relative flex items-center gap-3 px-4 py-3 
                      bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900
                      border border-cyan-500/30 rounded-xl
                      shadow-[0_0_20px_rgba(6,182,212,0.15)]
                      hover:shadow-[0_0_30px_rgba(6,182,212,0.3)]
                      hover:border-cyan-400/50
                      transition-all duration-300 ease-out
                      transform hover:scale-[1.02]
                      min-w-[240px]">
        
        {/* 发光边框效果 */}
        <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-cyan-500/10 via-purple-500/10 to-cyan-500/10 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        
        {/* 左侧文件图标 */}
        <div className="relative flex-shrink-0 w-10 h-10 
                        flex items-center justify-center
                        rounded-lg bg-gradient-to-br from-cyan-500/20 to-purple-500/20
                        border border-cyan-400/30
                        group-hover:from-cyan-500/30 group-hover:to-purple-500/30
                        transition-all duration-300">
          {getFileIcon(filename)}
        </div>
        
        {/* 中间文件名信息 */}
        <div className="relative flex-1 min-w-0">
          <p className="text-xs text-cyan-400 font-medium tracking-wider uppercase mb-0.5">
            生成的文档
          </p>
          <p className="text-sm text-gray-200 font-medium truncate
                        group-hover:text-white transition-colors">
            {filename}
          </p>
        </div>
        
        {/* 右侧下载按钮 */}
        <div className="relative flex-shrink-0">
          <div className="flex items-center justify-center w-8 h-8
                          rounded-full bg-cyan-500/20
                          border border-cyan-400/40
                          group-hover:bg-cyan-500 group-hover:border-cyan-400
                          transition-all duration-300">
            <Download className="w-4 h-4 text-cyan-400 group-hover:text-white transition-colors" />
          </div>
        </div>
        
        {/* 角落装饰 */}
        <div className="absolute top-0 right-0 w-16 h-16 
                        bg-gradient-to-bl from-cyan-500/10 to-transparent
                        rounded-tr-xl pointer-events-none" />
      </div>
      
      {/* 底部光效 */}
      <div className="absolute bottom-0 left-4 right-4 h-px 
                      bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent
                      group-hover:via-cyan-400 transition-colors duration-300" />
    </div>
  );
};

/**
 * 消息气泡组件
 * 独立封装便于错误隔离
 */
interface MessageBubbleProps {
  message: Message;
  onDownloadFile: (filename: string) => void;
  formatTime: (date: Date) => string;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onDownloadFile, formatTime }) => {
  // 防御性编程：确保消息对象有效
  if (!message || typeof message !== 'object') {
    console.warn('MessageBubble 收到无效的消息对象:', message);
    return null;
  }
  
  const role = message.role === 'user' ? 'user' : 'assistant';
  const content = safeString(message.content, '【空消息】');
  const timestamp = message.timestamp instanceof Date ? message.timestamp : new Date();
  
  // 安全地处理文档列表
  const documents = normalizeDocuments(message.documents);
  const hasDocuments = isValidArray(documents);
  
  return (
    <div
      className={`
        flex gap-3 max-w-4xl mx-auto
        ${role === 'user' ? 'flex-row-reverse' : 'flex-row'}
      `}
    >
      {/* 头像 */}
      <div
        className={`
          w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0
          ${role === 'user' 
            ? 'bg-blue-600' 
            : 'bg-gradient-to-br from-blue-500 to-purple-600'}
        `}
      >
        {role === 'user' ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <Bot className="w-4 h-4 text-white" />
        )}
      </div>
      
      {/* 消息内容 */}
      <div className={`flex flex-col ${role === 'user' ? 'items-end' : 'items-start'} max-w-[calc(100vw-6rem)] lg:max-w-2xl`}>
        {/* 气泡 */}
        <div
          className={`
            px-4 py-2.5 rounded-2xl
            ${role === 'user'
              ? 'bg-blue-600 text-white rounded-br-md'
              : 'bg-white border border-gray-200 text-gray-800 rounded-bl-md shadow-sm'}
          `}
        >
          {/* AI 消息使用 Markdown 渲染 */}
          {role === 'assistant' ? (
            <div
              className="markdown-content text-sm leading-relaxed"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
            />
          ) : (
            <p className="text-sm leading-relaxed whitespace-pre-wrap">
              {content}
            </p>
          )}
        </div>
        
        {/* 文件下载卡片 - 科技感设计 */}
        {hasDocuments && (
          <div className="mt-3 space-y-2">
            {documents!.map((doc, index) => (
              <FileDownloadCard
                key={`${doc.filename}-${index}`}
                filename={doc.filename}
                onDownload={onDownloadFile}
                index={index}
              />
            ))}
          </div>
        )}
        
        {/* 时间戳 */}
        <span className="text-xs text-gray-400 mt-1 px-1">
          {formatTime(timestamp)}
        </span>
      </div>
    </div>
  );
};

function App() {
  // ==================== 状态管理 ====================
  
  /**
   * messages: 当前聊天会话中的所有消息列表
   * 每条消息包含 id, role(用户/AI), content, timestamp, documents
   */
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: '你好！我是你的 AI 销售助手。有什么我可以帮你的吗？',
      timestamp: new Date(),
    },
  ]);
  
  /**
   * inputValue: 输入框当前值
   */
  const [inputValue, setInputValue] = useState('');
  
  /**
   * isLoading: 是否正在等待 AI 回复
   * 用于显示加载动画和禁用发送按钮
   */
  const [isLoading, setIsLoading] = useState(false);
  
  /**
   * sidebarOpen: 移动端侧边栏开关状态
   */
  const [sidebarOpen, setSidebarOpen] = useState(false);
  
  /**
   * chatSessions: 历史会话列表（简化版，实际可从 localStorage 或后端加载）
   */
  const [chatSessions] = useState([
    { id: '1', title: '产品咨询对话', date: '今天' },
    { id: '2', title: '报价方案讨论', date: '昨天' },
    { id: '3', title: '客户需求分析', date: '3天前' },
  ]);

  // ==================== Refs ====================
  
  /**
   * messagesEndRef: 用于自动滚动到最新消息
   * 每次消息更新后，滚动到底部
   */
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  /**
   * textareaRef: 输入框引用，用于自动调整高度
   */
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // ==================== 副作用 ====================
  
  /**
   * 自动滚动到最新消息
   * 当 messages 数组变化时触发
   */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  /**
   * 自动调整输入框高度
   * 根据内容行数动态调整，最大高度限制为 150px
   */
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  }, [inputValue]);

  // ==================== 事件处理函数 ====================
  
  /**
   * 触发文件下载
   * 通过创建临时 <a> 标签触发浏览器下载行为
   */
  const handleDownloadFile = (filename: string) => {
    // 防御性编程：确保文件名有效
    if (!isNonEmptyString(filename)) {
      console.error('无效的文件名:', filename);
      return;
    }
    
    try {
      const downloadUrl = `${DOCUMENTS_URL}/${encodeURIComponent(filename)}`;
      
      // 创建临时 <a> 标签触发下载
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename; // 指定下载文件名
      link.target = '_blank';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      console.error('下载文件时出错:', error);
      alert('下载文件失败，请重试');
    }
  };

  /**
   * 发送消息到后端 API
   * 1. 将用户消息添加到本地消息列表
   * 2. 调用后端 API
   * 3. 将 AI 回复添加到消息列表（包含 documents 字段）
   */
  const handleSendMessage = async () => {
    // 验证输入：不能为空或仅空白字符
    if (!inputValue.trim() || isLoading) return;
    
    const userMessage = inputValue.trim();
    setInputValue(''); // 清空输入框
    
    // 重置输入框高度
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    
    // 创建用户消息对象
    const newUserMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: userMessage,
      timestamp: new Date(),
    };
    
    // 更新消息列表（添加用户消息）
    setMessages((prev) => [...prev, newUserMessage]);
    
    // 设置加载状态
    setIsLoading(true);
    
    try {
      // 构建请求体
      const requestBody: ChatRequest = {
        session_id: SESSION_ID,
        message: userMessage,
      };
      
      // 发送 POST 请求到后端
      const response = await fetch(BACKEND_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });
      
      // 检查响应状态
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      // 解析响应 JSON
      const data: ChatResponse = await response.json();
      
      // 安全地获取回复文本
      const replyText = safeString(data.reply, '抱歉，我暂时无法回答这个问题。');
      
      // 处理文件列表：优先使用后端返回的 documents，否则从文本中提取
      let documents: DocumentFile[] | undefined = normalizeDocuments(data.documents);
      
      // 如果后端没有返回有效的 documents，尝试从 reply 文本中提取文件名
      if (!documents) {
        const extractedFilenames = extractFilenamesFromText(replyText);
        if (extractedFilenames.length > 0) {
          documents = extractedFilenames.map(filename => ({ filename }));
        }
      }
      
      // 创建 AI 回复消息对象
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: replyText,
        timestamp: new Date(),
        documents: documents,
      };
      
      // 更新消息列表（添加 AI 回复）
      setMessages((prev) => [...prev, aiMessage]);
      
    } catch (error) {
      // 错误处理：显示错误提示
      console.error('发送消息失败:', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '抱歉，连接服务器出现问题，请稍后再试。',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      // 无论成功失败，都关闭加载状态
      setIsLoading(false);
    }
  };

  /**
   * 处理键盘事件
   * Enter: 发送消息
   * Shift+Enter: 换行
   */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  /**
   * 清空当前对话
   * 重置消息列表为初始状态
   */
  const handleClearChat = () => {
    if (confirm('确定要清空当前对话吗？')) {
      setMessages([
        {
          id: 'welcome',
          role: 'assistant',
          content: '对话已清空。我是你的 AI 销售助手，有什么可以帮你的吗？',
          timestamp: new Date(),
        },
      ]);
    }
  };

  /**
   * 格式化时间显示
   * 将 Date 对象转换为 HH:mm 格式
   */
  const formatTime = (date: Date): string => {
    try {
      if (!(date instanceof Date) || isNaN(date.getTime())) {
        date = new Date();
      }
      return date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch (error) {
      console.error('格式化时间时出错:', error);
      return '--:--';
    }
  };

  // ==================== 渲染 ====================
  
  return (
    <div className="flex h-screen bg-gray-50">
      
      {/* ==================== 左侧边栏 ==================== */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200 
          transform transition-transform duration-300 ease-in-out
          lg:relative lg:transform-none
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        {/* 侧边栏头部：Logo */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            {/* AI 助手 Logo 图标 */}
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <span className="font-semibold text-gray-800">AI 销售助手</span>
          </div>
          {/* 移动端关闭按钮 */}
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-1 hover:bg-gray-100 rounded"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>
        
        {/* 新建对话按钮 */}
        <div className="p-4">
          <button
            onClick={handleClearChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 
                       bg-blue-600 hover:bg-blue-700 text-white rounded-lg 
                       transition-colors duration-200"
          >
            <Plus className="w-4 h-4" />
            <span>新建对话</span>
          </button>
        </div>
        
        {/* 历史会话列表 */}
        <div className="px-4 pb-4">
          <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
            历史会话
          </h3>
          <div className="space-y-1">
            {chatSessions.map((session) => (
              <button
                key={session.id}
                className="w-full flex items-center gap-3 px-3 py-2 
                           text-left text-sm text-gray-700 
                           hover:bg-gray-100 rounded-lg transition-colors"
              >
                <MessageSquare className="w-4 h-4 text-gray-400" />
                <div className="flex-1 min-w-0">
                  <p className="truncate">{session.title}</p>
                  <p className="text-xs text-gray-400">{session.date}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
        
        {/* 侧边栏底部：清空对话按钮 */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-200">
          <button
            onClick={handleClearChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 
                       text-red-600 hover:bg-red-50 rounded-lg 
                       transition-colors duration-200"
          >
            <Trash2 className="w-4 h-4" />
            <span>清空对话</span>
          </button>
        </div>
      </aside>

      {/* ==================== 主聊天区域 ==================== */}
      <main className="flex-1 flex flex-col min-w-0">
        
        {/* 顶部导航栏（移动端显示菜单按钮） */}
        <header className="flex items-center justify-between h-16 px-4 border-b border-gray-200 bg-white lg:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <Menu className="w-5 h-5 text-gray-600" />
          </button>
          <span className="font-semibold text-gray-800">AI 销售助手</span>
          <div className="w-10" /> {/* 占位保持居中 */}
        </header>

        {/* 消息列表区域 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((message, index) => (
            <MessageBubble
              key={message?.id || `msg-${index}`}
              message={message}
              onDownloadFile={handleDownloadFile}
              formatTime={formatTime}
            />
          ))}
          
          {/* 加载状态指示器 */}
          {isLoading && (
            <div className="flex gap-3 max-w-4xl mx-auto">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
                <div className="flex items-center gap-2 text-gray-500">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">正在思考...</span>
                </div>
              </div>
            </div>
          )}
          
          {/* 滚动锚点 */}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入区域 */}
        <div className="border-t border-gray-200 bg-white p-4">
          <div className="max-w-4xl mx-auto">
            <div className="relative flex items-end gap-2 bg-gray-100 rounded-2xl p-2">
              {/* 多行文本输入框 */}
              <textarea
                ref={textareaRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入消息...（Enter 发送，Shift+Enter 换行）"
                disabled={isLoading}
                rows={1}
                className="
                  flex-1 resize-none bg-transparent border-0 outline-none 
                  px-3 py-2 text-gray-800 placeholder-gray-400
                  disabled:opacity-50 disabled:cursor-not-allowed
                  min-h-[40px] max-h-[150px]
                "
              />
              
              {/* 发送按钮 */}
              <button
                onClick={handleSendMessage}
                disabled={!inputValue.trim() || isLoading}
                className={`
                  flex-shrink-0 p-2 rounded-xl transition-all duration-200
                  ${inputValue.trim() && !isLoading
                    ? 'bg-blue-600 hover:bg-blue-700 text-white'
                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'}
                `}
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
            
            {/* 底部提示文字 */}
            <p className="text-center text-xs text-gray-400 mt-2">
              AI 生成的内容仅供参考，请核实重要信息
            </p>
          </div>
        </div>
      </main>

      {/* 移动端侧边栏遮罩 */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
}

export default App;

/**
 * AI 销售助手 - 主应用组件（重构版）
 * 
 * 技术栈：React + TypeScript + Tailwind CSS
 * 重构亮点：
 * - 集成 MessageBubble 组件（防御性 + 科技感下载）
 * - 正确处理后端返回的 documents
 * - 优雅的错误处理
 */

import { useState, useRef, useEffect } from 'react';
import { MessageBubble, LoadingBubble } from './components/MessageBubble';
import type { Message, ChatRequest, ChatResponse, DocumentInfo } from './types';
import { 
  Send, 
  MessageSquare, 
  Plus, 
  Bot, 
  Trash2,
  Menu,
  X,
  Sparkles
} from 'lucide-react';

/**
 * API 基础配置
 */
const BACKEND_URL = 'http://127.0.0.1:8000/api/v1/chat';
const SESSION_ID = 'web_user_001';

/**
 * 从后端响应提取文档列表（防御性）
 */
const extractDocumentsFromResponse = (data: ChatResponse): DocumentInfo[] => {
  // 防御性检查
  if (!data || typeof data !== 'object') {
    return [];
  }

  const docs: DocumentInfo[] = [];
  const seenFilenames = new Set<string>(); // 去重

  // 1. 从 documents 数组提取
  if (data.documents && Array.isArray(data.documents)) {
    data.documents.forEach((doc) => {
      if (doc && typeof doc === 'object' && doc.filename) {
        const filename = String(doc.filename).trim();
        if (filename && !seenFilenames.has(filename)) {
          seenFilenames.add(filename);
          docs.push({
            filename,
            path: doc.path || `/output/${filename}`,
            type: doc.type || filename.split('.').pop() || 'unknown',
            size: doc.size,
          });
        }
      }
    });
  }

  // 2. 从 reply 文本中提取（兜底）
  // 关键：支持中文的正则 [一-龥]
  const content = data.reply;
  if (content && typeof content === 'string') {
    const filenameRegex = /[\w\-\u4e00-\u9fa5]+\.(?:xlsx|xls|docx|doc|pdf|txt|md|pptx)/gi;
    const matches = content.match(filenameRegex);
    
    if (matches && Array.isArray(matches)) {
      matches.forEach((filename) => {
        const cleanFilename = filename.trim();
        if (cleanFilename && !seenFilenames.has(cleanFilename)) {
          seenFilenames.add(cleanFilename);
          docs.push({
            filename: cleanFilename,
            path: `/output/${cleanFilename}`,
            type: cleanFilename.split('.').pop() || 'unknown',
          });
        }
      });
    }
  }

  return docs;
};

function App() {
  // ==================== 状态管理 ====================
  
  /**
   * messages: 当前聊天会话中的所有消息列表
   */
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: '你好！我是你的 AI 销售助手。我可以帮你生成报价单、提案书，或解答产品相关问题。有什么我可以帮你的吗？',
      timestamp: new Date(),
    },
  ]);
  
  /**
   * inputValue: 输入框当前值
   */
  const [inputValue, setInputValue] = useState('');
  
  /**
   * isLoading: 是否正在等待 AI 回复
   */
  const [isLoading, setIsLoading] = useState(false);
  
  /**
   * sidebarOpen: 移动端侧边栏开关状态
   */
  const [sidebarOpen, setSidebarOpen] = useState(false);
  
  /**
   * chatSessions: 历史会话列表
   */
  const [chatSessions] = useState([
    { id: '1', title: '产品咨询对话', date: '今天' },
    { id: '2', title: '报价方案讨论', date: '昨天' },
    { id: '3', title: '客户需求分析', date: '3天前' },
  ]);

  // ==================== Refs ====================
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // ==================== 副作用 ====================
  
  /**
   * 自动滚动到最新消息
   */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  /**
   * 自动调整输入框高度
   */
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  }, [inputValue]);

  // ==================== 事件处理函数 ====================
  
  /**
   * 发送消息到后端 API
   */
  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;
    
    const userMessage = inputValue.trim();
    setInputValue('');
    
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
      
      // 提取文档列表
      const documents = extractDocumentsFromResponse(data);
      
      // 创建 AI 回复消息对象
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.reply || '抱歉，我暂时无法回答这个问题。',
        timestamp: new Date(),
        documents: documents.length > 0 ? documents : undefined,
      };
      
      // 更新消息列表（添加 AI 回复）
      setMessages((prev) => [...prev, aiMessage]);
      
    } catch (error) {
      console.error('发送消息失败:', error);
      
      // 错误消息
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '抱歉，连接服务器出现问题，请稍后再试。如果问题持续，请联系技术支持。',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * 处理键盘事件
   */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  /**
   * 清空当前对话
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

  // ==================== 渲染 ====================
  
  return (
    <div className="flex h-screen bg-slate-50">
      
      {/* ==================== 左侧边栏 ==================== */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-50 w-72 
          transform transition-transform duration-300 ease-in-out
          lg:relative lg:transform-none
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
        style={{
          background: 'linear-gradient(180deg, #0f172a 0%, #1e293b 100%)',
          borderRight: '1px solid rgba(56, 189, 248, 0.1)',
        }}
      >
        {/* 侧边栏头部：Logo */}
        <div className="flex items-center justify-between h-16 px-5 border-b border-slate-700/50">
          <div className="flex items-center gap-3">
            {/* AI 助手 Logo 图标 */}
            <div 
              className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{
                background: 'linear-gradient(135deg, #38bdf8 0%, #6366f1 100%)',
                boxShadow: '0 0 20px rgba(56, 189, 248, 0.3)',
              }}
            >
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-white text-lg">智销云</span>
              <p className="text-xs text-slate-400">AI 销售助手</p>
            </div>
          </div>
          {/* 移动端关闭按钮 */}
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>
        
        {/* 新建对话按钮 */}
        <div className="p-4">
          <button
            onClick={handleClearChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 
                       rounded-xl font-medium text-white
                       transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
            style={{
              background: 'linear-gradient(135deg, #38bdf8 0%, #0ea5e9 100%)',
              boxShadow: '0 4px 20px rgba(56, 189, 248, 0.3)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow = '0 6px 25px rgba(56, 189, 248, 0.4)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow = '0 4px 20px rgba(56, 189, 248, 0.3)';
            }}
          >
            <Plus className="w-5 h-5" />
            <span>新建对话</span>
          </button>
        </div>
        
        {/* 历史会话列表 */}
        <div className="px-4 pb-4">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 px-2">
            历史会话
          </h3>
          <div className="space-y-1">
            {chatSessions.map((session) => (
              <button
                key={session.id}
                className="w-full flex items-center gap-3 px-3 py-3 
                           text-left rounded-xl transition-all duration-200
                           hover:bg-slate-700/50 group"
              >
                <MessageSquare className="w-4 h-4 text-slate-500 group-hover:text-sky-400 transition-colors" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-300 group-hover:text-white truncate transition-colors">
                    {session.title}
                  </p>
                  <p className="text-xs text-slate-500">{session.date}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
        
        {/* 侧边栏底部 */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-slate-700/50">
          <button
            onClick={handleClearChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 
                       text-slate-400 hover:text-red-400 
                       hover:bg-red-500/10 rounded-xl
                       transition-all duration-200"
          >
            <Trash2 className="w-4 h-4" />
            <span className="text-sm">清空对话</span>
          </button>
        </div>
      </aside>

      {/* ==================== 主聊天区域 ==================== */}
      <main className="flex-1 flex flex-col min-w-0 bg-gradient-to-br from-slate-50 to-slate-100">
        
        {/* 顶部导航栏（移动端） */}
        <header 
          className="flex items-center justify-between h-16 px-4 border-b lg:hidden"
          style={{
            background: 'rgba(255, 255, 255, 0.8)',
            backdropFilter: 'blur(10px)',
            borderColor: 'rgba(226, 232, 240, 0.8)',
          }}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
          >
            <Menu className="w-5 h-5 text-slate-600" />
          </button>
          <div className="flex items-center gap-2">
            <div 
              className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{
                background: 'linear-gradient(135deg, #38bdf8 0%, #6366f1 100%)',
              }}
            >
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold text-slate-800">智销云</span>
          </div>
          <div className="w-10" />
        </header>

        {/* 消息列表区域 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {messages.map((message) => (
            <MessageBubble 
              key={message.id} 
              message={message} 
            />
          ))}
          
          {/* 加载状态 */}
          {isLoading && <LoadingBubble />}
          
          {/* 滚动锚点 */}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入区域 */}
        <div 
          className="border-t px-4 py-4"
          style={{
            background: 'rgba(255, 255, 255, 0.9)',
            backdropFilter: 'blur(10px)',
            borderColor: 'rgba(226, 232, 240, 0.8)',
          }}
        >
          <div className="max-w-4xl mx-auto">
            <div 
              className="relative flex items-end gap-2 p-2 rounded-2xl"
              style={{
                background: 'rgba(241, 245, 249, 0.8)',
                border: '1px solid rgba(226, 232, 240, 0.8)',
              }}
            >
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
                  px-4 py-3 text-slate-700 placeholder-slate-400
                  disabled:opacity-50 disabled:cursor-not-allowed
                  min-h-[48px] max-h-[150px]
                "
              />
              
              {/* 发送按钮 */}
              <button
                onClick={handleSendMessage}
                disabled={!inputValue.trim() || isLoading}
                className={`
                  flex-shrink-0 p-3 rounded-xl transition-all duration-200
                  disabled:opacity-40 disabled:cursor-not-allowed
                  ${inputValue.trim() && !isLoading
                    ? 'hover:scale-105 active:scale-95'
                    : ''}
                `}
                style={{
                  background: inputValue.trim() && !isLoading
                    ? 'linear-gradient(135deg, #38bdf8 0%, #0ea5e9 100%)'
                    : '#cbd5e1',
                  boxShadow: inputValue.trim() && !isLoading
                    ? '0 4px 15px rgba(56, 189, 248, 0.3)'
                    : 'none',
                }}
              >
                <Send className={`w-5 h-5 ${inputValue.trim() && !isLoading ? 'text-white' : 'text-slate-500'}`} />
              </button>
            </div>
            
            {/* 底部提示文字 */}
            <p className="text-center text-xs text-slate-400 mt-2">
              AI 生成的内容仅供参考，请核实重要信息
            </p>
          </div>
        </div>
      </main>

      {/* 移动端侧边栏遮罩 */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
}

export default App;

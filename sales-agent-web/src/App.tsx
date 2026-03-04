/**
 * AI 销售助手 - 主应用组件
 * 
 * 这是一个基于 React + TypeScript + Tailwind CSS 构建的现代化聊天界面
 * 功能包括：
 * - 左侧边栏显示历史会话和 Logo
 * - 右侧聊天区域（消息列表 + 输入框）
 * - 支持 Markdown 渲染
 * - 与 FastAPI 后端对接
 */

import { useState, useRef, useEffect } from 'react';
import type { Message, ChatRequest, ChatResponse } from './types';
import { 
  Send, 
  MessageSquare, 
  Plus, 
  Bot, 
  User, 
  Loader2,
  Trash2,
  Menu,
  X
} from 'lucide-react';

/**
 * API 基础配置
 * BACKEND_URL: 后端服务地址
 * SESSION_ID: 当前会话标识（实际应用中可动态生成或使用用户 ID）
 */
const BACKEND_URL = 'http://127.0.0.1:8000/api/v1/chat';
const SESSION_ID = 'web_user_001';

/**
 * 简单的 Markdown 渲染函数
 * 将 Markdown 文本转换为 HTML（简化版，支持常用语法）
 */
const renderMarkdown = (text: string): string => {
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
};

function App() {
  // ==================== 状态管理 ====================
  
  /**
   * messages: 当前聊天会话中的所有消息列表
   * 每条消息包含 id, role(用户/AI), content, timestamp
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
   * 发送消息到后端 API
   * 1. 将用户消息添加到本地消息列表
   * 2. 调用后端 API
   * 3. 将 AI 回复添加到消息列表
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
      
      // 创建 AI 回复消息对象
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.reply || '抱歉，我暂时无法回答这个问题。',
        timestamp: new Date(),
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
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
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
          {messages.map((message) => (
            <div
              key={message.id}
              className={`
                flex gap-3 max-w-4xl mx-auto
                ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}
              `}
            >
              {/* 头像 */}
              <div
                className={`
                  w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0
                  ${message.role === 'user' 
                    ? 'bg-blue-600' 
                    : 'bg-gradient-to-br from-blue-500 to-purple-600'}
                `}
              >
                {message.role === 'user' ? (
                  <User className="w-4 h-4 text-white" />
                ) : (
                  <Bot className="w-4 h-4 text-white" />
                )}
              </div>
              
              {/* 消息内容 */}
              <div className={`flex flex-col ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
                {/* 气泡 */}
                <div
                  className={`
                    px-4 py-2.5 rounded-2xl max-w-[calc(100vw-6rem)] lg:max-w-2xl
                    ${message.role === 'user'
                      ? 'bg-blue-600 text-white rounded-br-md'
                      : 'bg-white border border-gray-200 text-gray-800 rounded-bl-md shadow-sm'}
                  `}
                >
                  {/* AI 消息使用 Markdown 渲染 */}
                  {message.role === 'assistant' ? (
                    <div
                      className="markdown-content text-sm leading-relaxed"
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
                    />
                  ) : (
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">
                      {message.content}
                    </p>
                  )}
                </div>
                {/* 时间戳 */}
                <span className="text-xs text-gray-400 mt-1 px-1">
                  {formatTime(message.timestamp)}
                </span>
              </div>
            </div>
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

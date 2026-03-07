/**
 * 类型定义文件
 * 定义聊天应用中使用的主要数据类型
 */

/**
 * 文档信息类型
 * @property filename - 文件名
 * @property path - 文件路径
 * @property type - 文档类型
 * @property size - 文件大小
 */
export interface DocumentInfo {
  filename: string;
  path: string;
  type: string;
  size?: number;
}

/**
 * 单条消息的类型定义
 * @property id - 消息唯一标识符
 * @property role - 发送者角色：'user' 表示用户，'assistant' 表示 AI
 * @property content - 消息内容文本
 * @property timestamp - 消息发送时间戳
 * @property documents - 消息关联的文档列表（可选）
 */
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  documents?: DocumentInfo[];
}

/**
 * API 请求体类型
 * @property session_id - 会话 ID，用于区分不同用户的对话
 * @property message - 用户发送的消息内容
 * @property context - 业务上下文（可选）
 */
export interface ChatRequest {
  session_id: string;
  message: string;
  context?: Record<string, unknown>;
}

/**
 * API 响应体类型
 * @property reply - AI 助手的回复内容
 * @property session_id - 会话 ID（后端可能返回相同的或新的）
 * @property status - 响应状态
 * @property documents - 生成的文档列表
 * @property suggested_actions - 建议的操作
 * @property intent - 识别的意图
 */
export interface ChatResponse {
  reply: string;
  session_id?: string;
  status?: string;
  documents?: DocumentInfo[];
  suggested_actions?: string[];
  intent?: string;
}

/**
 * 会话历史记录类型
 * @property id - 会话唯一标识
 * @property title - 会话标题（可由第一条用户消息生成）
 * @property messages - 该会话中的消息列表
 * @property createdAt - 会话创建时间
 * @property updatedAt - 最后更新时间
 */
export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

/**
 * 下载按钮组件属性
 * @property filename - 文件名
 * @property onDownload - 下载回调函数
 * @property className - 额外的 CSS 类名
 */
export interface DownloadButtonProps {
  filename: string;
  onDownload?: (filename: string) => void;
  className?: string;
}

/**
 * 消息气泡组件属性
 * @property message - 消息对象
 * @property isLoading - 是否显示加载状态
 */
export interface MessageBubbleProps {
  message: Message;
  isLoading?: boolean;
}

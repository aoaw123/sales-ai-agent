/**
 * 类型定义文件
 * 定义聊天应用中使用的主要数据类型
 */

/**
 * 文档文件类型定义
 * @property filename - 文件名
 * @property url - 文件下载地址（可选，后端返回时可能包含）
 */
export interface DocumentFile {
  filename: string;
  url?: string;
}

/**
 * 单条消息的类型定义
 * @property id - 消息唯一标识符
 * @property role - 发送者角色：'user' 表示用户，'assistant' 表示 AI
 * @property content - 消息内容文本
 * @property timestamp - 消息发送时间戳
 * @property documents - 附带生成的文件列表（如 Excel 报价单）
 */
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  documents?: DocumentFile[];
}

/**
 * API 请求体类型
 * @property session_id - 会话 ID，用于区分不同用户的对话
 * @property message - 用户发送的消息内容
 */
export interface ChatRequest {
  session_id: string;
  message: string;
}

/**
 * API 响应体类型
 * @property reply - AI 助手的回复内容
 * @property session_id - 会话 ID（后端可能返回相同的或新的）
 * @property status - 响应状态
 * @property documents - 生成的文件列表（如 Excel 报价单）
 */
export interface ChatResponse {
  reply: string;
  session_id?: string;
  status?: string;
  documents?: DocumentFile[];
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

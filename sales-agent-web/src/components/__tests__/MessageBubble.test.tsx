/**
 * MessageBubble 组件测试
 * 
 * 测试要点：
 * - 防御性渲染（无效 message 不渲染）
 * - 中文文件名提取 [一-龥]
 * - Set 去重
 * - Markdown 渲染
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MessageBubble } from '../MessageBubble';
import type { Message } from '../../types';

describe('MessageBubble', () => {
  const baseMessage: Message = {
    id: '1',
    role: 'assistant',
    content: '测试消息',
    timestamp: new Date(),
  };

  it('renders user message correctly', () => {
    const message: Message = {
      ...baseMessage,
      role: 'user',
      content: '你好',
    };
    render(<MessageBubble message={message} />);
    expect(screen.getByText('你好')).toBeInTheDocument();
  });

  it('renders assistant message correctly', () => {
    render(<MessageBubble message={baseMessage} />);
    expect(screen.getByText('测试消息')).toBeInTheDocument();
  });

  it('returns null for null message', () => {
    const { container } = render(<MessageBubble message={null as unknown as Message} />);
    expect(container.firstChild).toBeNull();
  });

  it('returns null for undefined message', () => {
    const { container } = render(<MessageBubble message={undefined as unknown as Message} />);
    expect(container.firstChild).toBeNull();
  });

  describe('Chinese filename extraction', () => {
    it('extracts Chinese filenames from content', () => {
      const message: Message = {
        ...baseMessage,
        content: '已生成报价单_华为公司_20260306.xlsx，请下载',
      };
      render(<MessageBubble message={message} />);
      
      // 应该显示下载按钮
      expect(screen.getByText('报价单_华为公司_20260306.xlsx')).toBeInTheDocument();
    });

    it('extracts multiple Chinese filenames', () => {
      const message: Message = {
        ...baseMessage,
        content: '文档1：报价单_华为_20260306.xlsx，文档2：提案书_阿里_20260307.docx',
      };
      render(<MessageBubble message={message} />);
      
      expect(screen.getByText('报价单_华为_20260306.xlsx')).toBeInTheDocument();
      expect(screen.getByText('提案书_阿里_20260307.docx')).toBeInTheDocument();
    });

    it('handles mixed Chinese-English filenames', () => {
      const message: Message = {
        ...baseMessage,
        content: '生成文件：report_v2_华为_2026.xlsx',
      };
      render(<MessageBubble message={message} />);
      
      expect(screen.getByText('report_v2_华为_2026.xlsx')).toBeInTheDocument();
    });
  });

  describe('Document deduplication', () => {
    it('deduplicates filenames using Set', () => {
      const message: Message = {
        ...baseMessage,
        content: '文件：test.xlsx 和 test.xlsx', // 重复
        documents: [
          { filename: 'test.xlsx', path: '/test.xlsx', type: 'xlsx' },
          { filename: 'test.xlsx', path: '/test.xlsx', type: 'xlsx' }, // 重复
        ],
      };
      render(<MessageBubble message={message} />);
      
      // 应该只显示一个下载按钮
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBe(1);
    });

    it('deduplicates between documents array and content', () => {
      const message: Message = {
        ...baseMessage,
        content: '已生成报价单_华为.xlsx',
        documents: [
          { filename: '报价单_华为.xlsx', path: '/test.xlsx', type: 'xlsx' },
        ],
      };
      render(<MessageBubble message={message} />);
      
      // 应该只显示一个下载按钮（去重）
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBe(1);
    });
  });

  describe('Defensive programming', () => {
    it('handles undefined documents gracefully', () => {
      const message: Message = {
        ...baseMessage,
        documents: undefined,
      };
      render(<MessageBubble message={message} />);
      // 不应该崩溃，正常渲染消息
      expect(screen.getByText('测试消息')).toBeInTheDocument();
    });

    it('handles null documents gracefully', () => {
      const message: Message = {
        ...baseMessage,
        documents: null as unknown as undefined,
      };
      render(<MessageBubble message={message} />);
      expect(screen.getByText('测试消息')).toBeInTheDocument();
    });

    it('handles invalid document entries', () => {
      const message: Message = {
        ...baseMessage,
        documents: [
          { filename: 'valid.xlsx', path: '/valid.xlsx', type: 'xlsx' },
          null as unknown as { filename: string; path: string; type: string },
          { path: '/no_filename.xlsx', type: 'xlsx' } as unknown as { filename: string; path: string; type: string },
        ],
      };
      render(<MessageBubble message={message} />);
      
      // 只显示有效的文档
      expect(screen.getByText('valid.xlsx')).toBeInTheDocument();
    });

    it('handles empty content', () => {
      const message: Message = {
        ...baseMessage,
        content: '',
      };
      const { container } = render(<MessageBubble message={message} />);
      // 不应该崩溃
      expect(container).toBeTruthy();
    });

    it('handles undefined content', () => {
      const message: Message = {
        ...baseMessage,
        content: undefined as unknown as string,
      };
      const { container } = render(<MessageBubble message={message} />);
      expect(container).toBeTruthy();
    });
  });

  describe('Markdown rendering', () => {
    it('renders bold text', () => {
      const message: Message = {
        ...baseMessage,
        content: '这是**粗体**文字',
      };
      render(<MessageBubble message={message} />);
      expect(screen.getByText('粗体')).toBeInTheDocument();
    });

    it('renders code blocks', () => {
      const message: Message = {
        ...baseMessage,
        content: '`code`',
      };
      render(<MessageBubble message={message} />);
      expect(screen.getByText('code')).toBeInTheDocument();
    });
  });
});

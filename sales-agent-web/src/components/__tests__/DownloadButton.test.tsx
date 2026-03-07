/**
 * DownloadButton 组件测试
 * 
 * 测试要点：
 * - 防御性渲染（无效 filename 不渲染）
 * - 悬浮动画效果
 * - 下载状态切换
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DownloadButton } from '../DownloadButton';

describe('DownloadButton', () => {
  it('renders with valid filename', () => {
    render(<DownloadButton filename="报价单_华为公司_20260306.xlsx" />);
    expect(screen.getByText('报价单_华为公司_20260306.xlsx')).toBeInTheDocument();
  });

  it('returns null for empty filename', () => {
    const { container } = render(<DownloadButton filename="" />);
    expect(container.firstChild).toBeNull();
  });

  it('returns null for undefined filename', () => {
    const { container } = render(<DownloadButton filename={undefined as unknown as string} />);
    expect(container.firstChild).toBeNull();
  });

  it('returns null for null filename', () => {
    const { container } = render(<DownloadButton filename={null as unknown as string} />);
    expect(container.firstChild).toBeNull();
  });

  it('calls onDownload when clicked', async () => {
    const onDownload = vi.fn();
    render(<DownloadButton filename="test.xlsx" onDownload={onDownload} />);
    
    const button = screen.getByRole('button');
    fireEvent.click(button);
    
    await waitFor(() => {
      expect(onDownload).toHaveBeenCalledWith('test.xlsx');
    });
  });

  it('truncates long filenames', () => {
    const longFilename = '非常长的文件名_' + 'x'.repeat(50) + '_20260306.xlsx';
    render(<DownloadButton filename={longFilename} />);
    
    const displayedText = screen.getByText(/\.xlsx$/);
    expect(displayedText.textContent?.length).toBeLessThan(longFilename.length);
  });
});

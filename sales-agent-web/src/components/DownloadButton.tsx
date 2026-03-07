/**
 * DownloadButton 组件 - 科技感文件下载按钮
 * 
 * 设计规范（frontend-design Skill）：
 * - 玻璃拟态（Glassmorphism）
 * - 发光边框（Glowing border）
 * - 微交互动画（Micro-interactions）
 * - 拒绝通用 AI 美学
 * 
 * 防御性编程：
 * - 严格的类型检查
 * - 空值处理
 * - 加载状态管理
 */

import { useState, useCallback } from 'react';
import { Download, FileSpreadsheet, FileText, File, Loader2, Check } from 'lucide-react';
import type { DownloadButtonProps } from '../types';

/**
 * 获取文件图标
 * 根据文件扩展名返回对应的图标组件
 */
const getFileIcon = (filename: string) => {
  if (!filename || typeof filename !== 'string') return File;
  
  const ext = filename.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'xlsx':
    case 'xls':
    case 'csv':
      return FileSpreadsheet;
    case 'docx':
    case 'doc':
      return FileText;
    default:
      return File;
  }
};

/**
 * 格式化文件名
 * 截断过长的文件名，添加省略号
 */
const formatFilename = (filename: string, maxLength: number = 30): string => {
  if (!filename || typeof filename !== 'string') return '未知文件';
  if (filename.length <= maxLength) return filename;
  
  const ext = filename.split('.').pop();
  const name = filename.substring(0, filename.lastIndexOf('.'));
  const truncatedName = name.substring(0, maxLength - 4 - (ext?.length || 0));
  return `${truncatedName}...${ext ? '.' + ext : ''}`;
};

/**
 * 下载按钮组件 - 硅谷级 SaaS 设计
 * 
 * 视觉特点：
 * - 深色科技风格背景
 * - 青色/蓝色渐变发光边框
 * - 玻璃拟态磨砂效果
 * - 悬浮时的光晕扩散动画
 */
export function DownloadButton({ 
  filename, 
  onDownload, 
  className = '' 
}: DownloadButtonProps) {
  // 防御性检查：确保 filename 有效
  if (!filename || typeof filename !== 'string' || filename.trim() === '') {
    return null;
  }

  const [isDownloading, setIsDownloading] = useState(false);
  const [isDownloaded, setIsDownloaded] = useState(false);
  
  const FileIcon = getFileIcon(filename);
  const displayName = formatFilename(filename);
  
  /**
   * 处理下载
   * 包含加载状态和成功反馈
   * 
   * 修复：使用正确的后端下载路径 /api/v1/docs/documents/{filename}
   */
  const handleDownload = useCallback(async () => {
    if (isDownloading || isDownloaded) return;
    
    setIsDownloading(true);
    
    try {
      // 如果有外部下载处理器，使用它
      if (onDownload) {
        await onDownload(filename);
      } else {
        // 默认下载行为：构造下载链接
        // 修复：正确的后端路径是 /api/v1/docs/documents/{filename}
        const downloadUrl = `http://127.0.0.1:8000/api/v1/docs/documents/${encodeURIComponent(filename)}`;
        
        // 创建临时链接并点击
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
      
      // 显示成功状态
      setIsDownloaded(true);
      setTimeout(() => setIsDownloaded(false), 2000);
    } catch (error) {
      console.error('下载失败:', error);
    } finally {
      setIsDownloading(false);
    }
  }, [filename, onDownload, isDownloading, isDownloaded]);

  return (
    <button
      onClick={handleDownload}
      disabled={isDownloading}
      className={`
        group relative flex items-center gap-3 
        px-4 py-3 rounded-xl
        transition-all duration-300 ease-out
        disabled:opacity-70 disabled:cursor-not-allowed
        ${className}
      `}
      style={{
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 41, 59, 0.95) 100%)',
        border: '1px solid rgba(56, 189, 248, 0.2)',
        boxShadow: '0 0 20px rgba(56, 189, 248, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'rgba(56, 189, 248, 0.5)';
        e.currentTarget.style.boxShadow = '0 0 30px rgba(56, 189, 248, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.15)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'rgba(56, 189, 248, 0.2)';
        e.currentTarget.style.boxShadow = '0 0 20px rgba(56, 189, 248, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.1)';
      }}
    >
      {/* 背景光晕效果 */}
      <div 
        className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"
        style={{
          background: 'radial-gradient(circle at center, rgba(56, 189, 248, 0.15) 0%, transparent 70%)',
        }}
      />
      
      {/* 文件图标 */}
      <div 
        className="relative flex items-center justify-center w-10 h-10 rounded-lg transition-transform duration-300 group-hover:scale-110"
        style={{
          background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.2) 0%, rgba(14, 165, 233, 0.3) 100%)',
          border: '1px solid rgba(56, 189, 248, 0.3)',
        }}
      >
        <FileIcon className="w-5 h-5 text-sky-400" />
      </div>
      
      {/* 文件名 */}
      <div className="relative flex-1 text-left">
        <p className="text-sm font-medium text-slate-200 group-hover:text-white transition-colors">
          {displayName}
        </p>
        <p className="text-xs text-slate-400 group-hover:text-slate-300 transition-colors">
          点击下载
        </p>
      </div>
      
      {/* 下载/状态图标 */}
      <div className="relative">
        {isDownloading ? (
          <Loader2 className="w-5 h-5 text-sky-400 animate-spin" />
        ) : isDownloaded ? (
          <div 
            className="flex items-center justify-center w-8 h-8 rounded-full"
            style={{ background: 'rgba(34, 197, 94, 0.2)' }}
          >
            <Check className="w-4 h-4 text-green-400" />
          </div>
        ) : (
          <div 
            className="flex items-center justify-center w-8 h-8 rounded-full transition-all duration-300 group-hover:scale-110"
            style={{ 
              background: 'rgba(56, 189, 248, 0.15)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
            }}
          >
            <Download className="w-4 h-4 text-sky-400 group-hover:text-sky-300 transition-colors" />
          </div>
        )}
      </div>
      
      {/* 悬浮时的光条效果 */}
      <div 
        className="absolute bottom-0 left-0 right-0 h-px opacity-0 group-hover:opacity-100 transition-opacity duration-300"
        style={{
          background: 'linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.8), transparent)',
        }}
      />
    </button>
  );
}

export default DownloadButton;

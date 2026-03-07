/**
 * 文件名提取工具函数
 * 
 * 核心功能：
 * - 支持中文的文件名提取
 * - Set 去重
 * - 防御性编程
 * 
 * 正则说明：
 * [\w\-\u4e00-\u9fa5]+ 匹配：
 * - \w: 单词字符（字母、数字、下划线）
 * - \-: 连字符
 * - \u4e00-\u9fa5: 中文字符
 * 
 * 这样可以匹配：
 * - 报价单_华为公司_20260306.xlsx
 * - product_list_v2.xlsx
 * - 测试文档-2024.md
 */

import type { DocumentInfo } from '../types';

/**
 * 从文本内容中提取文件名
 * 
 * @param content - 文本内容
 * @returns 文件名数组
 */
export const extractFilenamesFromText = (content: string | undefined | null): string[] => {
  // 防御性检查
  if (!content || typeof content !== 'string') {
    return [];
  }

  /**
   * 关键正则：支持中文的文件名匹配
   * 
   * [\w\-\u4e00-\u9fa5]+ 匹配文件名主体（支持中文、英文、数字、下划线、连字符）
   * \.(?:xlsx|xls|docx|doc|pdf|txt|md|pptx) 匹配扩展名
   * 
   * flags:
   * - g: 全局匹配
   * - i: 忽略大小写
   */
  const filenameRegex = /[\w\-\u4e00-\u9fa5]+\.(?:xlsx|xls|docx|doc|pdf|txt|md|pptx)/gi;
  
  const matches = content.match(filenameRegex);
  
  if (!matches || !Array.isArray(matches)) {
    return [];
  }
  
  // 清理并去重
  const uniqueFilenames = [...new Set(
    matches
      .map(name => name.trim())
      .filter(name => name.length > 0)
  )];
  
  return uniqueFilenames;
};

/**
 * 从文档列表中提取文件名（带去重）
 * 
 * @param documents - 文档列表
 * @returns 文档信息数组
 */
export const extractDocuments = (
  documents: unknown[] | undefined | null,
  content?: string | null
): DocumentInfo[] => {
  const result: DocumentInfo[] = [];
  const seenFilenames = new Set<string>();

  // 1. 从 documents 数组提取
  if (documents && Array.isArray(documents)) {
    documents.forEach((doc) => {
      // 防御性检查
      if (!doc || typeof doc !== 'object') return;
      
      const docObj = doc as Record<string, unknown>;
      const filename = docObj.filename;
      
      if (filename && typeof filename === 'string') {
        const cleanFilename = filename.trim();
        
        if (cleanFilename && !seenFilenames.has(cleanFilename)) {
          seenFilenames.add(cleanFilename);
          result.push({
            filename: cleanFilename,
            path: String(docObj.path || `/output/${cleanFilename}`),
            type: String(docObj.type || cleanFilename.split('.').pop() || 'unknown'),
            size: typeof docObj.size === 'number' ? docObj.size : undefined,
          });
        }
      }
    });
  }

  // 2. 从 content 文本中提取（兜底）
  const textFilenames = extractFilenamesFromText(content);
  
  textFilenames.forEach((filename) => {
    if (!seenFilenames.has(filename)) {
      seenFilenames.add(filename);
      result.push({
        filename,
        path: `/output/${filename}`,
        type: filename.split('.').pop() || 'unknown',
      });
    }
  });

  return result;
};

/**
 * 格式化文件名（截断过长名称）
 * 
 * @param filename - 原始文件名
 * @param maxLength - 最大长度
 * @returns 格式化后的文件名
 */
export const formatFilename = (filename: string, maxLength: number = 30): string => {
  if (!filename || typeof filename !== 'string') {
    return '未知文件';
  }
  
  if (filename.length <= maxLength) {
    return filename;
  }
  
  // 分离扩展名
  const lastDotIndex = filename.lastIndexOf('.');
  if (lastDotIndex === -1) {
    return filename.substring(0, maxLength - 3) + '...';
  }
  
  const name = filename.substring(0, lastDotIndex);
  const ext = filename.substring(lastDotIndex);
  
  // 计算保留的长度
  const availableLength = maxLength - 3 - ext.length; // 3 是 "..." 的长度
  
  if (availableLength <= 0) {
    return filename.substring(0, maxLength);
  }
  
  return name.substring(0, availableLength) + '...' + ext;
};

/**
 * 验证文件名是否有效
 * 
 * @param filename - 文件名
 * @returns 是否有效
 */
export const isValidFilename = (filename: unknown): filename is string => {
  if (!filename || typeof filename !== 'string') {
    return false;
  }
  
  const trimmed = filename.trim();
  
  // 检查长度
  if (trimmed.length === 0 || trimmed.length > 255) {
    return false;
  }
  
  // 检查是否包含非法字符
  const invalidChars = /[<>:"|?*\x00-\x1f]/;
  if (invalidChars.test(trimmed)) {
    return false;
  }
  
  // 检查是否有扩展名
  if (!trimmed.includes('.')) {
    return false;
  }
  
  return true;
};

# AI 销售助手 - 前端应用

基于 **React + TypeScript + Vite + Tailwind CSS** 构建的现代化 AI 聊天界面。

## 技术栈

- ⚡ **Vite** - 极速构建工具
- ⚛️ **React 18** - 函数组件 + Hooks
- 🔷 **TypeScript** - 类型安全
- 🎨 **Tailwind CSS** - 原子化 CSS 框架
- 🎯 **Lucide React** - 图标库

## 功能特性

- ✅ 左侧边栏：Logo、新建对话、历史会话列表
- ✅ 聊天界面：用户消息（蓝色右对齐）、AI 消息（白色左对齐）
- ✅ Markdown 渲染：支持代码块、标题、列表、粗体、斜体等
- ✅ 加载状态：发送消息时显示"正在思考..."
- ✅ 响应式设计：移动端适配侧边栏
- ✅ 自动滚动：新消息自动滚动到底部
- ✅ 智能输入框：Enter 发送，Shift+Enter 换行，自动调整高度

## API 对接

后端地址：`http://127.0.0.1:8000/api/v1/chat`

请求格式：
```json
{
  "session_id": "web_user_001",
  "message": "用户的输入"
}
```

响应格式：
```json
{
  "reply": "AI 的回复内容"
}
```

## 安装与启动

### 1. 安装依赖

```bash
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

应用将在 `http://localhost:5173` 启动（Vite 默认端口）。

### 3. 构建生产版本

```bash
npm run build
```

构建后的文件位于 `dist/` 目录。

## 项目结构

```
sales-agent-web/
├── src/
│   ├── App.tsx          # 主应用组件（聊天界面）
│   ├── types.ts         # TypeScript 类型定义
│   ├── main.tsx         # 应用入口
│   └── index.css        # 全局样式（含 Tailwind）
├── index.html           # HTML 模板
├── tailwind.config.js   # Tailwind 配置
├── postcss.config.js    # PostCSS 配置
├── package.json         # 项目依赖
└── README.md            # 本文件
```

## 注意事项

1. **后端服务**：确保 FastAPI 后端已启动并在 `http://127.0.0.1:8000` 运行
2. **跨域问题**：如果后端未配置 CORS，可能需要在后端添加跨域支持
3. **Session ID**：当前使用固定的 `web_user_001`，实际应用应动态生成或使用用户 ID

## 自定义配置

### 修改后端地址

编辑 `src/App.tsx` 中的 `BACKEND_URL` 常量：

```typescript
const BACKEND_URL = 'http://你的后端地址/api/v1/chat';
```

### 修改会话 ID

编辑 `src/App.tsx` 中的 `SESSION_ID` 常量：

```typescript
const SESSION_ID = '你的会话ID';
```

## 浏览器支持

- Chrome / Edge / Firefox / Safari 最新版本
- 不支持 IE11

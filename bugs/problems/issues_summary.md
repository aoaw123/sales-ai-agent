# 踩坑与问题复盘文档

> **项目：** 智能销售 AI Agent  
> **文档用途：** 记录核心开发阶段遇到的关键问题及解决方案，为重构提供避坑指南

---

## 1. 意图识别与大模型输出格式问题

### 问题描述
GLM 等国产大模型在返回结构化数据时，容易在 JSON 外包裹 Markdown 代码块标记（如 ` ```json ` 或 ` ``` `），导致标准 JSON 解析器直接抛出解析异常。

### 影响范围
- 意图识别节点 (`intent_node.py`)
- 参数提取节点
- 任何依赖模型输出 JSON 的模块

### 解决方案
1. **Prompt 层面**：在系统提示词中明确约束模型只返回纯 JSON，禁止添加 Markdown 标记
2. **解析层面**：实现正则回退机制，先尝试标准 `json.loads()`，失败时通过正则提取 ` ```json\n(.*?)\n``` ` 或 ` \{.*\} ` 范围内的内容
3. **兜底机制**：设置解析失败时的默认意图和参数

---

## 2. RAG 向量库模型不匹配

### 问题描述
错误使用了 OpenAI 的 `text-embedding-3-small` 模型，而项目中配置的是智谱 AI 的 API Key，导致调用时返回 **1211 模型不存在** 的错误。

### 错误信息
```
Error code: 1211 - 模型不存在
```

### 解决方案
- **必须使用智谱官方 Embedding 模型**：`embedding-2`
- 在 `.env` 配置文件中明确区分不同厂商的模型名称
- 加载知识库前校验 Embedding 模型可用性

---

## 3. LangChain 库版本冲突

### 问题描述
LangChain 核心库与文本处理模块分离后，`langchain.text_splitter` 模块路径发生变更，旧代码导入时报错 `ModuleNotFoundError`。

### 解决方案
1. **安装独立包**：
   ```bash
   pip install langchain-text-splitters
   ```
2. **修改导入路径**：
   ```python
   # 旧方式（已废弃）
   from langchain.text_splitter import RecursiveCharacterTextSplitter
   
   # 新方式
   from langchain_text_splitters import RecursiveCharacterTextSplitter
   ```

---

## 4. LangGraph 状态中断 (Interrupt) 导致的数据越界

### 问题描述
当工作流因缺少必要参数触发 `interrupt` 暂停后，LangGraph 返回的图状态在某些情况下可能是空元组 `()`。代码中直接访问 `value[0]` 会导致 `IndexError: tuple index out of range`，引发 **500 内部服务器错误**。

### 问题代码示例
```python
# 危险写法
state = graph.get_state(config)
result = state.values[0]  # 当 values 为 () 时崩溃
```

### 解决方案
```python
# 安全写法
state = graph.get_state(config)
values = state.values if isinstance(state.values, (list, tuple)) else (state.values,)
if len(values) == 0:
    result = {}  # 提供默认值
else:
    result = values[0]
```

---

## 5. Pydantic 校验拦截

### 问题描述
流程中断或异常分支时，回复生成节点可能未生成任何话术，导致 `reply` 字段为 `None`。当该数据通过 Pydantic 模型响应给前端时，触发字段校验失败，返回 **500 Validation Error**。

### 解决方案
- 所有 Node 节点必须确保输出字段有兜底值
- 在 Pydantic Schema 中为可选字段设置默认值：
  ```python
  reply: str = "抱歉，我暂时无法处理您的请求，请稍后再试。"
  ```
- 回复生成节点增加空值检查，为 `None` 自动填充默认回复

---

## 6. 前端白屏与正则匹配 Bug

### 问题描述
该问题包含两个连锁缺陷：

### 6.1 防御性编程缺失导致白屏
前端在提取文件名渲染下载按钮时，如果后端返回的数据结构异常或字段缺失，访问 `undefined` 的属性会直接引发 JavaScript 运行时错误，导致整个页面白屏。

### 6.2 正则表达式中文字符集缺失
提取文件名的正则表达式若未包含中文字符集（`\u4e00-\u9fa5`），遇到中文文件名时会在第一个中文字符处截断，导致提取的文件名不完整。后续点击下载时，携带错误文件名的请求会导致后端返回 **404 Not Found**。

### 解决方案

**前端防御性编程：**
```javascript
// 安全提取文件名
const filename = data?.documents?.[0]?.filename || '报价单.xlsx';
```

**支持中文的正则表达式：**
```javascript
// 匹配包含中文、字母、数字、下划线、横线的文件名
const filenameRegex = /[\w\-\u4e00-\u9fa5]+\.\w+/;
const match = replyText.match(filenameRegex);
```

**去重处理：**
```javascript
// 确保 documents 列表无重复文件名
const uniqueDocs = [...new Map(documents.map(d => [d.filename, d])).values()];
```

---

## 总结

| 问题编号 | 严重程度 | 影响模块 | 核心解决思路 |
|:--------:|:--------:|:--------:|:-------------|
| 1 | 🔴 高 | 意图识别 | Prompt 约束 + 正则回退解析 |
| 2 | 🔴 高 | RAG 知识库 | 使用正确的 Embedding 模型 |
| 3 | 🟡 中 | 文本处理 | 更新导入路径，安装独立包 |
| 4 | 🔴 高 | LangGraph 状态 | 严格的类型判断和长度校验 |
| 5 | 🔴 高 | API 响应 | Pydantic 默认值 + 兜底回复 |
| 6 | 🟡 中 | 前端交互 | 防御性编程 + 中文正则支持 |

---

> 💡 **重构原则**：针对上述问题，在新代码中必须建立**防御性编程**思维，对所有外部输入（模型输出、用户输入、跨模块数据）进行校验和兜底处理。

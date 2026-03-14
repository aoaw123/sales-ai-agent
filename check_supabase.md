# Supabase 连接问题排查指南

## 错误信息
```
FATAL: Tenant or user not found
```

## 排查步骤

### 1. 检查 Supabase 项目状态
- 登录 https://supabase.com/dashboard
- 进入你的项目
- 确认项目状态为 "Active"

### 2. 获取正确的连接字符串
在 Supabase 控制台中：
```
Project Settings > Database > Connection string
```

选择 **URI** 标签，复制连接字符串。

### 3. 检查两种连接方式

#### 方式 A: 连接池模式 (端口 6543)
- 使用场景：事务模式，短连接
- 用户名格式：`postgres.[PROJECT_REF]`
- 示例：`postgres.jzwcxpojjzpnnryayfzu`

#### 方式 B: 直接连接 (端口 5432)
- 使用场景：会话模式，长连接
- 主机格式：`db.[PROJECT_REF].supabase.co`
- 用户名：`postgres` (不带 project ref)

### 4. 密码检查
确保密码中特殊字符已正确 URL 编码：
- `@` → `%40`
- `:` → `%3A`
- `/` → `%2F`

### 5. 更新 .env 文件

尝试使用 **直接连接**（通常更稳定）：
```bash
# 直接连接 - 端口 5432
DATABASE_URL="postgresql://postgres:your_password@db.jzwcxpojjzpnnryayfzu.supabase.co:5432/postgres?sslmode=require"
```

或者使用 **连接池**：
```bash
# 连接池 - 端口 6543  
DATABASE_URL="postgresql://postgres.jzwcxpojjzpnnryayfzu:your_password@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
```

### 6. 验证连接
修改 .env 后运行：
```bash
python test_connection.py
```

## 常见问题

### Q: 密码中有 `@` 符号怎么办？
A: 将 `@` 替换为 `%40`

### Q: 如何测试连接？
A: 使用 psql 命令行：
```bash
psql "postgresql://postgres:your_password@db.jzwcxpojjzpnnryayfzu.supabase.co:5432/postgres?sslmode=require"
```

### Q: 项目引用是什么？
A: 项目引用是 `jzwcxpojjzpnnryayfzu` 这部分，在你的 Supabase 项目 URL 中可以找到：
```
https://supabase.com/dashboard/project/jzwcxpojjzpnnryayfzu
```

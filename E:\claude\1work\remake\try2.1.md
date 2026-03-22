# Supabase 连接问题修复记录

## 问题 1：Tenant or user not found

### 问题现象
```
FATAL:  Tenant or user not found
couldn't get a connection after 30.00 sec
```

### 修复方案

**修复前（错误）：**
```bash
DATABASE_URL=postgresql://postgres.jzwcxpojjzpnnryayfzu:weiyiao110Aa%40@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require
```

**修复后（正确）：**
```bash
DATABASE_URL=postgresql://postgres.jzwcxpojjzpnnryayfzu:weiyiao110Aa%40@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres?sslmode=require
```

### 关键变更点

| 配置项 | 错误值 | 正确值 |
|--------|--------|--------|
| **主机地址** | `aws-0-ap-southeast-1.pooler.supabase.com` | `aws-1-ap-southeast-2.pooler.supabase.com` |
| 用户名格式 | `postgres.jzwcxpojjzpnnryayfzu` | `postgres.jzwcxpojjzpnnryayfzu` (保持不变) |
| 密码编码 | `weiyiao110Aa%40` | `weiyiao110Aa%40` (保持不变) |

### 根本原因

Supabase 可能进行了以下变更：
- **服务器迁移**：从 `ap-southeast-1` 可用区迁移到 `ap-southeast-2`
- **连接池节点故障/切换**：原连接池节点不可用，需要切换到新节点

---

## 问题 2：prepared statement "_pg3_0" already exists

### 问题现象
```
prepared statement "_pg3_0" already exists
工作流执行异常: couldn't get a connection after 30.00 sec
```

### 修复方案

在使用 `psycopg` + `AsyncConnectionPool` + Supabase 连接池模式时，需要**在代码中**禁用 Prepared Statement 缓存。

**⚠️ 注意**：`prepare_threshold` 不是连接字符串参数，不能放在 DATABASE_URL 中！

#### 修复 1：AsyncConnectionPool（运行时连接池）✅ 正确方式

```python
from psycopg_pool import AsyncConnectionPool

# 正确方式：使用 kwargs 参数传递 prepare_threshold
async with AsyncConnectionPool(
    conninfo=settings.database_url,
    max_size=20,
    min_size=1,
    open=False,
    kwargs={"prepare_threshold": None},  # ← 关键：禁用 prepared statement
) as pool:
    # ... 使用 pool
```

**⚠️ 注意**：不要使用 `configure` 回调来设置 `prepare_threshold`，它不会被正确应用到所有连接场景。

#### 修复 2：AsyncConnection.connect()（初始化连接）

```python
from psycopg import AsyncConnection

conn = await AsyncConnection.connect(
    settings.database_url,
    autocommit=True,
    gssencmode="disable",
    prepare_threshold=None,  # ← 关键：使用 None 禁用（不是 0）
)
```

### 关键代码变更（sales_graph.py）

**1. initialize_database() 函数：**

```python
conn = await AsyncConnection.connect(
    settings.database_url,
    autocommit=True,
    gssencmode="disable",
    prepare_threshold=None,  # ← 添加这行：None 禁用 prepared statement
)
```

**2. run_sales_agent() 函数：**

```python
# 在 AsyncConnectionPool 创建时添加 kwargs 参数
async with AsyncConnectionPool(
    conninfo=settings.database_url,
    max_size=20,
    min_size=1,
    open=False,
    kwargs={"prepare_threshold": None},  # ← 添加这行：禁用 prepared statement
) as pool:
```

### 根本原因

- **Prepared Statement 冲突**：`psycopg` 默认会缓存 Prepared Statement，但在 Supabase 连接池模式下，连接可能被复用，导致同名 Prepared Statement 已存在的错误
- **连接池行为差异**：Supabase 的 pgBouncer 连接池与 `psycopg` 的 Prepared Statement 缓存机制不兼容

### 错误的尝试 ❌

**❌ 错误 1：在连接字符串中添加 prepare_threshold**
```bash
DATABASE_URL=postgresql://.../postgres?sslmode=require&prepare_threshold=0
```
错误：
```
invalid URI query parameter: "prepare_threshold"
```

**❌ 错误 2：使用 configure 回调设置 prepare_threshold**
```python
async def _configure_connection(conn):
    conn.prepare_threshold = None

async with AsyncConnectionPool(
    conninfo=settings.database_url,
    configure=_configure_connection,  # 不会生效！
) as pool:
```
错误：仍然会出现 `prepared statement "_pg3_0" already exists`

### 正确的做法 ✅

在代码中设置 `prepare_threshold=0`，保持连接字符串干净：

```bash
# ✅ 正确的 DATABASE_URL（不要加 prepare_threshold）
DATABASE_URL=postgresql://postgres.jzwcxpojjzpnnryayfzu:weiyiao110Aa%40@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres?sslmode=require
```

---

## 验证方式

```bash
# 使用 test_connection.py 验证连接
python test_connection.py

# 期望输出
✅ 连接成功! 测试查询结果: (1,)
```

---

## 经验总结

1. **获取最新连接字符串**：遇到 "Tenant or user not found" 时，应直接从 Supabase Dashboard 复制最新的连接字符串
   - 路径：`Project Settings > Database > Connection string > URI`

2. **注意主机地址变化**：Supabase 的服务器地址可能会变化，不要假设地址永远不变

3. **密码编码规则**：密码中的特殊字符需要 URL 编码
   - `@` → `%40`
   - `:` → `%3A`
   - `/` → `%2F`

4. **连接参数调优**：
   - **连接池模式**（端口 6543）：需要在代码中设置 `prepare_threshold=0`
   - **直接连接**（端口 5432）：不需要此设置，但国内网络可能不稳定

5. **技术栈兼容性**：
   - `psycopg` + `AsyncConnectionPool` + Supabase pgBouncer = 需要禁用 prepared statement
   - 正确方式：`kwargs={"prepare_threshold": None}`（不是 configure 回调）
   - `prepare_threshold` **不是**连接字符串参数，不能放在 DATABASE_URL 中

6. **正确的配置方式**：
   - 连接字符串只放标准参数（sslmode 等）
   - `AsyncConnectionPool` 使用 `kwargs` 参数传递连接选项
   - `AsyncConnection.connect()` 直接传入参数

---

## 重构注意事项

在重构项目时，确保：
1. 从环境变量读取 `DATABASE_URL`，不要硬编码
2. 保留 `test_connection.py` 作为连接诊断工具
3. 数据库初始化代码要有错误处理和重试机制
4. 考虑添加连接健康检查端点
5. 如果使用 `psycopg` 连接池 + Supabase：
   - 使用 `kwargs={"prepare_threshold": None}` 禁用 prepared statement
   - 不要使用 `configure` 回调（不会生效）
6. **不要**在 DATABASE_URL 中添加非标准连接字符串参数

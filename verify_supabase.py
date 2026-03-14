#!/usr/bin/env python3
"""验证 Supabase 连接凭据"""

# 请从 Supabase 控制台复制正确的连接字符串
# 路径: Project Settings > Database > Connection string > URI

print("请确认以下信息:\n")
print("1. 登录 https://supabase.com/dashboard")
print("2. 确认项目处于 Active 状态（没有被暂停）")
print("3. 进入 Project Settings > Database")
print("4. 在 Connection string 中复制 URI 格式的连接字符串\n")

print("当前 .env 中的 DATABASE_URL:")
import os
from dotenv import load_dotenv
load_dotenv()
url = os.getenv("DATABASE_URL", "")
print(f"  {url}\n")

print("您的连接字符串结构:")
# 简单解析
parts = url.replace("postgresql://", "").split("@")
if len(parts) == 2:
    user_pass = parts[0]
    host_db = parts[1]
    if ":" in user_pass:
        user, password = user_pass.split(":", 1)
        print(f"  用户名: {user}")
        print(f"  密码: {'*' * len(password)}")
    else:
        user = user_pass
        print(f"  用户名: {user}")
        print(f"  密码: [未设置]")
    print(f"  主机和数据库: {host_db}")

print("\n常见错误:")
print("  - 如果密码中有 @ 符号，必须替换为 %40")
print("  - 如果项目被暂停，需要点击 Resume 恢复")
print("  - 如果使用 IPv6，可能需要添加 ?sslmode=require")

print("\n请提供从 Supabase 控制台复制的连接字符串，我帮您更新 .env")

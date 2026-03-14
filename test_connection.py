#!/usr/bin/env python3
"""测试不同的连接方式"""
import asyncio
import os
from urllib.parse import urlparse, quote_plus

# 加载 .env
from dotenv import load_dotenv
load_dotenv()

original_url = os.getenv("DATABASE_URL", "")
print(f"原始 URL: {original_url[:60]}...")

# 解析 URL
parsed = urlparse(original_url)
print(f"\n解析结果:")
print(f"  用户名: {parsed.username}")
print(f"  密码: {'*' * len(parsed.password) if parsed.password else 'None'}")
print(f"  主机: {parsed.hostname}")
print(f"  端口: {parsed.port}")
print(f"  数据库: {parsed.path}")

# 尝试三种连接方式
urls_to_try = []

# 1. 原始 URL（连接池端口 6543）
urls_to_try.append(("连接池 6543", original_url))

# 2. 改为端口 5432（直接连接）
if parsed.port == 6543:
    direct_host = parsed.hostname.replace("pooler.supabase.com", "supabase.co")
    # 直接连接通常使用简单用户名（不带 .projectref）
    # 但 Supabase 有时也要求带 projectref，需要看具体配置
    direct_url1 = f"postgresql://{parsed.username}:{quote_plus(parsed.password)}@{direct_host}:5432{parsed.path}?sslmode=require"
    urls_to_try.append(("直接连接 5432 (主机改为 supabase.co)", direct_url1))
    
    # 另一种可能：保留 pooler 主机，只改端口
    direct_url2 = f"postgresql://{parsed.username}:{quote_plus(parsed.password)}@{parsed.hostname}:5432{parsed.path}?sslmode=require"
    urls_to_try.append(("直接连接 5432 (pooler 主机)", direct_url2))

print(f"\n将尝试以下连接方式:\n")
for name, url in urls_to_try:
    print(f"  [{name}]")
    print(f"    {url[:70]}...")
    print()


async def test_connection(name, conninfo):
    """测试单个连接"""
    from psycopg import AsyncConnection
    
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"{'='*60}")
    
    try:
        conn = await AsyncConnection.connect(
            conninfo,
            autocommit=True,
            sslmode="require",
            gssencmode="disable",
            connect_timeout=10,
        )
        
        # 执行简单查询
        cur = await conn.execute("SELECT 1")
        result = await cur.fetchone()
        await conn.close()
        
        print(f"✅ 连接成功! 测试查询结果: {result}")
        return True
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False


async def main():
    results = []
    for name, url in urls_to_try:
        success = await test_connection(name, url)
        results.append((name, success, url))
    
    print(f"\n\n{'='*60}")
    print("测试结果汇总")
    print(f"{'='*60}")
    for name, success, url in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{status} - {name}")
    
    # 输出推荐配置
    successful = [(name, url) for name, success, url in results if success]
    if successful:
        print(f"\n✅ 推荐使用的 DATABASE_URL:")
        print(f"export DATABASE_URL=\"{successful[0][1]}\"")
    else:
        print(f"\n❌ 所有连接方式都失败")
        print("请检查 Supabase 控制台获取正确的连接字符串")
        print("路径: Project Settings > Database > Connection string")

if __name__ == "__main__":
    asyncio.run(main())

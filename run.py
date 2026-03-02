#!/usr/bin/env python3
"""
启动脚本 - 便捷启动开发服务器

用法：
    python run.py          # 启动服务器
    python run.py --prod   # 生产模式启动
    python run.py --help   # 查看帮助
"""

import argparse
import os
import sys

# 确保当前目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description="智能销售 AI Agent 启动脚本")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="服务器监听地址 (默认: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="服务器端口 (默认: 8000)"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="生产模式启动（禁用自动重载）"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="工作进程数（生产模式有效）"
    )
    
    args = parser.parse_args()
    
    # 设置环境变量
    if not args.prod:
        os.environ["DEBUG"] = "true"
        print("🚀 启动开发服务器（自动重载已启用）")
    else:
        os.environ["DEBUG"] = "false"
        print("🚀 启动生产服务器")
    
    # 导入并启动
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=not args.prod,
        workers=args.workers if args.prod else 1,
        log_level="info" if not args.prod else "warning",
    )


if __name__ == "__main__":
    main()

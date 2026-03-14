import anthropic

# 客户端会自动读取刚才在终端里配置的 BASE_URL 和 API_KEY 环境变量
client = anthropic.Anthropic()

message = client.messages.create(
    model="MiniMax-M2.5",
    max_tokens=1000,
    system="你是一个顶级的编程助手。",
    messages=[
        {
            "role": "user",
            "content": [{"type": "text", "text": "你好！请用Python写一个简短的贪吃蛇游戏核心逻辑。"}]
        }
    ]
)

# 打印模型返回的内部思考过程和最终生成的文本
for block in message.content:
    if block.type == "thinking":
        print(f"💡 内部思考过程:\n{block.thinking}\n{'-'*40}")
    elif block.type == "text":
        print(f"📝 最终回复:\n{block.text}\n")
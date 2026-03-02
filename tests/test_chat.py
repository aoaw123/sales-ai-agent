"""
聊天接口测试
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    """测试健康检查端点"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_chat_endpoint_validation():
    """测试聊天接口参数校验"""
    # 空消息
    response = client.post(
        "/api/v1/chat",
        json={"session_id": "test", "message": ""}
    )
    assert response.status_code == 422


def test_chat_endpoint_structure():
    """测试聊天接口响应结构"""
    # 由于调用 LLM 需要 API Key，这里仅测试接口结构
    # 实际测试需要 mock LLM 调用
    pass


@pytest.mark.asyncio
async def test_intent_recognition():
    """测试意图识别"""
    from app.agents.nodes.intent_node import intent_recognition_node
    from app.agents.state import create_initial_state
    
    state = create_initial_state(
        session_id="test",
        user_message="帮我生成一份报价单"
    )
    
    # 注意：这个测试需要有效的 API Key
    # result = await intent_recognition_node(state)
    # assert result["intent_analysis"] is not None

import uuid

import pytest
from httpx import AsyncClient

from order_status_bot.app import app


@pytest.mark.asyncio
async def test_conversation_flow():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a new conversation
        create_resp = await client.post("/conversations")
        assert create_resp.status_code == 200
        conv_id = create_resp.json()["conversation_id"]
        assert uuid.UUID(conv_id)  # valid UUID

        # Initially, messages should be empty
        get_resp = await client.get(f"/conversations/{conv_id}/messages")
        assert get_resp.status_code == 200
        assert get_resp.json()["messages"] == []

        # Check order 12345
        resp1 = await client.post(
            f"/conversations/{conv_id}/messages",
            json={"content": "Hi, can you check my order 12345?"},
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert "assistant" in data1
        assert "tool_result" in data1
        assert "12345" in data1["assistant"]  # message mentions the order
        # Ensure tool_result found true
        tool1 = data1["tool_result"]
        assert tool1["found"] is True
        assert tool1["order"]["status"] == "shipped"

        # Cancel processing order 23456
        resp2 = await client.post(
            f"/conversations/{conv_id}/messages",
            json={"content": "Please cancel order 23456"},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["tool_result"]["ok"] is True
        assert "canceled successfully" in data2["assistant"].lower()

        # Check order 23456 again
        resp3 = await client.post(
            f"/conversations/{conv_id}/messages",
            json={"content": "What's the status of order 23456?"},
        )
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert "assistant" in data3
        assert "canceled" in data3["assistant"].lower()
        # tool_result should reflect the canceled status as well
        tool3 = data3["tool_result"]
        assert tool3["found"] is True
        assert tool3["order"]["status"] == "canceled"

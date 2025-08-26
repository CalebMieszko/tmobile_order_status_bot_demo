"""
FastAPI application exposing REST endpoints for the order-status chatbot.

This module defines three endpoints:
  - POST /conversations: create a new conversation and return its ID.
  - GET /conversations/{conversation_id}/messages: retrieve the conversation history,
    excluding internal tool messages.
  - POST /conversations/{conversation_id}/messages: send a new user message and
    receive an assistant reply (and tool result if applicable).

Conversation state is stored in memory only and will be lost when the process
terminates.
"""

from __future__ import annotations

import json
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel, Field

from .llm import chat_turn
from .models import Conversation, Message


app = FastAPI(title="Order Status Chatbot")

# In-memory conversation store
CONVERSATIONS: Dict[str, Conversation] = {}


class CreateConversationResponse(BaseModel):
    conversation_id: str = Field(..., description="Unique conversation identifier")


class UserMessageRequest(BaseModel):
    content: str = Field(..., description="The user's message content")


class AssistantMessageResponse(BaseModel):
    assistant: str = Field(..., description="Assistant's textual reply")
    tool_result: dict | None = Field(
        default=None,
        description="JSON result returned by a tool call, if any was invoked.",
    )


class ConversationMessagesResponse(BaseModel):
    messages: List[Message] = Field(
        ..., description="List of messages in the conversation (user and assistant)."
    )


@app.post("/conversations", response_model=CreateConversationResponse)
async def create_conversation() -> CreateConversationResponse:
    """Start a new conversation and return its ID."""
    conv = Conversation()
    conv_id = str(conv.conversation_id)
    CONVERSATIONS[conv_id] = conv
    return CreateConversationResponse(conversation_id=conv_id)


@app.get(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
)
async def get_messages(
    conversation_id: str = Path(..., description="Conversation ID")
) -> ConversationMessagesResponse:
    """Retrieve the message history for a given conversation, excluding tool messages."""
    conv = CONVERSATIONS.get(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    # Return only user and assistant messages
    visible_messages = [m for m in conv.messages if m.role in {"user", "assistant"}]
    return ConversationMessagesResponse(messages=visible_messages)


@app.post(
    "/conversations/{conversation_id}/messages",
    response_model=AssistantMessageResponse,
)
async def post_message(
    *,
    conversation_id: str = Path(..., description="Conversation ID"),
    request: UserMessageRequest,
) -> AssistantMessageResponse:
    """Send a new user message and obtain the assistant's reply."""
    conv = CONVERSATIONS.get(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    # Create user message
    user_msg = Message(role="user", content=request.content)
    conv.messages.append(user_msg)
    # Call LLM to get assistant reply (and optional tool result)
    assistant_msg, tool_result = chat_turn(conv.messages)
    # If a tool was invoked, record the tool message internally
    if tool_result is not None:
        tool_message = Message(
            role="tool", content=json.dumps(tool_result), tool_name="tool"
        )
        conv.messages.append(tool_message)
    # Append assistant message
    conv.messages.append(assistant_msg)
    return AssistantMessageResponse(
        assistant=assistant_msg.content, tool_result=tool_result
    )

"""
Pydantic data models for our order status chatbot.

These classes define the structure of orders, messages, conversations, and the
inputs/outputs for the supported tools. All models are strictly typed to
ensure deterministic behaviour and validation throughout the application.
"""

from __future__ import annotations

import uuid
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Order(BaseModel):
    """Represents a single order in the system."""

    order_id: str = Field(..., description="The unique identifier for the order.")
    status: Literal["processing", "shipped", "canceled"] = Field(
        ..., description="The current status of the order."
    )
    item: str = Field(..., description="The product associated with the order.")


class Message(BaseModel):
    """Represents an entry in a conversation, either from the user, assistant or a tool."""

    role: Literal["user", "assistant", "tool"] = Field(
        ...,
        description="The origin of the message: user input, assistant response, or a tool output.",
    )
    content: str = Field(..., description="The textual content of the message.")
    tool_name: Optional[str] = Field(
        default=None,
        description="Name of the tool when the role is 'tool', otherwise None.",
    )


class Conversation(BaseModel):
    """Represents a conversation between the user and the assistant, maintaining context."""

    conversation_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="The unique identifier for the conversation.",
    )
    messages: List[Message] = Field(
        default_factory=list,
        description="The sequential list of messages exchanged in the conversation.",
    )


class FindOrderInput(BaseModel):
    """Input schema for the find_order tool."""

    order_id: str = Field(..., description="The ID of the order to look up.")


class FindOrderResult(BaseModel):
    """Result schema for the find_order tool."""

    found: bool = Field(..., description="Whether the order was found.")
    order: Optional[Order] = Field(
        default=None,
        description="The order object, if found; otherwise None.",
    )


class CancelOrderInput(BaseModel):
    """Input schema for the cancel_order tool."""

    order_id: str = Field(..., description="The ID of the order to cancel.")


class CancelOrderResult(BaseModel):
    """Result schema for the cancel_order tool."""

    ok: bool = Field(..., description="Whether the cancellation request succeeded.")
    reason: Optional[str] = Field(
        default=None,
        description="Reason for a failure to cancel; None if successful.",
    )
    order: Optional[Order] = Field(
        default=None,
        description="The updated order object if the cancellation succeeded; otherwise the current order state.",
    )

"""
Abstractions for interacting with OpenAI's chat API using function calling.

This module defines the tool functions used to look up and cancel orders and
provides a `chat_turn` function that orchestrates the conversation loop with
function calling. If the `OPENAI_API_KEY` environment variable is not set, a
simple fallback implementation will handle user queries deterministically.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional, Tuple

try:
    import openai  # type: ignore
except ImportError:
    # If the openai package is unavailable, leave as None. The fallback will be used.
    openai = None  # type: ignore

from pydantic import ValidationError

from .models import (
    CancelOrderInput,
    CancelOrderResult,
    FindOrderInput,
    FindOrderResult,
    Message,
)
from .orders import cancel_order as cancel_order_logic
from .orders import get_order


def find_order_tool(args: dict) -> FindOrderResult:
    """
    Tool callable that wraps the order lookup.
    Expects args to conform to FindOrderInput.
    """
    try:
        input_model = FindOrderInput(**args)
    except ValidationError as exc:
        raise ValueError(f"Invalid input for find_order: {exc}")
    order = get_order(input_model.order_id)
    if order is not None:
        return FindOrderResult(found=True, order=order)
    return FindOrderResult(found=False, order=None)


def cancel_order_tool(args: dict) -> CancelOrderResult:
    """
    Tool callable that wraps the cancel operation.
    Expects args to conform to CancelOrderInput.
    """
    try:
        input_model = CancelOrderInput(**args)
    except ValidationError as exc:
        raise ValueError(f"Invalid input for cancel_order: {exc}")
    return cancel_order_logic(input_model.order_id)


def _system_prompt() -> str:
    """Return the system prompt for the order assistant."""
    return (
        "You are an order assistant. Use the available tools to look up or cancel "
        "orders. Never invent order data. If the user requests to cancel an order "
        "that is already shipped or canceled, explain that the order cannot be canceled."
    )


def _build_functions_spec() -> List[dict]:
    """Return the OpenAI function definitions for our tools."""
    return [
        {
            "name": "find_order",
            "description": "Look up an order by order_id in the system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The ID of the order to look up.",
                    },
                },
                "required": ["order_id"],
            },
        },
        {
            "name": "cancel_order",
            "description": "Cancel an existing order if it is still processing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The ID of the order to cancel.",
                    },
                },
                "required": ["order_id"],
            },
        },
    ]


def chat_turn(messages: List[Message]) -> Tuple[Message, Optional[Dict]]:
    """
    Perform a single assistant turn given the conversation history.

    Args:
        messages: List of Message objects representing the conversation history.

    Returns:
        A tuple of (assistant_message, tool_result) where tool_result is a dict
        containing the JSON returned by a tool if one was invoked; otherwise None.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    # Only attempt to call OpenAI if both the API key and the openai package are present
    if not api_key or openai is None:
        return _fallback_chat_turn(messages)
    client = openai
    client.api_key = api_key
    openai_messages = []
    for msg in messages:
        if msg.role == "tool":
            openai_messages.append(
                {
                    "role": "tool",
                    "content": msg.content,
                    "name": msg.tool_name,
                }
            )
        else:
            openai_messages.append({"role": msg.role, "content": msg.content})
    openai_messages = [
        {"role": "system", "content": _system_prompt()}
    ] + openai_messages
    response = client.chat.completions.create(
        model="gpt-3.5-turbo-0613",
        messages=openai_messages,
        functions=_build_functions_spec(),
        function_call="auto",
        temperature=0,
    )
    choice = response.choices[0]
    if choice.finish_reason == "function_call":
        fn_name = choice.message.function_call.name
        fn_args_json = choice.message.function_call.arguments
        try:
            args_dict = json.loads(fn_args_json)
        except json.JSONDecodeError:
            assistant = Message(
                role="assistant", content="Sorry, I couldn't parse the tool arguments."
            )
            return assistant, None
        if fn_name == "find_order":
            result = find_order_tool(args_dict)
        elif fn_name == "cancel_order":
            result = cancel_order_tool(args_dict)
        else:
            assistant = Message(role="assistant", content=f"Unknown tool {fn_name}.")
            return assistant, None
        tool_message = Message(role="tool", content=result.json(), tool_name=fn_name)
        followup_messages = openai_messages + [
            {
                "role": "tool",
                "content": tool_message.content,
                "name": tool_message.tool_name,
            }
        ]
        followup_response = client.chat.completions.create(
            model="gpt-3.5-turbo-0613",
            messages=followup_messages,
            temperature=0,
        )
        final_content = followup_response.choices[0].message.content
        assistant = Message(role="assistant", content=final_content)
        return assistant, result.model_dump()
    else:
        assistant = Message(role="assistant", content=choice.message.content)
        return assistant, None


def _fallback_chat_turn(messages: List[Message]) -> Tuple[Message, Optional[Dict]]:
    """
    A fallback implementation of the chat turn when no OpenAI API key is present.

    This simple parser searches the last user message for an order ID and infers
    the intent (lookup vs cancel) based on keywords. It returns a deterministic
    assistant reply and includes the tool result dict when a tool is called.
    """
    if not messages:
        return (
            Message(role="assistant", content="Hello! What can I help you with?"),
            None,
        )
    last_message = messages[-1]
    if last_message.role != "user":
        return Message(role="assistant", content="Awaiting your instructions."), None
    content = last_message.content.lower()
    match = re.search(r"\b(\d+)\b", content)
    order_id = match.group(1) if match else None
    if order_id is None:
        return Message(role="assistant", content="Please provide an order ID."), None
    if "cancel" in content:
        result = cancel_order_tool({"order_id": order_id})
        if result.ok:
            msg = f"Order {order_id} has been canceled successfully."
        else:
            if result.reason == "not_found":
                msg = f"I couldn't find an order with ID {order_id}."
            else:
                msg = f"Order {order_id} cannot be canceled because it is {result.order.status}."
        assistant = Message(role="assistant", content=msg)
        return assistant, result.model_dump()
    else:
        result = find_order_tool({"order_id": order_id})
        if result.found:
            msg = f"Order {order_id} is currently {result.order.status}."
        else:
            msg = f"I couldn't find an order with ID {order_id}."
        assistant = Message(role="assistant", content=msg)
        # return the dict representation whether found or not for consistency
        return assistant, result.model_dump()

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.utils.function_calling import convert_to_json_schema, convert_to_openai_tool

_TOOLS_KWARG = "model_provider_tools"
_TOOL_CHOICE_KWARG = "model_provider_tool_choice"
_STRUCTURED_OUTPUT_KWARG = "model_provider_structured_output"


class ModelProviderChatModel(BaseChatModel):
    model: str
    base_url: str
    temperature: float = 0.0
    timeout: float = 30.0
    openai_fallback: bool = False
    http_client: httpx.Client | None = None
    async_http_client: httpx.AsyncClient | None = None

    @property
    def _llm_type(self) -> str:
        return "model-provider"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": self.model, "base_url": self.base_url, "temperature": self.temperature}

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ):
        serialized_tools = [self._serialize_tool(tool) for tool in tools]
        return self.bind(**{_TOOLS_KWARG: serialized_tools, _TOOL_CHOICE_KWARG: tool_choice, **kwargs})

    def with_structured_output(self, schema: dict[str, Any] | type, **kwargs: Any):
        schema_payload = convert_to_json_schema(schema)
        structured_output = {
            "name": schema_payload.get("title") or "structured_output",
            "schema": schema_payload,
            "strict": bool(kwargs.pop("strict", False)),
        }
        return self.bind(**{_STRUCTURED_OUTPUT_KWARG: structured_output, **kwargs})

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = self._build_payload(messages, stop=stop, stream=False, **kwargs)
        client = self.http_client or httpx.Client(timeout=self.timeout)
        response = client.post(f"{self.base_url}/internal/v1/chat/messages", json=payload)
        response.raise_for_status()
        return self._chat_result_from_response(response.json())

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = self._build_payload(messages, stop=stop, stream=False, **kwargs)
        client = self.async_http_client or httpx.AsyncClient(timeout=self.timeout)
        response = await client.post(f"{self.base_url}/internal/v1/chat/messages", json=payload)
        response.raise_for_status()
        return self._chat_result_from_response(response.json())

    def _stream(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: Any | None = None, **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        payload = self._build_payload(messages, stop=stop, stream=True, **kwargs)
        client = self.http_client or httpx.Client(timeout=self.timeout)
        with client.stream("POST", f"{self.base_url}/internal/v1/chat/messages", json=payload) as response:
            response.raise_for_status()
            for chunk in self._iter_sse_chunks(response.iter_lines()):
                yield chunk

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        payload = self._build_payload(messages, stop=stop, stream=True, **kwargs)
        client = self.async_http_client or httpx.AsyncClient(timeout=self.timeout)
        async with client.stream("POST", f"{self.base_url}/internal/v1/chat/messages", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                frame = json.loads(data)
                chunk = self._chunk_from_frame(frame)
                if chunk is not None:
                    yield chunk

    def _build_payload(self, messages: list[BaseMessage], *, stop: list[str] | None, stream: bool, **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [self._serialize_message(message) for message in messages],
            "stream": stream,
            "temperature": self.temperature,
        }
        if stop:
            payload["stop"] = stop
        tools = kwargs.pop(_TOOLS_KWARG, None)
        if tools:
            payload["tools"] = tools
        tool_choice = kwargs.pop(_TOOL_CHOICE_KWARG, None)
        if tool_choice:
            payload["tool_choice"] = self._serialize_tool_choice(tool_choice)
        structured_output = kwargs.pop(_STRUCTURED_OUTPUT_KWARG, None)
        if structured_output:
            payload["structured_output"] = structured_output
        return payload

    def _serialize_message(self, message: BaseMessage) -> dict[str, Any]:
        if message.type == "system":
            return {"role": "system", "content": [{"type": "text", "text": self._content_to_text(message.content)}]}
        if message.type == "human":
            return {"role": "user", "content": [{"type": "text", "text": self._content_to_text(message.content)}]}
        if message.type == "tool":
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_call_id": getattr(message, "tool_call_id", "tool_call"),
                        "content": self._content_to_text(message.content),
                    }
                ],
            }

        content: list[dict[str, Any]] = []
        text_content = self._content_to_text(message.content)
        if text_content:
            content.append({"type": "text", "text": text_content})
        for tool_call in getattr(message, "tool_calls", []) or []:
            content.append(
                {
                    "type": "tool_call",
                    "id": tool_call.get("id", "tool_call"),
                    "name": tool_call.get("name", "tool"),
                    "arguments": tool_call.get("args", {}),
                }
            )
        return {"role": "assistant", "content": content}

    def _serialize_tool(self, tool: dict[str, Any] | type | Any) -> dict[str, Any]:
        converted = convert_to_openai_tool(tool)
        function = converted.get("function", {})
        return {
            "type": "function",
            "name": function.get("name", "tool"),
            "description": function.get("description"),
            "parameters": function.get("parameters") or {},
        }

    def _serialize_tool_choice(self, tool_choice: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(tool_choice, str):
            if tool_choice == "required":
                return {"type": "required"}
            return {"type": tool_choice}
        if tool_choice.get("type") == "function":
            function = tool_choice.get("function", {})
            return {"type": "tool", "name": function.get("name", "tool")}
        return tool_choice

    def _chat_result_from_response(self, payload: dict[str, Any]) -> ChatResult:
        message_payload = payload.get("message", {})
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in message_payload.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_call":
                tool_calls.append(
                    {
                        "id": block.get("id"),
                        "name": block.get("name"),
                        "args": block.get("arguments", {}),
                        "type": "tool_call",
                    }
                )

        ai_message = AIMessage(
            content="".join(text_parts),
            tool_calls=tool_calls,
            response_metadata={
                "finish_reason": payload.get("finish_reason"),
                "usage": payload.get("usage", {}),
                "model": payload.get("model"),
            },
            id=payload.get("id"),
        )
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    def _iter_sse_chunks(self, lines: Iterator[str]) -> Iterator[ChatGenerationChunk]:
        for line in lines:
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            frame = json.loads(data)
            chunk = self._chunk_from_frame(frame)
            if chunk is not None:
                yield chunk

    def _chunk_from_frame(self, frame: dict[str, Any]) -> ChatGenerationChunk | None:
        if frame.get("type") == "text_delta":
            return ChatGenerationChunk(message=AIMessageChunk(content=frame.get("text", "")))
        if frame.get("type") == "tool_call":
            return ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "id": frame.get("id"),
                            "name": frame.get("name"),
                            "args": json.dumps(frame.get("arguments", {})),
                            "index": 0,
                            "type": "tool_call_chunk",
                        }
                    ],
                )
            )
        if frame.get("type") == "completion":
            return ChatGenerationChunk(message=AIMessageChunk(content="", response_metadata={"finish_reason": frame.get("finish_reason")}))
        if frame.get("type") == "usage":
            return ChatGenerationChunk(message=AIMessageChunk(content="", response_metadata={"usage": frame.get("usage", {})}))
        return None

    def _content_to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content)
        return str(content)

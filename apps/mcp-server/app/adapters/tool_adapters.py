from __future__ import annotations

from app.contracts import (
    AddToolInput,
    AddToolOutput,
    EchoToolInput,
    EchoToolOutput,
    ToolDescriptor,
)


class ToolAdapterRegistry:
    def list_tools(self) -> list[ToolDescriptor]:
        return [
            ToolDescriptor(
                name="echo",
                title="Echo",
                description="Return the input text.",
                input_schema=EchoToolInput.model_json_schema(),
                output_schema=EchoToolOutput.model_json_schema(),
            ),
            ToolDescriptor(
                name="add",
                title="Add",
                description="Add two integers.",
                input_schema=AddToolInput.model_json_schema(),
                output_schema=AddToolOutput.model_json_schema(),
            ),
        ]

    def invoke_echo(self, args: EchoToolInput) -> EchoToolOutput:
        return EchoToolOutput(text=args.text)

    def invoke_add(self, args: AddToolInput) -> AddToolOutput:
        return AddToolOutput(sum=args.a + args.b)

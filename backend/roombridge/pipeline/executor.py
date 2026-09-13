"""Shared step executor: render an allowlisted prompt, call the model, validate, record.

Every call is persisted as an LLMCall with its rendered messages, seed, temperature, and
prompt version -- following MAD's practice of storing the prompt inline with each output
(sec5_infer_api.py:119). The ROOMBRIDGE_STEP marker is injected here, once, for all steps.
"""
from __future__ import annotations

import json
from typing import Type, TypeVar

from pydantic import BaseModel, RootModel, model_validator

from ..prompts import PromptContext, get_prompt
from ..prompts.registry import PromptSpec
from ..providers.base import StructuredProvider

T = TypeVar("T", bound=BaseModel)


class _ListResponse(RootModel[list[T]]):
    @model_validator(mode="before")
    @classmethod
    def _accept_single_object(cls, data):
        # Preserve support for models returning one item without array brackets.
        return [data] if isinstance(data, dict) else data


class StepExecutor:
    def __init__(self, provider: StructuredProvider, recorder, *, model: str):
        self.provider = provider
        self.recorder = recorder
        self.model = model

    def _messages(self, spec: PromptSpec, ctx: PromptContext) -> list[dict]:
        system = f"ROOMBRIDGE_STEP: {spec.step}\n\n" + ctx.format(spec.system)
        user = ctx.format(spec.user)
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def run_object(
        self, prompt_name: str, ctx: PromptContext, schema: Type[T],
        *, model: str | None = None, seed: int | None = None, temperature: float = 0.0,
    ) -> T:
        spec = get_prompt(prompt_name)
        messages = self._messages(spec, ctx)
        mdl = model or self.model
        obj, result = self.provider.complete_structured(
            messages, schema, model=mdl, seed=seed, temperature=temperature
        )
        self.recorder.record_call(
            step=spec.step, prompt_name=spec.name, prompt_version=spec.version, model=mdl,
            seed=seed, temperature=temperature, messages=messages, raw=result.raw,
            parsed=obj.model_dump(mode="json"), usage=result.usage, ok=True,
        )
        return obj

    def run_list(
        self, prompt_name: str, ctx: PromptContext, item_schema: Type[T],
        *, model: str | None = None, seed: int | None = None, temperature: float = 0.0,
    ) -> list[T]:
        spec = get_prompt(prompt_name)
        messages = self._messages(spec, ctx)
        schema = _ListResponse[item_schema]
        messages[0]["content"] += (
            "\n\nReturn ONLY a JSON array matching this schema. Use exactly the allowed "
            "enum values:\n" + json.dumps(schema.model_json_schema())
        )
        mdl = model or self.model
        response, result = self.provider.complete_structured(
            messages, schema, model=mdl, seed=seed, temperature=temperature
        )
        items = response.root
        self.recorder.record_call(
            step=spec.step, prompt_name=spec.name, prompt_version=spec.version, model=mdl,
            seed=seed, temperature=temperature, messages=messages, raw=result.raw,
            parsed={"items": [i.model_dump(mode="json") for i in items]},
            usage=result.usage, ok=True,
        )
        return items

"""List outputs get the same bounded schema repair as object outputs."""
import json
from unittest.mock import Mock

import pytest
from sqlmodel import select

from roombridge.conditions.registry import run_condition
from roombridge.domain import models as M
from roombridge.domain.contracts import AssumptionFinding
from roombridge.domain.db import session_scope
from roombridge.domain.enums import Condition, Severity
from roombridge.pipeline.executor import StepExecutor
from roombridge.prompts import PromptContext, get_prompt
from roombridge.providers.base import CallResult, LLMError, StructuredProvider
from roombridge.providers.mock import MockProvider


def finding(severity="flag"):
    return {"text": "An unstated preference", "assumption_type": "unstated_preference",
            "grounded_in_need_id": None, "severity": severity}


def execute(*responses):
    backend = Mock(name="text_provider")
    backend.complete_text.side_effect = [CallResult(raw=raw) for raw in responses]
    recorder = Mock()
    executor = StepExecutor(StructuredProvider(backend), recorder, model="test-model")
    ctx = PromptContext(get_prompt("check_assumptions").allowed_fields,
                        needs=[], agreement_text="Example agreement")
    return backend, recorder, lambda: executor.run_list(
        "check_assumptions", ctx, AssumptionFinding, seed=42, temperature=0.7
    )


@pytest.mark.parametrize("raw, count", [
    ("[]", 0),
    (json.dumps([finding()]), 1),
    (json.dumps(finding()), 1),
    ("```json\n" + json.dumps([finding()]) + "\n```", 1),
])
def test_valid_lists_and_single_objects(raw, count):
    backend, recorder, run = execute(raw)
    assert len(run()) == count
    assert backend.complete_text.call_count == 1
    assert recorder.record_call.call_args.kwargs["ok"] is True


@pytest.mark.parametrize("invalid", [
    json.dumps([finding("minor")]), "not JSON", "[null]",
])
def test_invalid_list_is_repaired(invalid):
    backend, recorder, run = execute(invalid, json.dumps([finding("note")]))
    assert run()[0].severity == Severity.NOTE
    first, retry = backend.complete_text.call_args_list
    schema = json.loads(first.args[0][0]["content"].split("enum values:\n", 1)[1])
    assert schema["type"] == "array"
    assert schema["$defs"]["Severity"]["enum"] == ["blocking", "flag", "note"]
    assert first.kwargs == {"model": "test-model", "seed": 42, "temperature": 0.7}
    assert retry.kwargs == {"model": "test-model", "seed": 42, "temperature": 0.0}
    assert retry.args[0][-2] == {"role": "assistant", "content": invalid}
    assert "Error:" in retry.args[0][-1]["content"]
    assert recorder.record_call.call_args.kwargs["parsed"] == {"items": [finding("note")]}


def test_repeated_invalid_severity_raises_typed_error():
    invalid = json.dumps([finding("minor")])
    backend, recorder, run = execute(invalid, invalid)
    with pytest.raises(LLMError, match="structured parse failed after repair"):
        run()
    assert backend.complete_text.call_count == 2
    recorder.record_call.assert_not_called()


def test_unrepairable_list_marks_run_failed_without_crashing():
    class InvalidAssumptionsProvider(MockProvider):
        def _step_check_assumptions(self, blob, messages):
            return json.dumps([finding("minor")])

    rid = run_condition(
        "sc_001_quiet_vs_social", Condition.B_CONTEXT,
        StructuredProvider(InvalidAssumptionsProvider()), model="mock", auditor_model="mock",
    )
    with session_scope() as session:
        run = session.exec(select(M.Run).where(M.Run.run_id == rid)).one()
        assert run.status == "failed"
        assert "structured parse failed after repair" in run.error

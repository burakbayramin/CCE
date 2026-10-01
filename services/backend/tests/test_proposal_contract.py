"""Schema drift must not be hidden by the web's filtered field-limit tables."""

import importlib.util
import json
from pathlib import Path

import pytest
from pydantic import ConfigDict, Field, create_model

from cce.modules.contributions.schemas import CharacterProposal

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/check_proposal_contract.py"
spec = importlib.util.spec_from_file_location("proposal_contract", SCRIPT)
assert spec is not None and spec.loader is not None
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def test_committed_proposal_contract_matches_backend():
    contract.main()


@pytest.mark.parametrize("change", ["minimum", "required", "extra", "new_field", "whitespace"])
def test_contract_captures_previously_untracked_schema_changes(change):
    if change == "minimum":
        model = create_model(
            "Minimum",
            __base__=CharacterProposal,
            name=(str, Field(default="", min_length=3, max_length=80)),
        )
    elif change == "required":
        model = create_model(
            "Required", __base__=CharacterProposal, occupation=(str, Field(max_length=120))
        )
    elif change == "extra":
        model = create_model(
            "Extra", __base__=CharacterProposal, __config__=ConfigDict(extra="allow")
        )
    elif change == "new_field":
        # A nullable structured field is absent from every filtered UI table.
        model = create_model("NewField", __base__=CharacterProposal, title=(dict | None, None))
    else:
        model = create_model(
            "Whitespace",
            __base__=CharacterProposal,
            __config__=ConfigDict(str_strip_whitespace=False),
        )
    expected = contract.limits(model)
    baseline = contract.limits()
    # Class titles alone must not be the reason this test passes.
    expected["validation_schema"].pop("title")
    baseline["validation_schema"].pop("title")
    assert expected != baseline


def test_contract_preserves_list_item_minimum_and_nested_extra_rule():
    schema = contract.limits()["validation_schema"]
    assert schema["properties"]["strengths"]["items"]["minLength"] == 1
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["Personality"]["additionalProperties"] is False


def test_contract_check_rejects_changed_validation_snapshot(tmp_path, monkeypatch):
    value = contract.limits()
    value["validation_schema"]["additionalProperties"] = True
    path = tmp_path / "proposal-contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setattr(contract, "CONTRACT", path)
    with pytest.raises(SystemExit, match="differs from Pydantic"):
        contract.main()

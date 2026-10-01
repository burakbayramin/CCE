"""Keep the web form limits in sync with the authoritative Pydantic model."""

import json
from pathlib import Path

from cce.modules.contributions.schemas import CharacterProposal, Personality
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "apps/web/src/features/character-submissions/proposal-contract.json"


def limits(proposal_model: type[BaseModel] = CharacterProposal) -> dict[str, object]:
    schema = proposal_model.model_json_schema()
    fields = schema["properties"]
    axes = Personality.model_json_schema()["properties"]
    texts = {
        name: spec["maxLength"]
        for name, spec in fields.items()
        if spec.get("type") == "string" and name != "schema_version"
    }
    lists = {
        name: {"max_items": spec["maxItems"], "max_length": spec["items"]["maxLength"]}
        for name, spec in fields.items()
        if spec.get("type") == "array"
    }
    return {
        # Include every field/type and all constraints, including required,
        # additionalProperties, enum/const, and list item minima. A newly added
        # field cannot silently disappear from the filtered UI limit tables.
        "validation_schema": schema,
        "strip_whitespace": proposal_model.model_config.get(
            "str_strip_whitespace", False
        ),
        "schema_version": fields["schema_version"]["default"],
        "texts": texts,
        "lists": lists,
        "axes": {
            name: {"min": spec["minimum"], "max": spec["maximum"]}
            for name, spec in axes.items()
        },
        "age": {"min": fields["age"]["minimum"], "max": fields["age"]["maximum"]},
        "confirmations": sorted(
            name for name, spec in fields.items() if spec.get("type") == "boolean"
        ),
    }


def main() -> None:
    expected = limits()
    actual = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if actual != expected:
        raise SystemExit(
            "Web proposal contract differs from Pydantic; update proposal-contract.json"
        )


if __name__ == "__main__":
    main()

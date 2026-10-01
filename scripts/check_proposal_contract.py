"""Keep the web form limits in sync with the authoritative Pydantic model."""

import json
from pathlib import Path

from cce.modules.contributions.schemas import CharacterProposal, Personality

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "apps/web/src/features/character-submissions/proposal-contract.json"


def limits() -> dict[str, object]:
    fields = CharacterProposal.model_json_schema()["properties"]
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

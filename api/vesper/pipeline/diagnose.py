"""Model call 1 of 2."""

from vesper.llm import provider
from vesper.pipeline._stage import StageFailed, load_prompt, validate_twice
from vesper.pipeline.evidence import EvidencePacket, as_prompt_block
from vesper.pipeline.schemas import Diagnosis


def diagnose(packet: EvidencePacket) -> Diagnosis:
    system = load_prompt("diagnose")
    schema = Diagnosis.model_json_schema()

    def call(user: str) -> str:
        return provider.complete_json("diagnose", system=system, user=user, schema=schema)

    try:
        return validate_twice(call, Diagnosis, as_prompt_block(packet))
    except provider.ProviderError as e:
        raise StageFailed(str(e)) from e

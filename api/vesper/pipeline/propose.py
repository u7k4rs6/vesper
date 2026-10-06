"""Model call 2 of 2. After this the model is out of the loop."""

from vesper.llm import provider
from vesper.pipeline._stage import StageFailed, load_prompt, validate_twice
from vesper.pipeline.evidence import EvidencePacket, as_prompt_block, sanitise
from vesper.pipeline.schemas import Diagnosis, Proposal


def propose(packet: EvidencePacket, diagnosis: Diagnosis) -> Proposal:
    system = load_prompt("propose")
    schema = Proposal.model_json_schema()
    # The diagnosis is model output; it goes back in as data, never as instructions.
    diag = diagnosis.model_copy(
        update={"cause": sanitise(diagnosis.cause, 240), "customer_context": sanitise(diagnosis.customer_context, 200)}
    )
    user = as_prompt_block(packet) + "\n<data>" + diag.model_dump_json() + "</data>"

    def call(text: str) -> str:
        return provider.complete_json("propose", system=system, user=text, schema=schema)

    try:
        return validate_twice(call, Proposal, user)
    except provider.ProviderError as e:
        raise StageFailed(str(e)) from e


"""OnboardUserTool — the first task a driver performs for a person module.

Runs a conversational onboarding session via ElevenLabs voice agent,
extracts entities and relationships from the person's answers, and
writes the initial sovereign graph.

Pipeline:
    1. Voice conversation (ElevenLabs agent asks structured questions)
    2. Entity extraction (Haiku) on the captured transcript
    3. Relationship extraction (Sonnet) between discovered entities
    4. Write Nodes and Assertions to the module's Solid vault
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pacific_core.driver import IngestResult
from pacific_core.extraction.entity_extractor import EntityExtractor
from pacific_core.extraction.relationship_extractor import RelationshipExtractor
from pacific_core.extraction.types import EntityMention
from pacific_core.ontology.namespace import PAC
from pacific_core.owner import OwnerType
from pacific_core.tools import Tool

from pacific_tools.onboard_user.conversation import run_onboarding_conversation

if TYPE_CHECKING:
    from pacific_core.module import Module

# Onboarding-derived assertions are high-mass, low-volatility — the person
# stated these facts about themselves directly.
ONBOARDING_MASS = 5.0
ONBOARDING_VOLATILITY = 0.1


class OnboardUserTool(Tool):
    """First task when a module's driver is initialised as a person.

    Runs a structured voice conversation to learn who the person is,
    who they work with, and what they're working on. Extracts entities
    and relationships from the transcript and bootstraps the sovereign graph.
    """

    @property
    def name(self) -> str:
        return "onboard-user"

    @property
    def description(self) -> str:
        return (
            "Run a conversational onboarding session with the module's owner "
            "to bootstrap the sovereign graph with initial entities and relationships."
        )

    async def run(self, module: Module, **kwargs: Any) -> IngestResult:
        """Run the onboarding pipeline.

        Kwargs:
            agent_id: ElevenLabs agent ID for the onboarding conversation.
            elevenlabs_api_key: API key override (defaults to env).

        Raises:
            RuntimeError: If the module's owner is not a person.
        """
        if module.owner.owner_type != OwnerType.PERSON:
            raise RuntimeError(
                f"onboard-user requires a PersonOwner, got {module.owner.owner_type.value}. "
                "Only person-initialised modules can be onboarded via conversation."
            )

        agent_id: str = kwargs.get("agent_id", "")
        if not agent_id:
            raise RuntimeError(
                "agent_id is required. Pass the ElevenLabs agent ID configured "
                "for onboarding."
            )
        api_key: str | None = kwargs.get("elevenlabs_api_key")

        # 1. Run the voice conversation
        transcript = await run_onboarding_conversation(
            agent_id=agent_id,
            owner_label=module.config.pod_url.rstrip("/").rsplit("/", 1)[-1],
            api_key=api_key,
        )

        if not transcript.user_text.strip():
            return IngestResult(
                tool_name=self.name,
                errors=["Onboarding conversation produced no user input."],
                metadata={"conversation_id": transcript.conversation_id},
            )

        # 2. Entity extraction on the full conversation
        entity_extractor = EntityExtractor(
            model=module.config.extraction_model,
            confidence_threshold=module.config.confidence_threshold,
        )
        rel_extractor = RelationshipExtractor(
            model=module.config.relationship_model,
            confidence_threshold=module.config.confidence_threshold,
        )

        errors: list[str] = []
        extraction = await entity_extractor.extract(transcript.full_text)

        # Deduplicate by label
        seen: dict[str, EntityMention] = {}
        for entity in extraction.entities:
            key = entity.label.lower()
            if key not in seen or entity.confidence > seen[key].confidence:
                seen[key] = entity
        unique_entities = list(seen.values())

        # 3. Write Nodes to the sovereign graph
        node_uris: dict[str, str] = {}
        for entity in unique_entities:
            try:
                uri = await module.ensure_node(
                    label=entity.label,
                    node_type=entity.entity_type,
                )
                node_uris[entity.label.lower()] = uri
            except Exception as e:
                errors.append(f"Node creation failed for {entity.label}: {e}")

        # 4. Relationship extraction between discovered entities
        relationships = await rel_extractor.extract(
            transcript.full_text, unique_entities,
        )

        # 5. Write Assertions — anchor everything to the owner's root node
        root = module.root_node_uri or ""
        assertion_count = 0
        now = datetime.now(timezone.utc).isoformat()

        for rel in relationships:
            source_uri = node_uris.get(rel.source.label.lower())
            target_uri = node_uris.get(rel.target.label.lower())
            if source_uri and target_uri:
                try:
                    await module.assert_triple(
                        subject_uri=source_uri,
                        predicate_uri=rel.predicate,
                        object_uri=target_uri,
                        valid_from=now,
                        mass=ONBOARDING_MASS,
                        volatility=ONBOARDING_VOLATILITY,
                        source=f"onboarding:{transcript.conversation_id}",
                        confidence=rel.confidence,
                    )
                    assertion_count += 1
                except Exception as e:
                    errors.append(
                        f"Assertion failed for {rel.source.label} -> {rel.target.label}: {e}"
                    )

        # 6. Assert that the owner knows each discovered person entity
        if root:
            for entity in unique_entities:
                if entity.entity_type == "person":
                    entity_uri = node_uris.get(entity.label.lower())
                    if entity_uri and entity_uri != root:
                        try:
                            await module.assert_triple(
                                subject_uri=root,
                                predicate_uri=str(PAC.knows),
                                object_uri=entity_uri,
                                valid_from=now,
                                mass=ONBOARDING_MASS,
                                volatility=ONBOARDING_VOLATILITY,
                                source=f"onboarding:{transcript.conversation_id}",
                                confidence=1.0,
                            )
                            assertion_count += 1
                        except Exception as e:
                            errors.append(f"Knows-assertion failed for {entity.label}: {e}")

        return IngestResult(
            tool_name=self.name,
            entities_extracted=len(node_uris),
            relationships_extracted=assertion_count,
            errors=errors,
            metadata={
                "conversation_id": transcript.conversation_id,
                "turns": len(transcript.turns),
                "user_turns": sum(1 for t in transcript.turns if t.role == "user"),
            },
        )

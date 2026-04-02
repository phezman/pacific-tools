"""Tests for the onboard-user tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from pacific_core.driver import IngestResult
from pacific_core.extraction.types import EntityMention, ExtractionResult, RelationshipMention
from pacific_core.owner import OwnerType

from pacific_onboard_user.conversation import OnboardingTranscript, Turn
from pacific_onboard_user.tool import OnboardUserTool


# ── Fakes ────────────────────────────────────────────────────────────────────


class FakeOwner:
    def __init__(self, owner_type: OwnerType = OwnerType.PERSON) -> None:
        self._owner_type = owner_type

    @property
    def owner_type(self) -> OwnerType:
        return self._owner_type


class FakeConfig:
    pod_url = "https://alice.solidcommunity.net/"
    extraction_model = "claude-haiku-4-5-20251001"
    relationship_model = "claude-sonnet-4-5-20241022"
    confidence_threshold = 0.6


class FakeModule:
    def __init__(self, owner_type: OwnerType = OwnerType.PERSON) -> None:
        self.config = FakeConfig()
        self._owner = FakeOwner(owner_type)
        self.root_node_uri = "https://alice.solidcommunity.net/vault/nodes/alice"
        self._nodes_created: list[dict] = []
        self._assertions_created: list[dict] = []

    @property
    def owner(self) -> FakeOwner:
        return self._owner

    async def ensure_node(self, label: str, node_type: str, **kwargs: str) -> str:
        uri = f"https://alice.solidcommunity.net/vault/nodes/{label.lower().replace(' ', '-')}"
        self._nodes_created.append({"label": label, "node_type": node_type, "uri": uri})
        return uri

    async def assert_triple(self, subject_uri: str, predicate_uri: str, object_uri: str, **kw) -> str:
        uri = f"https://alice.solidcommunity.net/vault/assertions/{len(self._assertions_created)}"
        self._assertions_created.append({
            "subject": subject_uri,
            "predicate": predicate_uri,
            "object": object_uri,
            **kw,
        })
        return uri


# ── Fixtures ─────────────────────────────────────────────────────────────────


SAMPLE_TRANSCRIPT = OnboardingTranscript(
    turns=[
        Turn(role="agent", text="Hi Alice! Let's get you set up. What do you do?"),
        Turn(role="user", text="I'm a product manager at Acme Corp. I work closely with Bob Smith on the engineering team."),
        Turn(role="agent", text="Got it. What are you currently focused on?"),
        Turn(role="user", text="We're building a new payments integration with Stripe."),
    ],
    conversation_id="conv-abc-123",
)

SAMPLE_ENTITIES = [
    EntityMention(label="Alice", entity_type="person", confidence=0.95),
    EntityMention(label="Bob Smith", entity_type="person", confidence=0.9),
    EntityMention(label="Acme Corp", entity_type="organization", confidence=0.95),
    EntityMention(label="Stripe", entity_type="organization", confidence=0.85),
    EntityMention(label="payments integration", entity_type="topic", confidence=0.8),
]

SAMPLE_RELATIONSHIPS = [
    RelationshipMention(
        source=SAMPLE_ENTITIES[0],  # Alice
        target=SAMPLE_ENTITIES[2],  # Acme Corp
        predicate="https://pacific.systems/ontology/worksAt",
        description="Alice works at Acme Corp",
        confidence=0.9,
    ),
    RelationshipMention(
        source=SAMPLE_ENTITIES[1],  # Bob Smith
        target=SAMPLE_ENTITIES[2],  # Acme Corp
        predicate="https://pacific.systems/ontology/worksAt",
        description="Bob Smith works at Acme Corp",
        confidence=0.85,
    ),
]


# ── Tests ────────────────────────────────────────────────────────────────────


class TestOnboardUserTool:
    def test_name_and_description(self):
        tool = OnboardUserTool()
        assert tool.name == "onboard-user"
        assert "onboarding" in tool.description.lower()

    async def test_rejects_board_owner(self):
        tool = OnboardUserTool()
        module = FakeModule(owner_type=OwnerType.BOARD)
        with pytest.raises(RuntimeError, match="PersonOwner"):
            await tool.run(module, agent_id="agent-1")

    async def test_requires_agent_id(self):
        tool = OnboardUserTool()
        module = FakeModule()
        with pytest.raises(RuntimeError, match="agent_id"):
            await tool.run(module)

    @patch("pacific_onboard_user.tool.run_onboarding_conversation")
    @patch("pacific_onboard_user.tool.RelationshipExtractor")
    @patch("pacific_onboard_user.tool.EntityExtractor")
    async def test_full_pipeline(self, MockEntity, MockRel, mock_convo):
        mock_convo.return_value = SAMPLE_TRANSCRIPT

        entity_instance = MockEntity.return_value
        entity_instance.extract = AsyncMock(
            return_value=ExtractionResult(entities=SAMPLE_ENTITIES)
        )

        rel_instance = MockRel.return_value
        rel_instance.extract = AsyncMock(return_value=SAMPLE_RELATIONSHIPS)

        tool = OnboardUserTool()
        module = FakeModule()
        result = await tool.run(module, agent_id="agent-1")

        assert isinstance(result, IngestResult)
        assert result.tool_name == "onboard-user"
        assert result.entities_extracted == 5
        assert result.errors == []
        assert result.metadata["conversation_id"] == "conv-abc-123"
        assert result.metadata["turns"] == 4
        assert result.metadata["user_turns"] == 2

        # Verify nodes were created
        assert len(module._nodes_created) == 5
        labels = {n["label"] for n in module._nodes_created}
        assert "Bob Smith" in labels
        assert "Acme Corp" in labels

        # Verify relationship assertions were written
        assert len(module._assertions_created) >= 2

    @patch("pacific_onboard_user.tool.run_onboarding_conversation")
    async def test_empty_conversation(self, mock_convo):
        mock_convo.return_value = OnboardingTranscript(
            turns=[Turn(role="agent", text="Hi! Tell me about yourself.")],
            conversation_id="conv-empty",
        )

        tool = OnboardUserTool()
        module = FakeModule()
        result = await tool.run(module, agent_id="agent-1")

        assert result.entities_extracted == 0
        assert "no user input" in result.errors[0].lower()

    @patch("pacific_onboard_user.tool.run_onboarding_conversation")
    @patch("pacific_onboard_user.tool.RelationshipExtractor")
    @patch("pacific_onboard_user.tool.EntityExtractor")
    async def test_knows_assertions_for_person_entities(self, MockEntity, MockRel, mock_convo):
        """The tool should assert owner --knows--> every discovered person."""
        mock_convo.return_value = SAMPLE_TRANSCRIPT

        entity_instance = MockEntity.return_value
        entity_instance.extract = AsyncMock(
            return_value=ExtractionResult(entities=SAMPLE_ENTITIES)
        )

        rel_instance = MockRel.return_value
        rel_instance.extract = AsyncMock(return_value=[])

        tool = OnboardUserTool()
        module = FakeModule()
        result = await tool.run(module, agent_id="agent-1")

        knows_assertions = [
            a for a in module._assertions_created
            if a["predicate"] == "https://pacific.systems/ontology/knows"
        ]
        assert len(knows_assertions) >= 1
        assert all(a["confidence"] == 1.0 for a in knows_assertions)
        assert all(a["source"].startswith("onboarding:") for a in knows_assertions)


class TestOnboardingTranscript:
    def test_user_text(self):
        t = OnboardingTranscript(
            turns=[
                Turn(role="agent", text="Hello"),
                Turn(role="user", text="I'm Alice"),
                Turn(role="agent", text="What do you do?"),
                Turn(role="user", text="Product management"),
            ]
        )
        assert t.user_text == "I'm Alice\nProduct management"

    def test_full_text(self):
        t = OnboardingTranscript(
            turns=[Turn(role="agent", text="Hi"), Turn(role="user", text="Hello")]
        )
        assert t.full_text == "agent: Hi\nuser: Hello"

    def test_empty_transcript(self):
        t = OnboardingTranscript()
        assert t.user_text == ""
        assert t.full_text == ""

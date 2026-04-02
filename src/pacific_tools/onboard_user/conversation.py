"""Conversation manager — captures an ElevenLabs onboarding session as a transcript.

The conversation runs through a pre-configured ElevenLabs agent that asks
structured onboarding questions. This module captures the full transcript
(both agent and user turns) for downstream entity/relationship extraction.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from elevenlabs import AsyncElevenLabs
from elevenlabs.conversational_ai.conversation import (
    AsyncConversation,
    ConversationInitiationData,
)
from elevenlabs.conversational_ai.default_audio_interface import AsyncDefaultAudioInterface

if TYPE_CHECKING:
    from pacific_core.config import ModuleConfig


@dataclass
class Turn:
    """A single turn in the onboarding conversation."""

    role: str  # "agent" or "user"
    text: str


@dataclass
class OnboardingTranscript:
    """The captured transcript of an onboarding session."""

    turns: list[Turn] = field(default_factory=list)
    conversation_id: str = ""

    @property
    def user_text(self) -> str:
        """All user turns concatenated — the primary extraction input."""
        return "\n".join(t.text for t in self.turns if t.role == "user")

    @property
    def full_text(self) -> str:
        """Full conversation for context-aware extraction."""
        return "\n".join(f"{t.role}: {t.text}" for t in self.turns)


async def run_onboarding_conversation(
    *,
    agent_id: str,
    owner_label: str,
    api_key: str | None = None,
) -> OnboardingTranscript:
    """Run the onboarding conversation and return the transcript.

    Starts an ElevenLabs voice agent session, captures all turns, and
    blocks until the session ends (either the agent concludes or the
    user hangs up).

    Args:
        agent_id: ElevenLabs agent ID configured for onboarding.
        owner_label: The person's name — injected as a dynamic variable.
        api_key: ElevenLabs API key (falls back to ELEVENLABS_API_KEY env).

    Returns:
        OnboardingTranscript with all captured turns.
    """
    client = AsyncElevenLabs(api_key=api_key) if api_key else AsyncElevenLabs()
    audio = AsyncDefaultAudioInterface()
    transcript = OnboardingTranscript()

    async def on_agent_response(text: str) -> None:
        transcript.turns.append(Turn(role="agent", text=text))

    async def on_user_transcript(text: str) -> None:
        transcript.turns.append(Turn(role="user", text=text))

    conversation = AsyncConversation(
        client=client,
        agent_id=agent_id,
        requires_auth=True,
        audio_interface=audio,
        config=ConversationInitiationData(
            dynamic_variables={"owner_name": owner_label},
        ),
        callback_agent_response=on_agent_response,
        callback_user_transcript=on_user_transcript,
    )

    conversation.start_session()
    conversation_id = await conversation.wait_for_session_end()
    transcript.conversation_id = conversation_id

    return transcript

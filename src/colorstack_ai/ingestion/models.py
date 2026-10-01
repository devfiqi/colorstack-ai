from datetime import datetime

from pydantic import BaseModel, Field


class IngestionModel(BaseModel):
    pass


class NormalizedAttachment(IngestionModel):
    id: str
    name: str | None
    url: str
    content_type: str | None = Field(serialization_alias="contentType")
    size: int


class NormalizedReaction(IngestionModel):
    emoji: str
    count: int


class NormalizedDiscordMessage(IngestionModel):
    id: str
    guild_id: str | None = Field(serialization_alias="guildId")
    channel_id: str = Field(serialization_alias="channelId")
    channel_name: str | None = Field(serialization_alias="channelName")
    thread_id: str | None = Field(serialization_alias="threadId")
    author_id: str = Field(serialization_alias="authorId")
    username: str
    display_name: str | None = Field(serialization_alias="displayName")
    content: str
    created_at: datetime = Field(serialization_alias="createdAt")
    edited_at: datetime | None = Field(serialization_alias="editedAt")
    reply_to_message_id: str | None = Field(
        serialization_alias="replyToMessageId"
    )
    attachments: list[NormalizedAttachment]
    reactions: list[NormalizedReaction]


class DeletedDiscordMessage(IngestionModel):
    id: str
    guild_id: str | None = Field(serialization_alias="guildId")
    channel_id: str = Field(serialization_alias="channelId")
    deleted_at: datetime = Field(serialization_alias="deletedAt")

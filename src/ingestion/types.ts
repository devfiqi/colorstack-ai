export type NormalizedAttachment = {
  id: string;
  name: string | null;
  url: string;
  contentType: string | null;
  size: number;
};

export type NormalizedReaction = {
  emoji: string;
  count: number;
};

export type NormalizedDiscordMessage = {
  id: string;
  guildId: string | null;
  channelId: string;
  channelName: string | null;
  threadId: string | null;
  authorId: string;
  username: string;
  displayName: string | null;
  content: string;
  createdAt: Date;
  editedAt: Date | null;
  replyToMessageId: string | null;
  attachments: NormalizedAttachment[];
  reactions: NormalizedReaction[];
};

export type DeletedDiscordMessage = {
  id: string;
  guildId: string | null;
  channelId: string;
  deletedAt: Date;
};

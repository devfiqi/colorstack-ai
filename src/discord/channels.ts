import {
  ChannelType,
  PermissionFlagsBits,
  type ForumChannel,
  type Guild,
  type MediaChannel,
  type NewsChannel,
  type TextChannel,
  type ThreadChannel,
} from "discord.js";

export type ReadableMessageChannel =
  | TextChannel
  | NewsChannel
  | ThreadChannel;

type ThreadParent =
  | TextChannel
  | NewsChannel
  | ForumChannel
  | MediaChannel;

function canRead(
  guild: Guild,
  channel: ReadableMessageChannel | ThreadParent,
): boolean {
  const me = guild.members.me;
  if (!me) return false;

  const permissions = channel.permissionsFor(me);
  return (
    permissions?.has(PermissionFlagsBits.ViewChannel) === true &&
    permissions.has(PermissionFlagsBits.ReadMessageHistory)
  );
}

async function fetchArchivedThreads(
  parent: ThreadParent,
  type: "public" | "private",
): Promise<ThreadChannel[]> {
  const threads: ThreadChannel[] = [];
  let before: Date | ThreadChannel | undefined;
  const me = parent.guild.members.me;
  const fetchAllPrivate =
    type === "private" &&
    me !== null &&
    parent.permissionsFor(me)?.has(PermissionFlagsBits.ManageThreads) === true;

  while (true) {
    const page = await parent.threads.fetchArchived({
      type,
      fetchAll: fetchAllPrivate,
      limit: 100,
      before,
    });

    threads.push(...page.threads.values());
    if (!page.hasMore || page.threads.size === 0) break;

    const oldestTimestamp = Math.min(
      ...page.threads.map(
        (thread) => thread.archiveTimestamp ?? Number.POSITIVE_INFINITY,
      ),
    );
    if (!Number.isFinite(oldestTimestamp)) break;

    if (type === "private" && !fetchAllPrivate) {
      const oldestThread = page.threads.reduce<ThreadChannel | undefined>(
        (oldest, thread) =>
          !oldest ||
          (thread.archiveTimestamp ?? Number.POSITIVE_INFINITY) <
            (oldest.archiveTimestamp ?? Number.POSITIVE_INFINITY)
            ? thread
            : oldest,
        undefined,
      );
      if (!oldestThread) break;
      before = oldestThread;
    } else {
      before = new Date(oldestTimestamp);
    }
  }

  return threads;
}

export async function findReadableMessageChannels(
  guild: Guild,
): Promise<ReadableMessageChannel[]> {
  const channels = await guild.channels.fetch();
  const readable = new Map<string, ReadableMessageChannel>();
  const threadParents: ThreadParent[] = [];

  for (const channel of channels.values()) {
    if (!channel) continue;

    if (
      (channel.type === ChannelType.GuildText ||
        channel.type === ChannelType.GuildAnnouncement) &&
      canRead(guild, channel)
    ) {
      readable.set(channel.id, channel);
    }

    if (
      channel.type === ChannelType.GuildText ||
      channel.type === ChannelType.GuildAnnouncement ||
      channel.type === ChannelType.GuildForum ||
      channel.type === ChannelType.GuildMedia
    ) {
      if (canRead(guild, channel)) threadParents.push(channel);
    }
  }

  try {
    const active = await guild.channels.fetchActiveThreads();
    for (const thread of active.threads.values()) {
      if (canRead(guild, thread)) readable.set(thread.id, thread);
    }
  } catch (error) {
    console.warn(`Could not fetch active threads in ${guild.name}:`, error);
  }

  for (const parent of threadParents) {
    const threadTypes: Array<"public" | "private"> =
      parent.type === ChannelType.GuildAnnouncement
        ? ["public"]
        : parent.type === ChannelType.GuildText
          ? ["public", "private"]
          : ["public"];

    for (const type of threadTypes) {
      try {
        const archived = await fetchArchivedThreads(parent, type);
        for (const thread of archived) {
          if (canRead(guild, thread)) readable.set(thread.id, thread);
        }
      } catch (error) {
        console.warn(
          `Could not fetch archived threads for #${parent.name} (${type}):`,
          error,
        );
      }
    }
  }

  return [...readable.values()];
}

import { createReadStream } from "node:fs";
import { appendFile, mkdir, open } from "node:fs/promises";
import { dirname } from "node:path";
import { createInterface } from "node:readline";
import type {
  DeletedDiscordMessage,
  NormalizedDiscordMessage,
} from "./types.js";

export interface MessageStore {
  has(messageId: string): boolean;
  insert(message: NormalizedDiscordMessage): Promise<boolean>;
  upsert(message: NormalizedDiscordMessage): Promise<void>;
  markDeleted(deletion: DeletedDiscordMessage): Promise<void>;
  close(): Promise<void>;
}

type StoredOperation =
  | {
      operation: "upsert";
      recordedAt: string;
      message: NormalizedDiscordMessage;
    }
  | {
      operation: "delete";
      recordedAt: string;
      deletion: DeletedDiscordMessage;
    };

/**
 * An append-only local verification store. Repeated upserts preserve edit history,
 * while the interface can later be implemented by PostgreSQL without changing the
 * Discord ingestion code.
 */
export class JsonlMessageStore implements MessageStore {
  private readonly knownMessageIds = new Set<string>();
  private writeQueue: Promise<void> = Promise.resolve();

  private constructor(private readonly filePath: string) {}

  static async create(filePath: string): Promise<JsonlMessageStore> {
    const store = new JsonlMessageStore(filePath);
    await mkdir(dirname(filePath), { recursive: true });

    const handle = await open(filePath, "a");
    await handle.close();
    await store.loadKnownMessageIds();

    return store;
  }

  has(messageId: string): boolean {
    return this.knownMessageIds.has(messageId);
  }

  async insert(message: NormalizedDiscordMessage): Promise<boolean> {
    if (this.has(message.id)) {
      return false;
    }

    this.knownMessageIds.add(message.id);
    await this.append({
      operation: "upsert",
      recordedAt: new Date().toISOString(),
      message,
    });
    return true;
  }

  async upsert(message: NormalizedDiscordMessage): Promise<void> {
    this.knownMessageIds.add(message.id);
    await this.append({
      operation: "upsert",
      recordedAt: new Date().toISOString(),
      message,
    });
  }

  async markDeleted(deletion: DeletedDiscordMessage): Promise<void> {
    await this.append({
      operation: "delete",
      recordedAt: new Date().toISOString(),
      deletion,
    });
  }

  async close(): Promise<void> {
    await this.writeQueue;
  }

  private async loadKnownMessageIds(): Promise<void> {
    const lines = createInterface({
      input: createReadStream(this.filePath, { encoding: "utf8" }),
      crlfDelay: Infinity,
    });

    for await (const line of lines) {
      if (!line.trim()) continue;

      try {
        const record = JSON.parse(line) as StoredOperation;
        if (record.operation === "upsert") {
          this.knownMessageIds.add(record.message.id);
        }
      } catch {
        console.warn(`Skipping malformed record in ${this.filePath}`);
      }
    }
  }

  private append(record: StoredOperation): Promise<void> {
    this.writeQueue = this.writeQueue.then(async () => {
      await appendFile(this.filePath, `${JSON.stringify(record)}\n`, "utf8");
    });

    return this.writeQueue;
  }
}

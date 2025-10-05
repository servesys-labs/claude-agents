#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { createClient } from "redis";

// Initialize Redis client
const redisUrl = process.env.REDIS_URL || "redis://localhost:6379";
const client = createClient({ url: redisUrl });

client.on("error", (err) => console.error("Redis Client Error", err));

await client.connect();

// Create server
const server = new Server(
  {
    name: "redis-bridge",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "get",
        description: "Get value for a key",
        inputSchema: {
          type: "object",
          properties: {
            key: {
              type: "string",
              description: "Redis key",
            },
          },
          required: ["key"],
        },
      },
      {
        name: "set",
        description: "Set key-value pair",
        inputSchema: {
          type: "object",
          properties: {
            key: {
              type: "string",
              description: "Redis key",
            },
            value: {
              type: "string",
              description: "Value to set",
            },
            ex: {
              type: "number",
              description: "Expiration in seconds (optional)",
            },
          },
          required: ["key", "value"],
        },
      },
      {
        name: "del",
        description: "Delete one or more keys",
        inputSchema: {
          type: "object",
          properties: {
            keys: {
              type: "array",
              items: { type: "string" },
              description: "Array of keys to delete",
            },
          },
          required: ["keys"],
        },
      },
      {
        name: "keys",
        description: "Find keys matching a pattern",
        inputSchema: {
          type: "object",
          properties: {
            pattern: {
              type: "string",
              description: "Pattern to match (e.g., 'user:*', '*session*')",
            },
          },
          required: ["pattern"],
        },
      },
      {
        name: "ttl",
        description: "Get time-to-live for a key",
        inputSchema: {
          type: "object",
          properties: {
            key: {
              type: "string",
              description: "Redis key",
            },
          },
          required: ["key"],
        },
      },
      {
        name: "exists",
        description: "Check if key(s) exist",
        inputSchema: {
          type: "object",
          properties: {
            keys: {
              type: "array",
              items: { type: "string" },
              description: "Array of keys to check",
            },
          },
          required: ["keys"],
        },
      },
      {
        name: "info",
        description: "Get Redis server info and stats",
        inputSchema: {
          type: "object",
          properties: {
            section: {
              type: "string",
              enum: ["all", "server", "clients", "memory", "persistence", "stats", "replication"],
              description: "Info section (default: all)",
              default: "all",
            },
          },
        },
      },
      {
        name: "flushdb",
        description: "Clear current database (use with caution!)",
        inputSchema: {
          type: "object",
          properties: {
            confirm: {
              type: "boolean",
              description: "Must be true to confirm deletion",
            },
          },
          required: ["confirm"],
        },
      },
      {
        name: "hget",
        description: "Get field value from hash",
        inputSchema: {
          type: "object",
          properties: {
            key: {
              type: "string",
              description: "Hash key",
            },
            field: {
              type: "string",
              description: "Field name",
            },
          },
          required: ["key", "field"],
        },
      },
      {
        name: "hgetall",
        description: "Get all fields and values from hash",
        inputSchema: {
          type: "object",
          properties: {
            key: {
              type: "string",
              description: "Hash key",
            },
          },
          required: ["key"],
        },
      },
      {
        name: "hset",
        description: "Set field in hash",
        inputSchema: {
          type: "object",
          properties: {
            key: {
              type: "string",
              description: "Hash key",
            },
            field: {
              type: "string",
              description: "Field name",
            },
            value: {
              type: "string",
              description: "Value to set",
            },
          },
          required: ["key", "field", "value"],
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    if (name === "get") {
      const { key } = args as { key: string };
      const value = await client.get(key);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ key, value }, null, 2),
          },
        ],
      };
    }

    if (name === "set") {
      const { key, value, ex } = args as { key: string; value: string; ex?: number };

      if (ex) {
        await client.set(key, value, { EX: ex });
      } else {
        await client.set(key, value);
      }

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ success: true, key, value, ex }, null, 2),
          },
        ],
      };
    }

    if (name === "del") {
      const { keys } = args as { keys: string[] };
      const count = await client.del(keys);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ deleted: count, keys }, null, 2),
          },
        ],
      };
    }

    if (name === "keys") {
      const { pattern } = args as { pattern: string };
      const keys = await client.keys(pattern);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ pattern, count: keys.length, keys }, null, 2),
          },
        ],
      };
    }

    if (name === "ttl") {
      const { key } = args as { key: string };
      const ttl = await client.ttl(key);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                key,
                ttl,
                description:
                  ttl === -1
                    ? "No expiration"
                    : ttl === -2
                    ? "Key does not exist"
                    : `Expires in ${ttl} seconds`,
              },
              null,
              2
            ),
          },
        ],
      };
    }

    if (name === "exists") {
      const { keys } = args as { keys: string[] };
      const count = await client.exists(keys);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ exists: count, keys }, null, 2),
          },
        ],
      };
    }

    if (name === "info") {
      const { section = "all" } = args as { section?: string };
      const info = section === "all" ? await client.info() : await client.info(section);

      // Parse info string into object
      const lines = info.split("\r\n");
      const parsed: any = {};
      let currentSection = "";

      for (const line of lines) {
        if (line.startsWith("#")) {
          currentSection = line.substring(2).trim();
          parsed[currentSection] = {};
        } else if (line.includes(":")) {
          const [key, value] = line.split(":");
          if (currentSection) {
            parsed[currentSection][key] = value;
          }
        }
      }

      return {
        content: [{ type: "text", text: JSON.stringify(parsed, null, 2) }],
      };
    }

    if (name === "flushdb") {
      const { confirm } = args as { confirm: boolean };

      if (!confirm) {
        return {
          content: [
            {
              type: "text",
              text: "Error: Must set confirm=true to flush database",
            },
          ],
          isError: true,
        };
      }

      await client.flushDb();

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ success: true, message: "Database flushed" }, null, 2),
          },
        ],
      };
    }

    if (name === "hget") {
      const { key, field } = args as { key: string; field: string };
      const value = await client.hGet(key, field);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ key, field, value }, null, 2),
          },
        ],
      };
    }

    if (name === "hgetall") {
      const { key } = args as { key: string };
      const value = await client.hGetAll(key);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ key, value }, null, 2),
          },
        ],
      };
    }

    if (name === "hset") {
      const { key, field, value } = args as { key: string; field: string; value: string };
      await client.hSet(key, field, value);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ success: true, key, field, value }, null, 2),
          },
        ],
      };
    }

    return {
      content: [{ type: "text", text: `Unknown tool: ${name}` }],
      isError: true,
    };
  } catch (error: any) {
    return {
      content: [
        {
          type: "text",
          text: `Redis error: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});

// Cleanup on exit
process.on("SIGINT", async () => {
  await client.disconnect();
  process.exit(0);
});

process.on("SIGTERM", async () => {
  await client.disconnect();
  process.exit(0);
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Redis Bridge MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});

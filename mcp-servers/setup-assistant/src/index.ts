#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { execSync } from "child_process";
import { readFileSync, writeFileSync, existsSync } from "fs";
import { homedir } from "os";
import { join } from "path";

const server = new Server(
  {
    name: "setup-assistant",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Paths for shell config
const SHELL_CONFIGS = [
  join(homedir(), ".zshrc"),
  join(homedir(), ".bashrc"),
  join(homedir(), ".bash_profile"),
];

function getShellConfig(): string {
  // Find which shell config exists
  for (const config of SHELL_CONFIGS) {
    if (existsSync(config)) {
      return config;
    }
  }
  // Default to .zshrc (most common on macOS)
  return SHELL_CONFIGS[0];
}

function checkEnvVar(varName: string): { set: boolean; value?: string } {
  const value = process.env[varName];
  return {
    set: !!value && value !== "",
    value: value || undefined,
  };
}

async function testDatabaseConnection(url: string): Promise<{ success: boolean; error?: string }> {
  try {
    // Use psql to test connection
    execSync(`psql "${url}" -c "SELECT 1" 2>&1`, { timeout: 5000 });
    return { success: true };
  } catch (error: any) {
    return { success: false, error: error.message };
  }
}

async function testRedisConnection(url: string): Promise<{ success: boolean; error?: string }> {
  try {
    // Use redis-cli to test connection
    const redisUrl = new URL(url);
    const host = redisUrl.hostname;
    const port = redisUrl.port || "6379";
    const password = redisUrl.password;

    const cmd = password
      ? `redis-cli -h ${host} -p ${port} -a ${password} PING 2>&1`
      : `redis-cli -h ${host} -p ${port} PING 2>&1`;

    const result = execSync(cmd, { timeout: 5000 }).toString();
    return { success: result.includes("PONG") };
  } catch (error: any) {
    return { success: false, error: error.message };
  }
}

function saveEnvVar(varName: string, value: string): { success: boolean; message: string } {
  try {
    const configPath = getShellConfig();
    let content = "";

    if (existsSync(configPath)) {
      content = readFileSync(configPath, "utf-8");
    }

    // Check if variable already exists
    const regex = new RegExp(`^export ${varName}=.*$`, "m");
    const exists = regex.test(content);

    if (exists) {
      // Update existing
      content = content.replace(regex, `export ${varName}="${value}"`);
    } else {
      // Append new
      content += `\n# Claude Orchestration Framework - Vector Memory\nexport ${varName}="${value}"\n`;
    }

    writeFileSync(configPath, content);

    return {
      success: true,
      message: `✅ Saved ${varName} to ${configPath}\n⚠️  Run: source ${configPath}`,
    };
  } catch (error: any) {
    return {
      success: false,
      message: `❌ Failed to save: ${error.message}`,
    };
  }
}

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "check_vector_memory_setup",
        description: "Check if Vector RAG Memory environment variables are configured correctly",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "save_credential",
        description: "Save a credential to shell configuration file (~/.zshrc or ~/.bashrc)",
        inputSchema: {
          type: "object",
          properties: {
            var_name: {
              type: "string",
              enum: ["DATABASE_URL_MEMORY", "REDIS_URL", "OPENAI_API_KEY", "ENABLE_VECTOR_RAG"],
              description: "Environment variable name",
            },
            value: {
              type: "string",
              description: "Value to save",
            },
          },
          required: ["var_name", "value"],
        },
      },
      {
        name: "test_database_connection",
        description: "Test PostgreSQL database connection using provided URL",
        inputSchema: {
          type: "object",
          properties: {
            url: {
              type: "string",
              description: "PostgreSQL connection string (postgresql://user:pass@host:port/db)",
            },
          },
          required: ["url"],
        },
      },
      {
        name: "test_redis_connection",
        description: "Test Redis connection using provided URL",
        inputSchema: {
          type: "object",
          properties: {
            url: {
              type: "string",
              description: "Redis connection string (redis://user:pass@host:port)",
            },
          },
          required: ["url"],
        },
      },
      {
        name: "get_railway_instructions",
        description: "Get step-by-step instructions for finding Railway credentials",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "get_supabase_instructions",
        description: "Get step-by-step instructions for setting up Supabase (pgvector)",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "check_vector_memory_setup": {
        const checks = {
          DATABASE_URL_MEMORY: checkEnvVar("DATABASE_URL_MEMORY"),
          REDIS_URL: checkEnvVar("REDIS_URL"),
          OPENAI_API_KEY: checkEnvVar("OPENAI_API_KEY"),
          ENABLE_VECTOR_RAG: checkEnvVar("ENABLE_VECTOR_RAG"),
        };

        const shellConfig = getShellConfig();
        const allSet = Object.values(checks).every((c) => c.set);

        let report = "# Vector RAG Memory Setup Status\n\n";

        for (const [varName, status] of Object.entries(checks)) {
          const icon = status.set ? "✅" : "❌";
          const masked = status.value && varName !== "ENABLE_VECTOR_RAG"
            ? status.value.substring(0, 20) + "..."
            : status.value;
          report += `${icon} ${varName}: ${status.set ? masked : "NOT SET"}\n`;
        }

        report += `\n**Shell Config**: ${shellConfig}\n`;

        if (!allSet) {
          report += `\n## ⚠️ Missing Credentials\n\n`;
          report += `Use the following tools to set up:\n`;
          report += `1. \`get_railway_instructions\` - Get Railway credentials\n`;
          report += `2. \`save_credential\` - Save each credential\n`;
          report += `3. \`test_database_connection\` - Verify database works\n`;
          report += `4. \`test_redis_connection\` - Verify Redis works\n`;
        } else {
          report += `\n✅ All credentials are set!\n`;
          report += `\nVector RAG Memory will automatically ingest DIGEST blocks to your database.\n`;
        }

        return {
          content: [{ type: "text", text: report }],
        };
      }

      case "save_credential": {
        const { var_name, value } = args as { var_name: string; value: string };
        const result = saveEnvVar(var_name, value);

        return {
          content: [{ type: "text", text: result.message }],
        };
      }

      case "test_database_connection": {
        const { url } = args as { url: string };
        const result = await testDatabaseConnection(url);

        const message = result.success
          ? `✅ Database connection successful!\n\nYou can now save this with:\n\`save_credential(var_name="DATABASE_URL_MEMORY", value="<your_url>")\``
          : `❌ Database connection failed:\n${result.error}\n\nPlease check your connection string.`;

        return {
          content: [{ type: "text", text: message }],
        };
      }

      case "test_redis_connection": {
        const { url } = args as { url: string };
        const result = await testRedisConnection(url);

        const message = result.success
          ? `✅ Redis connection successful!\n\nYou can now save this with:\n\`save_credential(var_name="REDIS_URL", value="<your_url>")\``
          : `❌ Redis connection failed:\n${result.error}\n\nPlease check your connection string.`;

        return {
          content: [{ type: "text", text: message }],
        };
      }

      case "get_railway_instructions": {
        const instructions = `# Getting Railway Credentials

## Step 1: Go to Railway Dashboard
Visit: https://railway.app/dashboard

## Step 2: Find Your pgvector Database
1. Select your project
2. Find the PostgreSQL service (the one with pgvector extension)
3. Click on the service
4. Go to "Variables" tab
5. Copy the \`DATABASE_URL\` value

## Step 3: Find Your Redis Service
1. In the same project, find the Redis service
2. Click on it
3. Go to "Variables" tab
4. Copy the \`REDIS_URL\` value

## Step 4: Test and Save
Use these tools:
\`\`\`
test_database_connection(url="postgresql://...")
test_redis_connection(url="redis://...")
save_credential(var_name="DATABASE_URL_MEMORY", value="postgresql://...")
save_credential(var_name="REDIS_URL", value="redis://...")
save_credential(var_name="ENABLE_VECTOR_RAG", value="true")
\`\`\`

## Step 5: Get OpenAI API Key
1. Visit: https://platform.openai.com/api-keys
2. Create a new API key
3. Save it:
\`\`\`
save_credential(var_name="OPENAI_API_KEY", value="sk-...")
\`\`\`

## Step 6: Reload Shell
\`\`\`bash
source ~/.zshrc  # or ~/.bashrc
\`\`\`

Then restart Claude Code to pick up the new environment variables.
`;

        return {
          content: [{ type: "text", text: instructions }],
        };
      }

      case "get_supabase_instructions": {
        const instructions = `# Setting Up Supabase (Managed pgvector)

## Step 1: Create Supabase Project
1. Visit: https://supabase.com
2. Create a new project (free tier available)
3. Wait for project to initialize (~2 minutes)

## Step 2: Enable pgvector Extension
1. Go to "Database" → "Extensions"
2. Search for "vector"
3. Enable the \`vector\` extension

## Step 3: Get Connection String
1. Go to "Project Settings" → "Database"
2. Find "Connection string" → "URI"
3. Copy the connection string

## Step 4: Get Service Role Key
1. Go to "Project Settings" → "API"
2. Copy the \`service_role\` key (not anon key!)

## Step 5: Save Credentials
\`\`\`
save_credential(var_name="DATABASE_URL_MEMORY", value="postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres")
save_credential(var_name="SUPABASE_SERVICE_KEY", value="eyJ...")
save_credential(var_name="ENABLE_VECTOR_RAG", value="true")
\`\`\`

## Step 6: Get OpenAI API Key
1. Visit: https://platform.openai.com/api-keys
2. Create a new API key
3. Save it:
\`\`\`
save_credential(var_name="OPENAI_API_KEY", value="sk-...")
\`\`\`

## Step 7: Reload Shell
\`\`\`bash
source ~/.zshrc  # or ~/.bashrc
\`\`\`

Then restart Claude Code.
`;

        return {
          content: [{ type: "text", text: instructions }],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error: any) {
    return {
      content: [
        {
          type: "text",
          text: `Error: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Setup Assistant MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});

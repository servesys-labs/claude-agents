#!/usr/bin/env node
/**
 * Vector Bridge MCP Server
 * Global memory/RAG service for Claude Code across all projects
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { z } from 'zod';
import { PgVectorProvider } from './providers/pgvector.provider.js';
import { SolutionProvider } from './providers/solution.provider.js';
import {
  memoryIngestSchema,
  memoryIngestTool,
} from './tools/memory-ingest.tool.js';
import {
  memorySearchSchema,
  memorySearchTool,
} from './tools/memory-search.tool.js';
import {
  memoryProjectsSchema,
  memoryProjectsTool,
} from './tools/memory-projects.tool.js';
import {
  autoSetupSchema,
  autoSetupTool,
  saveCredentialsSchema,
  saveCredentialsTool,
} from './tools/auto-setup.tool.js';

// Initialize providers with Redis cache
const DATABASE_URL = process.env.DATABASE_URL_MEMORY || process.env.DATABASE_URL;
const provider = new PgVectorProvider(DATABASE_URL, process.env.REDIS_URL);
const solutionProvider = new SolutionProvider(DATABASE_URL, process.env.REDIS_URL);

// Create MCP server
const server = new Server(
  {
    name: 'vector-bridge',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Register tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'memory_ingest',
        description:
          'Ingest text content into global vector store. Chunks text and creates embeddings for semantic search.',
        inputSchema: {
          type: 'object',
          properties: {
            project_root: {
              type: 'string',
              description: 'Absolute path to project root (e.g., /Users/name/project)',
            },
            path: {
              type: 'string',
              description: 'Relative path within project (e.g., src/utils/helper.ts)',
            },
            text: {
              type: 'string',
              description: 'Text content to chunk and index',
            },
            meta: {
              type: 'object',
              description: 'Optional metadata to attach to chunks',
            },
          },
          required: ['project_root', 'path', 'text'],
        },
      },
      {
        name: 'memory_search',
        description:
          'Search for similar chunks using semantic similarity. Returns top-k most relevant chunks.',
        inputSchema: {
          type: 'object',
          properties: {
            project_root: {
              type: 'string',
              description: 'Project root to search within',
            },
            query: {
              type: 'string',
              description: 'Search query text',
            },
            k: {
              type: 'number',
              description: 'Number of results (default: 8, max: 20)',
              default: 8,
            },
            global: {
              type: 'boolean',
              description: 'Search across all projects (default: false)',
              default: false,
            },
          },
          required: ['project_root', 'query'],
        },
      },
      {
        name: 'memory_projects',
        description:
          'List all indexed projects with statistics (document count, last updated)',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'solution_search',
        description:
          'Search for solution fixpacks matching an error message using vector semantic search. Returns ranked solutions with confidence scores, remediation steps, and success rates.',
        inputSchema: {
          type: 'object',
          properties: {
            error_message: {
              type: 'string',
              description: 'Error message to search for (full error text for best results)',
            },
            category: {
              type: 'string',
              enum: ['devops', 'deploy', 'workspace', 'tsconfig', 'migration', 'build', 'runtime', 'test', 'security', 'performance'],
              description: 'Optional: Filter by solution category',
            },
            component: {
              type: 'string',
              description: 'Optional: Filter by component (e.g., backend, frontend, mobile)',
            },
            limit: {
              type: 'number',
              description: 'Maximum number of solutions to return (default: 5)',
              default: 5,
            },
          },
          required: ['error_message'],
        },
      },
      {
        name: 'solution_apply',
        description:
          'Record that a solution was applied and whether it succeeded (for success rate tracking). Use after manually applying a fixpack to help improve solution recommendations.',
        inputSchema: {
          type: 'object',
          properties: {
            solution_id: {
              type: 'number',
              description: 'ID of the solution that was applied',
            },
            success: {
              type: 'boolean',
              description: 'Whether the solution successfully fixed the issue',
            },
          },
          required: ['solution_id', 'success'],
        },
      },
      {
        name: "solution_preview",
        description: "DRY-RUN preview of applying a solution fixpack. Shows what would be executed without making changes. Use before solution_apply to understand impact.",
        inputSchema: {
          type: "object",
          properties: {
            solution_id: {
              type: "number",
              description: "ID of the solution to preview",
            },
          },
          required: ["solution_id"],
        },
      },

      {
        name: 'solution_upsert',
        description:
          'Create a new solution fixpack or update an existing one. Solutions are reusable templates for fixing recurring errors.',
        inputSchema: {
          type: 'object',
          properties: {
            title: {
              type: 'string',
              description: 'Short descriptive title (e.g., "Fix TypeScript Module Not Found")',
            },
            description: {
              type: 'string',
              description: 'Detailed description of the problem and solution',
            },
            category: {
              type: 'string',
              enum: ['devops', 'deploy', 'workspace', 'tsconfig', 'migration', 'build', 'runtime', 'test', 'security', 'performance'],
              description: 'Solution category',
            },
            component: {
              type: 'string',
              description: 'Optional: Component this solution applies to',
            },
            tags: {
              type: 'array',
              items: { type: 'string' },
              description: 'Tags for filtering (e.g., ["typescript", "module-resolution"])',
            },
            project_root: {
              type: 'string',
              description: 'Optional: Specific project this solution applies to',
            },
            package_manager: {
              type: 'string',
              description: 'Optional: Package manager (npm, pnpm, yarn)',
            },
            monorepo_tool: {
              type: 'string',
              description: 'Optional: Monorepo tool (nx, turborepo, lerna)',
            },
            signatures: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  text: {
                    type: 'string',
                    description: 'Error message pattern to match (used for both regex and semantic search)',
                  },
                  regexes: {
                    type: 'array',
                    items: { type: 'string' },
                    description: 'Optional: Regex patterns for exact matching',
                  },
                  meta: {
                    type: 'object',
                    description: 'Optional: Additional metadata',
                  },
                },
                required: ['text'],
              },
              description: 'Error signatures that trigger this solution',
            },
            steps: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  step_order: {
                    type: 'number',
                    description: 'Execution order (1, 2, 3, ...)',
                  },
                  kind: {
                    type: 'string',
                    enum: ['cmd', 'patch', 'copy', 'script', 'env'],
                    description: 'Type of action to perform',
                  },
                  payload: {
                    type: 'object',
                    description: 'Action-specific data (e.g., {command: "npm install"})',
                  },
                  description: {
                    type: 'string',
                    description: 'Human-readable description of this step',
                  },
                  timeout_ms: {
                    type: 'number',
                    description: 'Timeout in milliseconds (default: 120000)',
                    default: 120000,
                  },
                },
                required: ['step_order', 'kind', 'payload'],
              },
              description: 'Ordered remediation steps',
            },
            checks: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  check_order: {
                    type: 'number',
                    description: 'Execution order',
                  },
                  cmd: {
                    type: 'string',
                    description: 'Command to run for validation',
                  },
                  expect_substring: {
                    type: 'string',
                    description: 'Expected command output (optional)',
                  },
                  expect_exit_code: {
                    type: 'number',
                    description: 'Expected exit code (default: 0)',
                    default: 0,
                  },
                  timeout_ms: {
                    type: 'number',
                    description: 'Timeout in milliseconds (default: 30000)',
                    default: 30000,
                  },
                },
                required: ['check_order', 'cmd'],
              },
              description: 'Validation checks (pre-flight, post-fix, rollback)',
            },
          },
          required: ['title', 'description', 'category', 'signatures', 'steps'],
        },
      },
      {
        name: 'auto_setup_credentials',
        description: autoSetupSchema.description,
        inputSchema: autoSetupSchema.inputSchema,
      },
      {
        name: 'save_credentials',
        description: saveCredentialsSchema.description,
        inputSchema: saveCredentialsSchema.inputSchema,
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'memory_ingest': {
        const validated = memoryIngestSchema.parse(args);
        const result = await memoryIngestTool(validated, provider);
        return {
          content: [{ type: 'text', text: result }],
        };
      }

      case 'memory_search': {
        const validated = memorySearchSchema.parse(args);
        const result = await memorySearchTool(validated, provider);
        return {
          content: [{ type: 'text', text: result }],
        };
      }

      case 'memory_projects': {
        const validated = memoryProjectsSchema.parse(args);
        const result = await memoryProjectsTool(validated, provider);
        return {
          content: [{ type: 'text', text: result }],
        };
      }

      case 'solution_search': {
        const schema = z.object({
          error_message: z.string(),
          category: z.enum(['devops', 'deploy', 'workspace', 'tsconfig', 'migration', 'build', 'runtime', 'test', 'security', 'performance']).optional(),
          component: z.string().optional(),
          limit: z.number().optional().default(5),
        });
        const validated = schema.parse(args);

        const matches = await solutionProvider.findSolutions(
          validated.error_message,
          {
            category: validated.category,
            component: validated.component,
          },
          validated.limit
        );

        // Format as markdown
        let output = `Found ${matches.length} matching solutions:\n\n`;

        for (let i = 0; i < matches.length; i++) {
          const match = matches[i];
          const sol = match.solution;

          output += `## ${i + 1}. ${sol.title} (Confidence: ${(match.score * 100).toFixed(0)}%)\n`;
          output += `**Category:** ${sol.category}\n`;
          output += `**Success Rate:** ${(sol.success_rate * 100).toFixed(0)}% (applied ${sol.success_count + sol.failure_count} times)\n\n`;

          if (sol.description) {
            output += `**Description:**\n${sol.description}\n\n`;
          }

          // Fetch full details including steps and checks
          const details = await solutionProvider.getSolution(sol.id, true);

          if (details?.steps && details.steps.length > 0) {
            output += `**Remediation Steps:**\n`;
            for (const step of details.steps) {
              output += `${step.step_order}. [${step.kind}] ${step.description || 'No description'}\n`;
              if (step.kind === 'cmd' && step.payload.command) {
                output += `   \`${step.payload.command}\`\n`;
              }
            }
            output += `\n`;
          }

          if (details?.checks && details.checks.length > 0) {
            output += `**Validation Checks:**\n`;
            for (const check of details.checks) {
              output += `- \`${check.cmd}\` (exit code: ${check.expect_exit_code})\n`;
            }
            output += `\n`;
          }

          output += `**Apply this solution:** Use \`solution_apply\` with solution_id=${sol.id}\n\n`;
          output += `---\n\n`;
        }

        if (matches.length === 0) {
          output = `No solutions found matching: "${validated.error_message}"\n\nConsider creating a new fixpack with \`solution_upsert\` if you solve this manually.`;
        }

        return {
          content: [{ type: 'text', text: output }],
        };
      }

      case "solution_preview": {
        const schema = z.object({
          solution_id: z.number(),
        });
        const validated = schema.parse(args);

        const details = await solutionProvider.getSolution(validated.solution_id, true);
        if (!details) {
          return {
            content: [{ type: "text", text: `❌ Solution #${validated.solution_id} not found` }],
          };
        }

        const sol = details.solution;
        let output = `# DRY-RUN Preview: ${sol.title}\n\n`;
        output += `**Category:** ${sol.category}\n`;
        output += `**Success Rate:** ${(sol.success_rate * 100).toFixed(0)}% (${sol.success_count}/${sol.success_count + sol.failure_count} successful)\n\n`;

        if (sol.description) {
          output += `**Description:**\n${sol.description}\n\n`;
        }

        output += `## ⚠️  The following actions would be executed:\n\n`;

        if (details.steps && details.steps.length > 0) {
          output += `### Remediation Steps:\n`;
          for (const step of details.steps) {
            output += `${step.step_order}. **[${step.kind.toUpperCase()}]** ${step.description || "No description"}\n`;

            switch (step.kind) {
              case "cmd":
                output += `   Command: \`${step.payload.command}\`\n`;
                output += `   Timeout: ${step.timeout_ms || 30000}ms\n`;
                break;
              case "patch":
                output += `   File: \`${step.payload.file}\`\n`;
                output += `   Search: \`${step.payload.search?.substring(0, 50)}...\`\n`;
                output += `   Replace: \`${step.payload.replace?.substring(0, 50)}...\`\n`;
                break;
              case "copy":
                output += `   From: \`${step.payload.from}\`\n`;
                output += `   To: \`${step.payload.to}\`\n`;
                break;
              case "env":
                output += `   Variable: \`${step.payload.key}\`\n`;
                output += `   Value: \`${step.payload.value}\`\n`;
                break;
            }
            output += `\n`;
          }
        }

        if (details.checks && details.checks.length > 0) {
          output += `### Validation Checks (would run after applying):\n`;
          for (const check of details.checks) {
            output += `${check.check_order}. \`${check.cmd}\`\n`;
            output += `   Expected exit code: ${check.expect_exit_code ?? 0}\n`;
            if (check.expect_substring) {
              output += `   Expected output: contains "${check.expect_substring}"\n`;
            }
            output += `\n`;
          }
        }

        output += `\n---\n\n`;
        output += `**To apply this solution:** Run \`solution_apply\` with solution_id=${sol.id} after manually executing the steps above.\n\n`;
        output += `⚠️  **IMPORTANT:** This is a DRY-RUN preview only. No changes have been made.\n`;

        return {
          content: [{ type: "text", text: output }],
        };
      }


      case 'solution_apply': {
        const schema = z.object({
          solution_id: z.number(),
          success: z.boolean(),
        });
        const validated = schema.parse(args);

        await solutionProvider.recordApplication(validated.solution_id, validated.success);

        // Get updated success rate
        const solution = await solutionProvider.getSolution(validated.solution_id, false);

        const output = validated.success
          ? `✅ Success recorded for solution #${validated.solution_id}\nNew success rate: ${((solution?.solution.success_rate || 0) * 100).toFixed(0)}%`
          : `❌ Failure recorded for solution #${validated.solution_id}\nSuccess rate: ${((solution?.solution.success_rate || 0) * 100).toFixed(0)}%`;

        return {
          content: [{ type: 'text', text: output }],
        };
      }

      case 'solution_upsert': {
        const schema = z.object({
          title: z.string(),
          description: z.string(),
          category: z.enum(['devops', 'deploy', 'workspace', 'tsconfig', 'migration', 'build', 'runtime', 'test', 'security', 'performance']),
          component: z.string().optional(),
          tags: z.array(z.string()).optional(),
          project_root: z.string().optional(),
          package_manager: z.string().optional(),
          monorepo_tool: z.string().optional(),
          signatures: z.array(z.object({
            text: z.string(),
            regexes: z.array(z.string()).optional(),
            meta: z.record(z.any()).optional(),
          })),
          steps: z.array(z.object({
            step_order: z.number(),
            kind: z.enum(['cmd', 'patch', 'copy', 'script', 'env']),
            payload: z.record(z.any()),
            description: z.string().optional(),
            timeout_ms: z.number().optional(),
          })),
          checks: z.array(z.object({
            check_order: z.number(),
            cmd: z.string(),
            expect_substring: z.string().optional(),
            expect_exit_code: z.number().optional(),
            timeout_ms: z.number().optional(),
          })).optional(),
        });
        const validated = schema.parse(args);

        const solutionId = await solutionProvider.createSolution(validated);

        const output = `✅ Created solution #${solutionId}: ${validated.title}\n` +
          `Category: ${validated.category}\n` +
          `Signatures: ${validated.signatures.length}\n` +
          `Steps: ${validated.steps.length}\n` +
          `Checks: ${validated.checks?.length || 0}`;

        return {
          content: [{ type: 'text', text: output }],
        };
      }

      case 'auto_setup_credentials': {
        const result = await autoSetupTool(args);
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      case 'save_credentials': {
        const result = await saveCredentialsTool(args);
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error: any) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              success: false,
              error: error.message,
              stack: error.stack,
            },
            null,
            2
          ),
        },
      ],
      isError: true,
    };
  }
});

// Cleanup on shutdown
process.on('SIGINT', async () => {
  console.error('Shutting down Vector Bridge MCP server...');
  await solutionProvider.close();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.error('Shutting down Vector Bridge MCP server...');
  await solutionProvider.close();
  process.exit(0);
});

// Health check - verify database and Redis connectivity
async function healthCheck() {
  const checks = {
    database: false,
    redis: false,
  };

  // Check PostgreSQL connection
  try {
    const result = await provider['pool'].query('SELECT 1 as ping');
    if (result.rows[0].ping === 1) {
      checks.database = true;
      console.error('[Health] ✅ PostgreSQL connected');
    }
  } catch (error: any) {
    console.error('[Health] ❌ PostgreSQL connection failed:', error.message);
    console.error('[Health] DATABASE_URL_MEMORY:', process.env.DATABASE_URL_MEMORY ? 'set' : 'missing');
    console.error('[Health] DATABASE_URL:', process.env.DATABASE_URL ? 'set' : 'missing');
  }

  // Check Redis connection (non-fatal)
  if (provider['cache']) {
    try {
      const isConnected = await provider['cache']['redis']?.ping();
      if (isConnected === 'PONG') {
        checks.redis = true;
        console.error('[Health] ✅ Redis connected');
      }
    } catch (error: any) {
      console.error('[Health] ⚠️  Redis unavailable (running in fallback mode):', error.message);
      console.error('[Health] REDIS_URL:', process.env.REDIS_URL ? 'set' : 'missing');
    }
  } else {
    console.error('[Health] ⚠️  Redis not configured (running without cache)');
  }

  // Database is required, Redis is optional
  if (!checks.database) {
    throw new Error('Database health check failed - cannot start server');
  }

  console.error(`[Health] Service ready (DB: ${checks.database ? '✅' : '❌'}, Redis: ${checks.redis ? '✅' : '⚠️'})`);
}

// Start server
async function main() {
  // Run health checks before starting
  await healthCheck();

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('Vector Bridge MCP server running on stdio');
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});

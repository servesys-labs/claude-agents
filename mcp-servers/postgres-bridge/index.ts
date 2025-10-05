#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import pg from "pg";

const { Pool } = pg;

// Initialize Postgres connection
const connectionString = process.env.DATABASE_URL;
if (!connectionString) {
  console.error("Error: DATABASE_URL environment variable is required");
  process.exit(1);
}

// === Schema Cache (1h TTL) ===
interface CacheEntry {
  data: any;
  expiresAt: number;
}

const schemaCache = new Map<string, CacheEntry>();
const SCHEMA_CACHE_TTL_MS = 3600000; // 1 hour

function getCachedSchema(cacheKey: string): any | null {
  const entry = schemaCache.get(cacheKey);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    schemaCache.delete(cacheKey);
    return null;
  }
  console.error(`[Schema Cache] HIT: ${cacheKey}`);
  return entry.data;
}

function setCachedSchema(cacheKey: string, data: any): void {
  schemaCache.set(cacheKey, {
    data,
    expiresAt: Date.now() + SCHEMA_CACHE_TTL_MS,
  });
  console.error(`[Schema Cache] SET: ${cacheKey} (TTL: 1h)`);
}

setInterval(() => {
  const now = Date.now();
  for (const [key, entry] of schemaCache.entries()) {
    if (now > entry.expiresAt) schemaCache.delete(key);
  }
}, 600000);
// ===


const pool = new Pool({
  connectionString,
  max: 10,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// SQL Safety Validator
interface ValidationResult {
  safe: boolean;
  issues: string[];
  warnings: string[];
}

function validateSQL(sql: string): ValidationResult {
  const result: ValidationResult = {
    safe: true,
    issues: [],
    warnings: [],
  };

  const trimmed = sql.trim();
  const upperSQL = trimmed.toUpperCase();

  // Single-statement guard: reject semicolons (multiple statements)
  const statementCount = trimmed.split(';').filter(s => s.trim()).length;
  if (statementCount > 1 || trimmed.includes(';')) {
    result.safe = false;
    result.issues.push("Multiple statements not allowed (semicolon detected)");
  }

  // Block CTE tricks and DDL/DML keywords
  const dangerousKeywords = [
    /\bDO\b/i,
    /\bBEGIN\b/i,
    /\bCOMMIT\b/i,
    /\bROLLBACK\b/i,
    /\bCREATE\b/i,
    /\bALTER\b/i,
    /\bDROP\b/i,
    /\bTRUNCATE\b/i,
    /\bDELETE\b/i,
    /\bUPDATE\b/i,
    /\bINSERT\b/i,
    /\bMERGE\b/i,
  ];

  for (const keyword of dangerousKeywords) {
    if (keyword.test(trimmed)) {
      result.safe = false;
      result.issues.push(`Blocked keyword: ${keyword.source}`);
    }
  }

  // Additional destructive patterns (kept for backward compatibility)
  const destructivePatterns = [
    /DROP\s+(TABLE|DATABASE|SCHEMA|INDEX)/i,
    /TRUNCATE/i,
    /ALTER\s+TABLE/i,
    /CREATE\s+OR\s+REPLACE/i,
  ];

  for (const pattern of destructivePatterns) {
    if (pattern.test(trimmed)) {
      result.safe = false;
      result.issues.push(`Blocked destructive operation: ${pattern.source}`);
    }
  }

  // Enforce SELECT-only
  if (!upperSQL.startsWith("SELECT") && !upperSQL.startsWith("WITH")) {
    result.safe = false;
    result.issues.push("Only SELECT queries allowed (or WITH...SELECT for CTEs)");
  }

  // If it's a WITH clause, ensure it ends with SELECT
  if (upperSQL.startsWith("WITH")) {
    const selectIndex = upperSQL.lastIndexOf("SELECT");
    if (selectIndex === -1) {
      result.safe = false;
      result.issues.push("WITH clause must end with SELECT");
    }
  }

  // Require LIMIT on SELECT queries
  if (upperSQL.startsWith("SELECT") && !upperSQL.includes("LIMIT")) {
    result.warnings.push("SELECT query missing LIMIT clause - will auto-add LIMIT 100");
  }

  // Warn on expensive operations
  if (/JOIN.*JOIN.*JOIN/i.test(trimmed)) {
    result.warnings.push("Multiple JOINs detected - query may be slow");
  }

  if (/SELECT\s+\*/i.test(trimmed)) {
    result.warnings.push("SELECT * detected - consider specifying columns");
  }

  return result;
}

function autoAddLimit(sql: string): string {
  const upperSQL = sql.trim().toUpperCase();
  if (upperSQL.startsWith("SELECT") && !upperSQL.includes("LIMIT")) {
    return sql.trim() + " LIMIT 100";
  }
  return sql;
}

// Session statistics
interface SessionStats {
  queriesExecuted: number;
  rowsReturned: number;
  errorsEncountered: number;
}

const sessionStats: SessionStats = {
  queriesExecuted: 0,
  rowsReturned: 0,
  errorsEncountered: 0,
};

// Create server
const server = new Server(
  {
    name: "postgres-bridge",
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
        name: "query",
        description: "Execute a read-only SQL query with automatic safety validation and LIMIT enforcement",
        inputSchema: {
          type: "object",
          properties: {
            sql: {
              type: "string",
              description: "SQL query to execute (SELECT only, auto-adds LIMIT 100 if missing)",
            },
            params: {
              type: "array",
              items: { type: "string" },
              description: "Optional parameterized query values ($1, $2, etc.)",
            },
          },
          required: ["sql"],
        },
      },
      {
        name: "explain",
        description: "Analyze query execution plan with EXPLAIN (read-only, safe, does not execute)",
        inputSchema: {
          type: "object",
          properties: {
            sql: {
              type: "string",
              description: "SQL query to analyze",
            },
          },
          required: ["sql"],
        },
      },
      {
        name: "schema",
        description: "Get database schema information (tables, columns, types, indexes)",
        inputSchema: {
          type: "object",
          properties: {
            table: {
              type: "string",
              description: "Specific table name (omit for all tables)",
            },
            include_indexes: {
              type: "boolean",
              description: "Include index information (default: false)",
              default: false,
            },
          },
        },
      },
      {
        name: "table_stats",
        description: "Get table statistics (row count, size, last update)",
        inputSchema: {
          type: "object",
          properties: {
            table: {
              type: "string",
              description: "Table name",
            },
          },
          required: ["table"],
        },
      },
      {
        name: "get_session_stats",
        description: "Get current session statistics (queries executed, rows returned, errors)",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "generate_sql",
        description: "Generate SQL from natural language query using AI. Auto-validates and runs EXPLAIN first.",
        inputSchema: {
          type: "object",
          properties: {
            prompt: {
              type: "string",
              description: "Natural language description of the query (e.g., 'show me all users who signed up last week')",
            },
            execute: {
              type: "boolean",
              description: "Execute the generated SQL (default: false, will only generate and validate)",
              default: false,
            },
            ai_provider: {
              type: "string",
              enum: ["openai", "gemini"],
              description: "AI provider to use for generation (default: gemini for cost efficiency)",
              default: "gemini",
            },
          },
          required: ["prompt"],
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    if (name === "query") {
      const { sql, params = [] } = args as { sql: string; params?: any[] };

      // Validate SQL
      const validation = validateSQL(sql);
      if (!validation.safe) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  error: "Query blocked by safety validator",
                  issues: validation.issues,
                },
                null,
                2
              ),
            },
          ],
          isError: true,
        };
      }

      // Auto-add LIMIT
      const safeSql = autoAddLimit(sql);

      // Execute in read-only transaction to prevent CTE tricks
      const client = await pool.connect();
      let result;
      try {
        await client.query('BEGIN READ ONLY');
        result = await client.query(safeSql, params);
        await client.query('ROLLBACK'); // Always rollback read-only txn
      } finally {
        client.release();
      }

      sessionStats.queriesExecuted++;
      sessionStats.rowsReturned += result.rowCount || 0;

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                rows: result.rows,
                rowCount: result.rowCount,
                warnings: validation.warnings,
                query: safeSql,
              },
              null,
              2
            ),
          },
        ],
      };
    }

    if (name === "explain") {
      const { sql } = args as { sql: string };

      // Validate it's a SELECT
      if (!sql.trim().toUpperCase().startsWith("SELECT")) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                { error: "EXPLAIN only works with SELECT queries" },
                null,
                2
              ),
            },
          ],
          isError: true,
        };
      }

      // Use EXPLAIN without ANALYZE - doesn't execute, just plans
      const explainSql = `EXPLAIN (FORMAT JSON, COSTS true) ${sql}`;
      const result = await pool.query(explainSql);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(result.rows[0]["QUERY PLAN"], null, 2),
          },
        ],
      };
    }

    if (name === "schema") {
      const { table, include_indexes = false } = args as {
        table?: string;
        include_indexes?: boolean;
      };

      // Check cache first
      const cacheKey = `schema:${table || "all"}:indexes=${include_indexes}`;
      const cached = getCachedSchema(cacheKey);
      if (cached) {
        return {
          content: [{ type: "text", text: JSON.stringify(cached, null, 2) }],
        };
      }


      let schemaQuery = `
        SELECT
          table_name,
          column_name,
          data_type,
          is_nullable,
          column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
      `;

      if (table) {
        schemaQuery += ` AND table_name = $1`;
      }

      schemaQuery += ` ORDER BY table_name, ordinal_position`;

      const result = table
        ? await pool.query(schemaQuery, [table])
        : await pool.query(schemaQuery);

      let response: any = {
        tables: {},
      };

      // Group by table
      for (const row of result.rows) {
        if (!response.tables[row.table_name]) {
          response.tables[row.table_name] = {
            columns: [],
          };
        }
        response.tables[row.table_name].columns.push({
          name: row.column_name,
          type: row.data_type,
          nullable: row.is_nullable === "YES",
          default: row.column_default,
        });
      }

      if (include_indexes) {
        const indexQuery = `
          SELECT
            tablename,
            indexname,
            indexdef
          FROM pg_indexes
          WHERE schemaname = 'public'
          ${table ? "AND tablename = $1" : ""}
        `;

        const indexResult = table
          ? await pool.query(indexQuery, [table])
          : await pool.query(indexQuery);

        for (const row of indexResult.rows) {
          if (response.tables[row.tablename]) {
            if (!response.tables[row.tablename].indexes) {
              response.tables[row.tablename].indexes = [];
            }
            response.tables[row.tablename].indexes.push({
              name: row.indexname,
              definition: row.indexdef,
            });
          }
        }
      }

      // Cache the response
      setCachedSchema(cacheKey, response);


      return {
        content: [{ type: "text", text: JSON.stringify(response, null, 2) }],
      };
    }

    if (name === "table_stats") {
      const { table } = args as { table: string };

      const statsQuery = `
        SELECT
          schemaname,
          tablename,
          pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
          n_live_tup AS row_count,
          last_vacuum,
          last_autovacuum,
          last_analyze,
          last_autoanalyze
        FROM pg_stat_user_tables
        WHERE tablename = $1
      `;

      const result = await pool.query(statsQuery, [table]);

      if (result.rows.length === 0) {
        return {
          content: [
            { type: "text", text: JSON.stringify({ error: "Table not found" }, null, 2) },
          ],
          isError: true,
        };
      }

      return {
        content: [{ type: "text", text: JSON.stringify(result.rows[0], null, 2) }],
      };
    }

    if (name === "get_session_stats") {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                queries_executed: sessionStats.queriesExecuted,
                rows_returned: sessionStats.rowsReturned,
                errors_encountered: sessionStats.errorsEncountered,
              },
              null,
              2
            ),
          },
        ],
      };
    }

    if (name === "generate_sql") {
      const { prompt, execute = false, ai_provider = "gemini" } = args as {
        prompt: string;
        execute?: boolean;
        ai_provider?: string;
      };

      // Get schema for context
      const schemaResult = await pool.query(`
        SELECT
          table_name,
          column_name,
          data_type,
          is_nullable,
          column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
      `);

      // Build schema context
      const schemaContext: any = {};
      for (const row of schemaResult.rows) {
        if (!schemaContext[row.table_name]) {
          schemaContext[row.table_name] = [];
        }
        schemaContext[row.table_name].push({
          column: row.column_name,
          type: row.data_type,
          nullable: row.is_nullable === "YES",
        });
      }

      const schemaDescription = Object.entries(schemaContext)
        .map(([table, columns]) => {
          const cols = (columns as any[])
            .map((c) => `${c.column} (${c.type}${c.nullable ? ", nullable" : ""})`)
            .join(", ");
          return `${table}: ${cols}`;
        })
        .join("\n");

      // Generate SQL using AI
      const aiPrompt = `You are a PostgreSQL expert. Generate a valid PostgreSQL query for the following request.

Database Schema:
${schemaDescription}

User Request: ${prompt}

Requirements:
1. Generate ONLY the SQL query, no explanations
2. Use proper PostgreSQL syntax
3. The query MUST be read-only (SELECT only)
4. Include appropriate JOINs if needed
5. Add a LIMIT clause if the result set could be large
6. Use table/column names exactly as shown in the schema

SQL Query:`;

      let generatedSQL: string;

      try {
        if (ai_provider === "openai") {
          // Note: This requires the openai-bridge MCP to be available
          // In practice, this would be called via MCP client mechanism
          // For now, returning placeholder indicating external dependency
          return {
            content: [
              {
                type: "text",
                text: JSON.stringify(
                  {
                    error: "OpenAI integration requires MCP client call - use Gemini for now",
                    suggestion: "Set ai_provider to 'gemini'",
                  },
                  null,
                  2
                ),
              },
            ],
            isError: true,
          };
        } else {
          // Use Gemini via environment variable API key
          const geminiApiKey = process.env.GEMINI_API_KEY;
          if (!geminiApiKey) {
            return {
              content: [
                {
                  type: "text",
                  text: JSON.stringify(
                    {
                      error: "GEMINI_API_KEY environment variable not set",
                      suggestion: "Add GEMINI_API_KEY to MCP server configuration",
                    },
                    null,
                    2
                  ),
                },
              ],
              isError: true,
            };
          }

          const { GoogleGenerativeAI } = await import("@google/generative-ai");
          const genAI = new GoogleGenerativeAI(geminiApiKey);
          const model = genAI.getGenerativeModel({ model: "gemini-2.0-flash-exp" });

          const result = await model.generateContent(aiPrompt);
          const response = await result.response;
          generatedSQL = response.text().trim();

          // Clean up SQL - remove markdown code blocks if present
          generatedSQL = generatedSQL
            .replace(/```sql\n?/g, "")
            .replace(/```\n?/g, "")
            .trim();
        }
      } catch (error: any) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  error: "Failed to generate SQL",
                  details: error.message,
                },
                null,
                2
              ),
            },
          ],
          isError: true,
        };
      }

      // Validate generated SQL
      const validation = validateSQL(generatedSQL);
      if (!validation.safe) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  generated_sql: generatedSQL,
                  error: "Generated SQL failed safety validation",
                  issues: validation.issues,
                  executed: false,
                },
                null,
                2
              ),
            },
          ],
          isError: true,
        };
      }

      // Auto-add LIMIT if needed
      const safeSql = autoAddLimit(generatedSQL);

      // Run EXPLAIN first (always, even if not executing)
      // Use EXPLAIN without ANALYZE - doesn't execute, just plans
      let explainPlan;
      try {
        const explainResult = await pool.query(
          `EXPLAIN (FORMAT JSON, COSTS true) ${safeSql}`
        );
        explainPlan = explainResult.rows[0]["QUERY PLAN"];
      } catch (error: any) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  generated_sql: safeSql,
                  error: "Generated SQL is invalid (EXPLAIN failed)",
                  details: error.message,
                  executed: false,
                },
                null,
                2
              ),
            },
          ],
          isError: true,
        };
      }

      // If execute=false, return SQL + EXPLAIN only
      if (!execute) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  generated_sql: safeSql,
                  validation: {
                    safe: true,
                    warnings: validation.warnings,
                  },
                  explain_plan: explainPlan,
                  executed: false,
                  message: "SQL generated and validated. Set execute=true to run it.",
                },
                null,
                2
              ),
            },
          ],
        };
      }

      // Execute the query in read-only transaction
      try {
        const client = await pool.connect();
        let queryResult;
        try {
          await client.query('BEGIN READ ONLY');
          queryResult = await client.query(safeSql);
          await client.query('ROLLBACK'); // Always rollback read-only txn
        } finally {
          client.release();
        }

        sessionStats.queriesExecuted++;
        sessionStats.rowsReturned += queryResult.rowCount || 0;

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  generated_sql: safeSql,
                  validation: {
                    safe: true,
                    warnings: validation.warnings,
                  },
                  explain_plan: explainPlan,
                  rows: queryResult.rows,
                  rowCount: queryResult.rowCount,
                  executed: true,
                },
                null,
                2
              ),
            },
          ],
        };
      } catch (error: any) {
        sessionStats.errorsEncountered++;
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  generated_sql: safeSql,
                  error: "Query execution failed",
                  details: error.message,
                  executed: false,
                },
                null,
                2
              ),
            },
          ],
          isError: true,
        };
      }
    }

    return {
      content: [{ type: "text", text: `Unknown tool: ${name}` }],
      isError: true,
    };
  } catch (error: any) {
    sessionStats.errorsEncountered++;
    return {
      content: [
        {
          type: "text",
          text: `Database error: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});

// Cleanup on exit
process.on("SIGINT", async () => {
  await pool.end();
  process.exit(0);
});

process.on("SIGTERM", async () => {
  await pool.end();
  process.exit(0);
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Postgres Bridge MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});

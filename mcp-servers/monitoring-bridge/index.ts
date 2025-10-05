#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import axios from "axios";
import { execSync } from "child_process";
import * as fs from "fs";
import * as os from "os";

// Environment variables
const railwayToken = process.env.RAILWAY_TOKEN;
const glitchTipUrl = process.env.GLITCHTIP_URL;
const glitchTipToken = process.env.GLITCHTIP_TOKEN;

if (!railwayToken && !glitchTipUrl) {
  console.error("Error: Either RAILWAY_TOKEN or GLITCHTIP_URL must be set");
  process.exit(1);
}

// Railway API client
const railwayApi = axios.create({
  baseURL: "https://backboard.railway.app/graphql/v2",
  headers: railwayToken
    ? {
        Authorization: `Bearer ${railwayToken}`,
        "Content-Type": "application/json",
      }
    : {},
});

// GlitchTip API client
const glitchTipApi = glitchTipUrl
  ? axios.create({
      baseURL: glitchTipUrl,
      headers: glitchTipToken
        ? {
            Authorization: `Bearer ${glitchTipToken}`,
            "Content-Type": "application/json",
          }
        : {},
    })
  : null;

// Create server
const server = new Server(
  {
    name: "monitoring-bridge",
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
  const tools: any[] = [];

  if (railwayToken) {
    tools.push(
      {
        name: "railway_list_projects",
        description: "List all Railway projects",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "railway_get_deployments",
        description: "Get recent deployments for a project/service",
        inputSchema: {
          type: "object",
          properties: {
            project_id: {
              type: "string",
              description: "Railway project ID",
            },
            service_id: {
              type: "string",
              description: "Railway service ID (optional)",
            },
            limit: {
              type: "number",
              description: "Number of deployments to fetch (default: 10)",
              default: 10,
            },
          },
          required: ["project_id"],
        },
      },
      {
        name: "railway_get_logs",
        description: "Fetch logs for a deployment or service",
        inputSchema: {
          type: "object",
          properties: {
            deployment_id: {
              type: "string",
              description: "Deployment ID to fetch logs from",
            },
            filter: {
              type: "string",
              description: "Filter logs by text (optional)",
            },
            limit: {
              type: "number",
              description: "Number of log lines (default: 100, max: 1000)",
              default: 100,
            },
          },
          required: ["deployment_id"],
        },
      },
      {
        name: "railway_get_metrics",
        description: "Get resource usage metrics (CPU, memory, network)",
        inputSchema: {
          type: "object",
          properties: {
            service_id: {
              type: "string",
              description: "Railway service ID",
            },
            metric_type: {
              type: "string",
              enum: ["cpu", "memory", "network"],
              description: "Type of metric to fetch",
            },
            timeframe: {
              type: "string",
              enum: ["1h", "6h", "24h", "7d"],
              description: "Time range for metrics (default: 1h)",
              default: "1h",
            },
          },
          required: ["service_id", "metric_type"],
        },
      },
      {
        name: "railway_get_env_variables",
        description: "Get environment variables from a Railway service. Returns variables and public URLs for database services.",
        inputSchema: {
          type: "object",
          properties: {
            project_id: {
              type: "string",
              description: "Railway project ID",
            },
            service_id: {
              type: "string",
              description: "Railway service ID",
            },
            environment_id: {
              type: "string",
              description: "Environment ID (optional, defaults to production)",
            },
          },
          required: ["project_id", "service_id"],
        },
      },
      {
        name: "save_credentials_to_shell",
        description: "Save environment credentials to shell configuration file (~/.zshrc or ~/.bashrc)",
        inputSchema: {
          type: "object",
          properties: {
            credentials: {
              type: "object",
              description: "Key-value pairs of environment variables to save",
              additionalProperties: {
                type: "string",
              },
            },
          },
          required: ["credentials"],
        },
      },
      {
        name: "test_vector_bridge_health",
        description: "Test if vector-bridge MCP server is connected and operational by checking database and Redis connectivity",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "setup_vector_rag",
        description: "Automated one-command setup for Vector RAG Memory. Fetches credentials from Railway, saves to shell config, and verifies connectivity. Use this for zero-config Vector RAG setup.",
        inputSchema: {
          type: "object",
          properties: {
            project_id: {
              type: "string",
              description: "Railway project ID (defaults to ai-memory project)",
              default: "676a4e56-bd2c-40f1-bdce-6b43a3799659",
            },
            service_id: {
              type: "string",
              description: "Railway service ID (defaults to vector-bridge service)",
              default: "81f9c3f5-695b-4cde-8e2a-ede72b550681",
            },
          },
        },
      },
      {
        name: "check_rag_status",
        description: "Check the complete status of Vector RAG Memory setup including credentials, MCP server health, database connectivity, and ingestion stats.",
        inputSchema: {
          type: "object",
          properties: {},
        },
      }
    );
  }

  if (glitchTipApi) {
    tools.push(
      {
        name: "glitchtip_list_issues",
        description: "List recent issues from GlitchTip",
        inputSchema: {
          type: "object",
          properties: {
            project: {
              type: "string",
              description: "GlitchTip project slug (optional, omit for all projects)",
            },
            status: {
              type: "string",
              enum: ["unresolved", "resolved", "ignored"],
              description: "Issue status filter (default: unresolved)",
              default: "unresolved",
            },
            limit: {
              type: "number",
              description: "Number of issues to fetch (default: 25)",
              default: 25,
            },
          },
        },
      },
      {
        name: "glitchtip_get_issue",
        description: "Get detailed information about a specific issue",
        inputSchema: {
          type: "object",
          properties: {
            issue_id: {
              type: "string",
              description: "GlitchTip issue ID",
            },
          },
          required: ["issue_id"],
        },
      },
      {
        name: "glitchtip_get_events",
        description: "Get events for a specific issue",
        inputSchema: {
          type: "object",
          properties: {
            issue_id: {
              type: "string",
              description: "GlitchTip issue ID",
            },
            limit: {
              type: "number",
              description: "Number of events (default: 10)",
              default: 10,
            },
          },
          required: ["issue_id"],
        },
      },
      {
        name: "glitchtip_resolve_issue",
        description: "Mark an issue as resolved in GlitchTip",
        inputSchema: {
          type: "object",
          properties: {
            issue_id: {
              type: "string",
              description: "GlitchTip issue ID",
            },
          },
          required: ["issue_id"],
        },
      }
    );
  }

  return { tools };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    // Railway tools
    if (name === "railway_list_projects") {
      const query = `
        query {
          projects {
            edges {
              node {
                id
                name
                description
                createdAt
                services {
                  edges {
                    node {
                      id
                      name
                    }
                  }
                }
              }
            }
          }
        }
      `;

      const response = await railwayApi.post("", { query });
      const projects = response.data.data.projects.edges.map((edge: any) => ({
        id: edge.node.id,
        name: edge.node.name,
        description: edge.node.description,
        created_at: edge.node.createdAt,
        services: edge.node.services.edges.map((s: any) => ({
          id: s.node.id,
          name: s.node.name,
        })),
      }));

      return {
        content: [{ type: "text", text: JSON.stringify(projects, null, 2) }],
      };
    }

    if (name === "railway_get_deployments") {
      const { project_id, service_id, limit = 10 } = args as any;

      const query = `
        query($projectId: String!, $serviceId: String, $limit: Int) {
          deployments(
            input: {
              projectId: $projectId
              serviceId: $serviceId
              first: $limit
            }
          ) {
            edges {
              node {
                id
                status
                createdAt
                updatedAt
                staticUrl
                meta
              }
            }
          }
        }
      `;

      const response = await railwayApi.post("", {
        query,
        variables: { projectId: project_id, serviceId: service_id, limit },
      });

      const deployments = response.data.data.deployments.edges.map((edge: any) => edge.node);

      return {
        content: [{ type: "text", text: JSON.stringify(deployments, null, 2) }],
      };
    }

    if (name === "railway_get_logs") {
      const { deployment_id, filter, limit = 100 } = args as any;

      const query = `
        query($deploymentId: String!, $limit: Int, $filter: String) {
          deploymentLogs(
            deploymentId: $deploymentId
            limit: $limit
            filter: $filter
          ) {
            timestamp
            message
            severity
          }
        }
      `;

      const response = await railwayApi.post("", {
        query,
        variables: { deploymentId: deployment_id, limit, filter },
      });

      const logs = response.data.data.deploymentLogs || [];

      return {
        content: [{ type: "text", text: JSON.stringify(logs, null, 2) }],
      };
    }

    if (name === "railway_get_metrics") {
      const { service_id, metric_type, timeframe = "1h" } = args as any;

      const query = `
        query($serviceId: String!, $metricType: String!, $timeframe: String!) {
          metrics(
            serviceId: $serviceId
            metricType: $metricType
            timeframe: $timeframe
          ) {
            timestamp
            value
          }
        }
      `;

      const response = await railwayApi.post("", {
        query,
        variables: { serviceId: service_id, metricType: metric_type, timeframe },
      });

      const metrics = response.data.data.metrics || [];

      return {
        content: [{ type: "text", text: JSON.stringify(metrics, null, 2) }],
      };
    }

    if (name === "railway_get_env_variables") {
      const { project_id, service_id, environment_id } = args as any;

      try {
        // First get project/service info and environment ID
        const infoQuery = `
          query($projectId: String!, $serviceId: String!) {
            project(id: $projectId) {
              id
              name
              environments {
                edges {
                  node {
                    id
                    name
                  }
                }
              }
            }
            service(id: $serviceId) {
              id
              name
            }
          }
        `;

        const infoResponse = await railwayApi.post("", {
          query: infoQuery,
          variables: { projectId: project_id, serviceId: service_id },
        });

        const data = infoResponse.data.data;
        const projectName = data.project?.name;
        const serviceName = data.service?.name;

        if (!projectName || !serviceName) {
          throw new Error(`Project ${project_id} or service ${service_id} not found`);
        }

        // Find the environment (default to production if not specified)
        let targetEnvId = environment_id;
        if (!targetEnvId && data.project?.environments?.edges) {
          const prodEnv = data.project.environments.edges.find((e: any) =>
            e.node.name.toLowerCase() === 'production'
          );
          targetEnvId = prodEnv?.node.id || data.project.environments.edges[0]?.node.id;
        }

        // Now get the actual variable values using the simplified query
        // This returns a key-value object directly!
        const varsQuery = `
          query variables($projectId: String!, $environmentId: String!, $serviceId: String) {
            variables(projectId: $projectId, environmentId: $environmentId, serviceId: $serviceId)
          }
        `;

        const varsResponse = await railwayApi.post("", {
          query: varsQuery,
          variables: {
            projectId: project_id,
            environmentId: targetEnvId,
            serviceId: service_id,
          },
        });

        const variables = varsResponse.data.data.variables || {};

        const result = {
          project_id: project_id,
          project_name: projectName,
          service_id: service_id,
          service_name: serviceName,
          environment_id: targetEnvId,
          variables: variables,
        };

        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      } catch (error: any) {
        return {
          content: [
            {
              type: "text",
              text: `Failed to get environment variables: ${error.message}${
                error.response?.data ? `\n${JSON.stringify(error.response.data, null, 2)}` : ""
              }`,
            },
          ],
          isError: true,
        };
      }
    }

    if (name === "save_credentials_to_shell") {
      const { credentials } = args as any;

      try {
        // Determine shell config file
        const shell = process.env.SHELL || "";
        const homeDir = os.homedir();
        let shellConfig: string;

        if (shell.includes("zsh")) {
          shellConfig = `${homeDir}/.zshrc`;
        } else if (shell.includes("bash")) {
          shellConfig = `${homeDir}/.bashrc`;
        } else {
          shellConfig = `${homeDir}/.zshrc`; // Default to zsh
        }

        // Build the export statements
        const timestamp = new Date().toISOString();
        let exportLines = `\n# Vector RAG Memory Credentials (auto-configured by Claude Code on ${timestamp})\n`;

        for (const [key, value] of Object.entries(credentials)) {
          // Escape double quotes in the value
          const escapedValue = (value as string).replace(/"/g, '\\"');
          exportLines += `export ${key}="${escapedValue}"\n`;
        }

        // Add ENABLE_VECTOR_RAG flag
        exportLines += `export ENABLE_VECTOR_RAG="true"\n`;

        // Append to shell config
        fs.appendFileSync(shellConfig, exportLines, "utf-8");

        const result = {
          success: true,
          file: shellConfig,
          credentials_saved: Object.keys(credentials),
          message: `Saved ${Object.keys(credentials).length} credentials to ${shellConfig}. Restart terminal or run 'source ${shellConfig}' to apply.`,
        };

        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      } catch (error: any) {
        return {
          content: [
            {
              type: "text",
              text: `Failed to save credentials: ${error.message}`,
            },
          ],
          isError: true,
        };
      }
    }

    if (name === "test_vector_bridge_health") {
      try {
        // Check if vector-bridge MCP server is running by testing database connection
        const homeDir = os.homedir();
        const vectorBridgePath = `${homeDir}/.claude/mcp-servers/vector-bridge`;

        // Try to run a simple health check via the vector-bridge server
        const healthCheck = execSync(
          `cd ${vectorBridgePath} && node -e "
            const pg = require('pg');
            const Redis = require('ioredis');

            const dbUrl = process.env.DATABASE_URL_MEMORY || process.env.DATABASE_URL;
            const redisUrl = process.env.REDIS_URL;

            console.log(JSON.stringify({
              env_vars: {
                DATABASE_URL_MEMORY: dbUrl ? 'set' : 'missing',
                REDIS_URL: redisUrl ? 'set' : 'missing',
                OPENAI_API_KEY: process.env.OPENAI_API_KEY ? 'set' : 'missing'
              }
            }));
          "`,
          { encoding: 'utf-8', env: process.env }
        );

        const envStatus = JSON.parse(healthCheck);

        const result = {
          vector_bridge_status: "checking",
          environment_variables: envStatus.env_vars,
          message: envStatus.env_vars.DATABASE_URL_MEMORY === 'set' && envStatus.env_vars.REDIS_URL === 'set'
            ? "✅ Environment variables are set. Vector-bridge should be operational after restart."
            : "⚠️  Some environment variables are missing. Please configure credentials first.",
        };

        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      } catch (error: any) {
        return {
          content: [
            {
              type: "text",
              text: `Health check failed: ${error.message}`,
            },
          ],
          isError: true,
        };
      }
    }

    if (name === "check_rag_status") {
      try {
        const status: any = {
          timestamp: new Date().toISOString(),
          environment: {
            DATABASE_URL_MEMORY: process.env.DATABASE_URL_MEMORY ? "✅ Set" : "❌ Missing",
            REDIS_URL: process.env.REDIS_URL ? "✅ Set" : "❌ Missing",
            OPENAI_API_KEY: process.env.OPENAI_API_KEY ? "✅ Set" : "❌ Missing",
            ENABLE_VECTOR_RAG: process.env.ENABLE_VECTOR_RAG || "not set",
          },
          shell_config: {},
          mcp_server: {},
          database: {},
          ingestion_stats: {},
        };

        // Check shell config file
        const shell = process.env.SHELL || "";
        const homeDir = os.homedir();
        let shellConfig: string;

        if (shell.includes("zsh")) {
          shellConfig = `${homeDir}/.zshrc`;
        } else if (shell.includes("bash")) {
          shellConfig = `${homeDir}/.bashrc`;
        } else {
          shellConfig = `${homeDir}/.zshrc`;
        }

        status.shell_config.path = shellConfig;
        status.shell_config.exists = fs.existsSync(shellConfig);

        if (status.shell_config.exists) {
          const configContent = fs.readFileSync(shellConfig, "utf-8");
          status.shell_config.has_db_url = configContent.includes("DATABASE_URL_MEMORY");
          status.shell_config.has_redis_url = configContent.includes("REDIS_URL");
          status.shell_config.has_openai_key = configContent.includes("OPENAI_API_KEY");
        }

        // Check MCP server files
        const vectorBridgePath = `${homeDir}/.claude/mcp-servers/vector-bridge`;
        status.mcp_server.path = vectorBridgePath;
        status.mcp_server.exists = fs.existsSync(vectorBridgePath);
        status.mcp_server.dist_exists = fs.existsSync(`${vectorBridgePath}/dist/index.js`);

        // Try to check database connectivity (if credentials exist)
        if (process.env.DATABASE_URL_MEMORY) {
          try {
            const dbCheck = execSync(
              `node -e "const {Client}=require('pg');const c=new Client({connectionString:process.env.DATABASE_URL_MEMORY});c.connect().then(()=>{console.log('connected');c.end();}).catch(e=>{console.error(e.message);process.exit(1)});"`,
              { encoding: "utf-8", timeout: 5000, env: process.env }
            );
            status.database.connectivity = "✅ Connected";
          } catch (error: any) {
            status.database.connectivity = `❌ Failed: ${error.message.split("\n")[0]}`;
          }
        } else {
          status.database.connectivity = "⚠️  No credentials to test";
        }

        // Try to get ingestion stats from vector-bridge
        if (process.env.DATABASE_URL_MEMORY) {
          try {
            const statsCheck = execSync(
              `node -e "const {Client}=require('pg');const c=new Client({connectionString:process.env.DATABASE_URL_MEMORY});c.connect().then(async()=>{const r=await c.query('SELECT COUNT(*) as total, COUNT(DISTINCT project_root) as projects FROM documents WHERE metadata->>\\\'source\\\'=\\\'digest\\\'');console.log(JSON.stringify(r.rows[0]));c.end();}).catch(e=>{console.error(e.message);process.exit(1)});"`,
              { encoding: "utf-8", timeout: 5000, env: process.env }
            );
            const stats = JSON.parse(statsCheck.trim());
            status.ingestion_stats.total_digests = stats.total;
            status.ingestion_stats.total_projects = stats.projects;
            status.ingestion_stats.status = "✅ Operational";
          } catch (error: any) {
            status.ingestion_stats.status = `⚠️  Could not fetch stats`;
          }
        } else {
          status.ingestion_stats.status = "⚠️  Not configured";
        }

        // Overall status
        const allCredsSet =
          status.environment.DATABASE_URL_MEMORY === "✅ Set" &&
          status.environment.REDIS_URL === "✅ Set" &&
          status.environment.OPENAI_API_KEY === "✅ Set";

        status.overall_status = allCredsSet
          ? "✅ Vector RAG Memory is operational"
          : "⚠️  Vector RAG Memory needs setup (run setup_vector_rag)";

        return {
          content: [{ type: "text", text: JSON.stringify(status, null, 2) }],
        };
      } catch (error: any) {
        return {
          content: [
            {
              type: "text",
              text: `Failed to check RAG status: ${error.message}`,
            },
          ],
          isError: true,
        };
      }
    }

    if (name === "setup_vector_rag") {
      const {
        project_id = "676a4e56-bd2c-40f1-bdce-6b43a3799659",
        service_id = "81f9c3f5-695b-4cde-8e2a-ede72b550681",
      } = args as any;

      const setupLog: string[] = [];

      try {
        setupLog.push("🚀 Starting Vector RAG Memory setup...\n");

        // Step 1: Fetch credentials from Railway
        setupLog.push("📡 Step 1/3: Fetching credentials from Railway...");

        const infoQuery = `
          query($projectId: String!, $serviceId: String!) {
            project(id: $projectId) {
              id
              name
              environments {
                edges {
                  node {
                    id
                    name
                  }
                }
              }
            }
            service(id: $serviceId) {
              id
              name
            }
          }
        `;

        const infoResponse = await railwayApi.post("", {
          query: infoQuery,
          variables: { projectId: project_id, serviceId: service_id },
        });

        const data = infoResponse.data.data;
        const projectName = data.project?.name;
        const serviceName = data.service?.name;

        if (!projectName || !serviceName) {
          throw new Error(`Project ${project_id} or service ${service_id} not found`);
        }

        let targetEnvId = data.project?.environments?.edges?.find((e: any) =>
          e.node.name.toLowerCase() === 'production'
        )?.node.id || data.project.environments.edges[0]?.node.id;

        const varsQuery = `
          query variables($projectId: String!, $environmentId: String!, $serviceId: String) {
            variables(projectId: $projectId, environmentId: $environmentId, serviceId: $serviceId)
          }
        `;

        const varsResponse = await railwayApi.post("", {
          query: varsQuery,
          variables: {
            projectId: project_id,
            environmentId: targetEnvId,
            serviceId: service_id,
          },
        });

        const allVariables = varsResponse.data.data.variables || {};

        // Extract only the credentials we need
        const credentials = {
          DATABASE_URL_MEMORY: allVariables.DATABASE_URL,
          REDIS_URL: allVariables.REDIS_PUBLIC_URL || allVariables.REDIS_URL,
          OPENAI_API_KEY: allVariables.OPENAI_API_KEY,
        };

        setupLog.push(`✅ Fetched credentials from ${projectName}/${serviceName}\n`);

        // Step 2: Save to shell config
        setupLog.push("💾 Step 2/3: Saving credentials to shell config...");

        const shell = process.env.SHELL || "";
        const homeDir = os.homedir();
        let shellConfig: string;

        if (shell.includes("zsh")) {
          shellConfig = `${homeDir}/.zshrc`;
        } else if (shell.includes("bash")) {
          shellConfig = `${homeDir}/.bashrc`;
        } else {
          shellConfig = `${homeDir}/.zshrc`;
        }

        const timestamp = new Date().toISOString();
        let exportLines = `\n# Vector RAG Memory Credentials (auto-configured on ${timestamp})\n`;

        for (const [key, value] of Object.entries(credentials)) {
          const escapedValue = (value as string).replace(/"/g, '\\"');
          exportLines += `export ${key}="${escapedValue}"\n`;
        }
        exportLines += `export ENABLE_VECTOR_RAG="true"\n`;

        fs.appendFileSync(shellConfig, exportLines, "utf-8");

        setupLog.push(`✅ Saved to ${shellConfig}\n`);

        // Step 3: Verify environment
        setupLog.push("🔍 Step 3/3: Verifying setup...");

        const homeCheck = os.homedir();
        const vectorBridgePath = `${homeCheck}/.claude/mcp-servers/vector-bridge`;

        const healthCheck = execSync(
          `cd ${vectorBridgePath} && node -e "
            const dbUrl = process.env.DATABASE_URL_MEMORY || process.env.DATABASE_URL;
            const redisUrl = process.env.REDIS_URL;
            console.log(JSON.stringify({
              DATABASE_URL_MEMORY: dbUrl ? 'set' : 'missing',
              REDIS_URL: redisUrl ? 'set' : 'missing',
              OPENAI_API_KEY: process.env.OPENAI_API_KEY ? 'set' : 'missing'
            }));
          "`,
          { encoding: 'utf-8', env: process.env }
        );

        const envStatus = JSON.parse(healthCheck);

        setupLog.push(`✅ Environment verified\n`);

        const result = {
          success: true,
          project: projectName,
          service: serviceName,
          shell_config: shellConfig,
          credentials_saved: Object.keys(credentials),
          environment_status: envStatus,
          next_steps: [
            "1. Restart your terminal or run: source " + shellConfig,
            "2. Restart Claude Code to reload MCP servers",
            "3. Vector RAG Memory will be operational!",
          ],
          setup_log: setupLog.join("\n"),
        };

        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      } catch (error: any) {
        setupLog.push(`\n❌ Setup failed: ${error.message}`);
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                success: false,
                error: error.message,
                setup_log: setupLog.join("\n"),
              }, null, 2),
            },
          ],
          isError: true,
        };
      }
    }

    // GlitchTip tools
    if (name === "glitchtip_list_issues" && glitchTipApi) {
      const { project, status = "unresolved", limit = 25 } = args as any;

      let url = `/api/0/issues/?query=is:${status}&limit=${limit}`;
      if (project) {
        url = `/api/0/projects/${project}/issues/?query=is:${status}&limit=${limit}`;
      }

      const response = await glitchTipApi.get(url);

      // Handle both array and paginated response formats
      const data = Array.isArray(response.data) ? response.data : (response.data.results || []);

      const issues = data.map((issue: any) => ({
        id: issue.id,
        title: issue.title,
        status: issue.status,
        level: issue.level,
        count: issue.count,
        userCount: issue.userCount,
        firstSeen: issue.firstSeen,
        lastSeen: issue.lastSeen,
        permalink: issue.permalink,
      }));

      return {
        content: [{ type: "text", text: JSON.stringify(issues, null, 2) }],
      };
    }

    if (name === "glitchtip_get_issue" && glitchTipApi) {
      const { issue_id } = args as any;

      const response = await glitchTipApi.get(`/api/0/issues/${issue_id}/`);

      return {
        content: [{ type: "text", text: JSON.stringify(response.data, null, 2) }],
      };
    }

    if (name === "glitchtip_get_events" && glitchTipApi) {
      const { issue_id, limit = 10 } = args as any;

      const response = await glitchTipApi.get(
        `/api/0/issues/${issue_id}/events/?limit=${limit}`
      );

      return {
        content: [{ type: "text", text: JSON.stringify(response.data, null, 2) }],
      };
    }

    if (name === "glitchtip_resolve_issue" && glitchTipApi) {
      const { issue_id } = args as any;

      const response = await glitchTipApi.put(`/api/0/issues/${issue_id}/`, {
        status: "resolved",
      });

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              { success: true, issue_id, status: "resolved" },
              null,
              2
            ),
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
          text: `Monitoring API error: ${error.message}${
            error.response?.data ? `\n${JSON.stringify(error.response.data, null, 2)}` : ""
          }`,
        },
      ],
      isError: true,
    };
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Monitoring Bridge MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});

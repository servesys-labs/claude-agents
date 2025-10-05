#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { Octokit } from "@octokit/rest";

// Initialize GitHub client
const token = process.env.GITHUB_TOKEN;
if (!token) {
  console.error("Error: GITHUB_TOKEN environment variable is required");
  process.exit(1);
}

const octokit = new Octokit({ auth: token });

// Create server
const server = new Server(
  {
    name: "github-bridge",
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
        name: "list_repos",
        description: "List repositories for the authenticated user or a specific user/org",
        inputSchema: {
          type: "object",
          properties: {
            username: {
              type: "string",
              description: "GitHub username or org (omit for authenticated user's repos)",
            },
            type: {
              type: "string",
              enum: ["all", "owner", "member", "public", "private"],
              description: "Type of repos to list (default: all)",
              default: "all",
            },
            sort: {
              type: "string",
              enum: ["created", "updated", "pushed", "full_name"],
              description: "Sort by (default: updated)",
              default: "updated",
            },
            per_page: {
              type: "number",
              description: "Results per page (default: 30, max: 100)",
              default: 30,
            },
          },
        },
      },
      {
        name: "get_repo",
        description: "Get detailed information about a specific repository",
        inputSchema: {
          type: "object",
          properties: {
            owner: {
              type: "string",
              description: "Repository owner",
            },
            repo: {
              type: "string",
              description: "Repository name",
            },
          },
          required: ["owner", "repo"],
        },
      },
      {
        name: "list_issues",
        description: "List issues for a repository",
        inputSchema: {
          type: "object",
          properties: {
            owner: {
              type: "string",
              description: "Repository owner",
            },
            repo: {
              type: "string",
              description: "Repository name",
            },
            state: {
              type: "string",
              enum: ["open", "closed", "all"],
              description: "Issue state (default: open)",
              default: "open",
            },
            labels: {
              type: "string",
              description: "Comma-separated list of labels",
            },
            per_page: {
              type: "number",
              description: "Results per page (default: 30, max: 100)",
              default: 30,
            },
          },
          required: ["owner", "repo"],
        },
      },
      {
        name: "create_issue",
        description: "Create a new issue in a repository",
        inputSchema: {
          type: "object",
          properties: {
            owner: {
              type: "string",
              description: "Repository owner",
            },
            repo: {
              type: "string",
              description: "Repository name",
            },
            title: {
              type: "string",
              description: "Issue title",
            },
            body: {
              type: "string",
              description: "Issue body/description",
            },
            labels: {
              type: "array",
              items: { type: "string" },
              description: "Array of label names",
            },
            assignees: {
              type: "array",
              items: { type: "string" },
              description: "Array of GitHub usernames to assign",
            },
          },
          required: ["owner", "repo", "title"],
        },
      },
      {
        name: "list_prs",
        description: "List pull requests for a repository",
        inputSchema: {
          type: "object",
          properties: {
            owner: {
              type: "string",
              description: "Repository owner",
            },
            repo: {
              type: "string",
              description: "Repository name",
            },
            state: {
              type: "string",
              enum: ["open", "closed", "all"],
              description: "PR state (default: open)",
              default: "open",
            },
            per_page: {
              type: "number",
              description: "Results per page (default: 30, max: 100)",
              default: 30,
            },
          },
          required: ["owner", "repo"],
        },
      },
      {
        name: "get_pr",
        description: "Get detailed information about a specific pull request",
        inputSchema: {
          type: "object",
          properties: {
            owner: {
              type: "string",
              description: "Repository owner",
            },
            repo: {
              type: "string",
              description: "Repository name",
            },
            pull_number: {
              type: "number",
              description: "Pull request number",
            },
          },
          required: ["owner", "repo", "pull_number"],
        },
      },
      {
        name: "get_ci_status",
        description: "Get CI/check run status for a commit or PR",
        inputSchema: {
          type: "object",
          properties: {
            owner: {
              type: "string",
              description: "Repository owner",
            },
            repo: {
              type: "string",
              description: "Repository name",
            },
            ref: {
              type: "string",
              description: "Git ref (branch name, commit SHA, or PR number)",
            },
          },
          required: ["owner", "repo", "ref"],
        },
      },
      {
        name: "search_code",
        description: "Search code across GitHub repositories",
        inputSchema: {
          type: "object",
          properties: {
            q: {
              type: "string",
              description: "Search query (e.g., 'useAuth repo:owner/repo', 'class:MyClass language:typescript')",
            },
            per_page: {
              type: "number",
              description: "Results per page (default: 30, max: 100)",
              default: 30,
            },
          },
          required: ["q"],
        },
      },
      {
        name: "get_user",
        description: "Get information about a GitHub user",
        inputSchema: {
          type: "object",
          properties: {
            username: {
              type: "string",
              description: "GitHub username (omit for authenticated user)",
            },
          },
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    if (name === "list_repos") {
      const { username, type = "all", sort = "updated", per_page = 30 } = args as any;

      let response;
      if (username) {
        response = await octokit.repos.listForUser({
          username,
          type,
          sort,
          per_page,
        });
      } else {
        response = await octokit.repos.listForAuthenticatedUser({
          type,
          sort,
          per_page,
        });
      }

      const repos = response.data.map((repo: any) => ({
        name: repo.name,
        full_name: repo.full_name,
        description: repo.description,
        private: repo.private,
        html_url: repo.html_url,
        stars: repo.stargazers_count,
        forks: repo.forks_count,
        open_issues: repo.open_issues_count,
        language: repo.language,
        updated_at: repo.updated_at,
      }));

      return {
        content: [{ type: "text", text: JSON.stringify(repos, null, 2) }],
      };
    }

    if (name === "get_repo") {
      const { owner, repo } = args as any;
      const response = await octokit.repos.get({ owner, repo });

      return {
        content: [{ type: "text", text: JSON.stringify(response.data, null, 2) }],
      };
    }

    if (name === "list_issues") {
      const { owner, repo, state = "open", labels, per_page = 30 } = args as any;
      const response = await octokit.issues.listForRepo({
        owner,
        repo,
        state,
        labels,
        per_page,
      });

      const issues = response.data.map((issue: any) => ({
        number: issue.number,
        title: issue.title,
        state: issue.state,
        user: issue.user.login,
        labels: issue.labels.map((l: any) => l.name),
        created_at: issue.created_at,
        updated_at: issue.updated_at,
        html_url: issue.html_url,
        body: issue.body?.substring(0, 200) + (issue.body?.length > 200 ? "..." : ""),
      }));

      return {
        content: [{ type: "text", text: JSON.stringify(issues, null, 2) }],
      };
    }

    if (name === "create_issue") {
      const { owner, repo, title, body, labels, assignees } = args as any;
      const response = await octokit.issues.create({
        owner,
        repo,
        title,
        body,
        labels,
        assignees,
      });

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                number: response.data.number,
                title: response.data.title,
                html_url: response.data.html_url,
                state: response.data.state,
              },
              null,
              2
            ),
          },
        ],
      };
    }

    if (name === "list_prs") {
      const { owner, repo, state = "open", per_page = 30 } = args as any;
      const response = await octokit.pulls.list({
        owner,
        repo,
        state,
        per_page,
      });

      const prs = response.data.map((pr: any) => ({
        number: pr.number,
        title: pr.title,
        state: pr.state,
        user: pr.user.login,
        created_at: pr.created_at,
        updated_at: pr.updated_at,
        html_url: pr.html_url,
        head: pr.head.ref,
        base: pr.base.ref,
        mergeable: pr.mergeable,
        draft: pr.draft,
      }));

      return {
        content: [{ type: "text", text: JSON.stringify(prs, null, 2) }],
      };
    }

    if (name === "get_pr") {
      const { owner, repo, pull_number } = args as any;
      const response = await octokit.pulls.get({
        owner,
        repo,
        pull_number,
      });

      return {
        content: [{ type: "text", text: JSON.stringify(response.data, null, 2) }],
      };
    }

    if (name === "get_ci_status") {
      const { owner, repo, ref } = args as any;
      const response = await octokit.checks.listForRef({
        owner,
        repo,
        ref,
      });

      const checks = response.data.check_runs.map((check: any) => ({
        name: check.name,
        status: check.status,
        conclusion: check.conclusion,
        started_at: check.started_at,
        completed_at: check.completed_at,
        html_url: check.html_url,
      }));

      return {
        content: [{ type: "text", text: JSON.stringify(checks, null, 2) }],
      };
    }

    if (name === "search_code") {
      const { q, per_page = 30 } = args as any;
      const response = await octokit.search.code({
        q,
        per_page,
      });

      const results = response.data.items.map((item: any) => ({
        name: item.name,
        path: item.path,
        repository: item.repository.full_name,
        html_url: item.html_url,
      }));

      return {
        content: [{ type: "text", text: JSON.stringify(results, null, 2) }],
      };
    }

    if (name === "get_user") {
      const { username } = args as any;

      let response;
      if (username) {
        response = await octokit.users.getByUsername({ username });
      } else {
        response = await octokit.users.getAuthenticated();
      }

      return {
        content: [{ type: "text", text: JSON.stringify(response.data, null, 2) }],
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
          text: `Error calling GitHub API: ${error.message}${
            error.status ? ` (HTTP ${error.status})` : ""
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
  console.error("GitHub Bridge MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});

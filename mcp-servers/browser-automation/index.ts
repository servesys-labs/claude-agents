#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { chromium, Browser, Page } from "playwright";

// Browser session management
let browser: Browser | null = null;
let page: Page | null = null;

async function ensureBrowser() {
  if (!browser) {
    browser = await chromium.launch({ headless: true });
  }
  if (!page) {
    page = await browser.newPage();
  }
  return { browser, page };
}

// Create server
const server = new Server(
  {
    name: "browser-automation",
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
        name: "navigate",
        description: "Navigate to a URL",
        inputSchema: {
          type: "object",
          properties: {
            url: {
              type: "string",
              description: "URL to navigate to",
            },
          },
          required: ["url"],
        },
      },
      {
        name: "screenshot",
        description: "Take a screenshot of the current page",
        inputSchema: {
          type: "object",
          properties: {
            path: {
              type: "string",
              description: "Path to save screenshot (optional, returns base64 if omitted)",
            },
            full_page: {
              type: "boolean",
              description: "Capture full scrollable page (default: false)",
              default: false,
            },
          },
        },
      },
      {
        name: "click",
        description: "Click an element on the page",
        inputSchema: {
          type: "object",
          properties: {
            selector: {
              type: "string",
              description: "CSS selector for element to click",
            },
          },
          required: ["selector"],
        },
      },
      {
        name: "fill",
        description: "Fill an input field",
        inputSchema: {
          type: "object",
          properties: {
            selector: {
              type: "string",
              description: "CSS selector for input element",
            },
            value: {
              type: "string",
              description: "Value to fill",
            },
          },
          required: ["selector", "value"],
        },
      },
      {
        name: "get_text",
        description: "Get text content of an element",
        inputSchema: {
          type: "object",
          properties: {
            selector: {
              type: "string",
              description: "CSS selector for element",
            },
          },
          required: ["selector"],
        },
      },
      {
        name: "evaluate",
        description: "Execute JavaScript in the page context",
        inputSchema: {
          type: "object",
          properties: {
            script: {
              type: "string",
              description: "JavaScript code to execute",
            },
          },
          required: ["script"],
        },
      },
      {
        name: "wait_for_selector",
        description: "Wait for an element to appear",
        inputSchema: {
          type: "object",
          properties: {
            selector: {
              type: "string",
              description: "CSS selector to wait for",
            },
            timeout: {
              type: "number",
              description: "Timeout in milliseconds (default: 30000)",
              default: 30000,
            },
          },
          required: ["selector"],
        },
      },
      {
        name: "get_html",
        description: "Get HTML content of the page or element",
        inputSchema: {
          type: "object",
          properties: {
            selector: {
              type: "string",
              description: "CSS selector for element (optional, gets full page if omitted)",
            },
          },
        },
      },
      {
        name: "close_browser",
        description: "Close the browser and clean up resources",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    if (name === "navigate") {
      const { url } = args as { url: string };
      const { page } = await ensureBrowser();

      await page.goto(url, { waitUntil: "networkidle" });

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                url: page.url(),
                title: await page.title(),
              },
              null,
              2
            ),
          },
        ],
      };
    }

    if (name === "screenshot") {
      const { path, full_page = false } = args as {
        path?: string;
        full_page?: boolean;
      };
      const { page } = await ensureBrowser();

      const screenshot = await page.screenshot({
        path,
        fullPage: full_page,
        type: "png",
      });

      if (path) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({ success: true, path }, null, 2),
            },
          ],
        };
      } else {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  success: true,
                  base64: screenshot.toString("base64"),
                },
                null,
                2
              ),
            },
          ],
        };
      }
    }

    if (name === "click") {
      const { selector } = args as { selector: string };
      const { page } = await ensureBrowser();

      await page.click(selector);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ success: true, selector }, null, 2),
          },
        ],
      };
    }

    if (name === "fill") {
      const { selector, value } = args as { selector: string; value: string };
      const { page } = await ensureBrowser();

      await page.fill(selector, value);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ success: true, selector, value }, null, 2),
          },
        ],
      };
    }

    if (name === "get_text") {
      const { selector } = args as { selector: string };
      const { page } = await ensureBrowser();

      const text = await page.textContent(selector);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ success: true, selector, text }, null, 2),
          },
        ],
      };
    }

    if (name === "evaluate") {
      const { script } = args as { script: string };
      const { page } = await ensureBrowser();

      const result = await page.evaluate(script);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ success: true, result }, null, 2),
          },
        ],
      };
    }

    if (name === "wait_for_selector") {
      const { selector, timeout = 30000 } = args as {
        selector: string;
        timeout?: number;
      };
      const { page } = await ensureBrowser();

      await page.waitForSelector(selector, { timeout });

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              { success: true, selector, found: true },
              null,
              2
            ),
          },
        ],
      };
    }

    if (name === "get_html") {
      const { selector } = args as { selector?: string };
      const { page } = await ensureBrowser();

      let html: string;
      if (selector) {
        const element = await page.$(selector);
        html = element ? await element.innerHTML() : "";
      } else {
        html = await page.content();
      }

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ success: true, html }, null, 2),
          },
        ],
      };
    }

    if (name === "close_browser") {
      if (browser) {
        await browser.close();
        browser = null;
        page = null;
      }

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ success: true, closed: true }, null, 2),
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
          text: `Browser automation error: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});

// Cleanup on exit
process.on("SIGINT", async () => {
  if (browser) await browser.close();
  process.exit(0);
});

process.on("SIGTERM", async () => {
  if (browser) await browser.close();
  process.exit(0);
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Browser Automation MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});

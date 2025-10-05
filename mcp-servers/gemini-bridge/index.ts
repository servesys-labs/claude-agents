#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { GoogleGenerativeAI } from "@google/generative-ai";

// Session statistics
interface SessionStats {
  totalTokens: number;
  totalCost: number;
}

const sessionStats: SessionStats = {
  totalTokens: 0,
  totalCost: 0,
};

// Pricing (as of 2025) - per 1M tokens
const PRICING = {
  "gemini-2.0-flash-exp": {
    input: 0, // Free tier
    output: 0,
  },
  "gemini-1.5-flash": {
    input: 0.075,
    output: 0.30,
  },
  "gemini-1.5-pro": {
    input: 1.25,
    output: 5.00,
  },
  "gemini-exp-1206": {
    input: 0, // Experimental, free
    output: 0,
  },
};

type GeminiModel = keyof typeof PRICING;

function calculateCost(model: GeminiModel, inputTokens: number, outputTokens: number): number {
  const pricing = PRICING[model];
  const inputCost = (inputTokens / 1_000_000) * pricing.input;
  const outputCost = (outputTokens / 1_000_000) * pricing.output;
  return inputCost + outputCost;
}

// Initialize Gemini
const apiKey = process.env.GOOGLE_API_KEY;
if (!apiKey) {
  console.error("Error: GOOGLE_API_KEY environment variable is required");
  process.exit(1);
}

const genAI = new GoogleGenerativeAI(apiKey);

// Create server
const server = new Server(
  {
    name: "gemini-bridge",
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
        name: "ask_gemini",
        description: "Send a prompt to Google Gemini and receive a response. Supports multiple models including Gemini 2.0 Flash (experimental), Gemini 1.5 Flash, and Gemini 1.5 Pro.",
        inputSchema: {
          type: "object",
          properties: {
            prompt: {
              type: "string",
              description: "The prompt to send to Gemini",
            },
            model: {
              type: "string",
              enum: ["gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-exp-1206"],
              description: "Which Gemini model to use (default: gemini-2.0-flash-exp for best performance)",
              default: "gemini-2.0-flash-exp",
            },
            system_instruction: {
              type: "string",
              description: "System instruction to set context (optional)",
            },
            temperature: {
              type: "number",
              description: "Temperature for response creativity (0-2, default: 0.7)",
              minimum: 0,
              maximum: 2,
              default: 0.7,
            },
            max_tokens: {
              type: "number",
              description: "Maximum tokens in response (default: 2000)",
              default: 2000,
            },
          },
          required: ["prompt"],
        },
      },
      {
        name: "get_usage_stats",
        description: "Get current session usage statistics (tokens used, cost incurred)",
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

  if (name === "ask_gemini") {
    const {
      prompt,
      model = "gemini-2.0-flash-exp",
      system_instruction,
      temperature = 0.7,
      max_tokens = 2000,
    } = args as {
      prompt: string;
      model?: GeminiModel;
      system_instruction?: string;
      temperature?: number;
      max_tokens?: number;
    };

    try {
      const geminiModel = genAI.getGenerativeModel({
        model,
        systemInstruction: system_instruction,
        generationConfig: {
          temperature,
          maxOutputTokens: max_tokens,
        },
      });

      const result = await geminiModel.generateContent(prompt);
      const response = result.response;
      const text = response.text();

      // Extract token usage
      const usageMetadata = response.usageMetadata;
      const inputTokens = usageMetadata?.promptTokenCount || 0;
      const outputTokens = usageMetadata?.candidatesTokenCount || 0;
      const totalTokens = usageMetadata?.totalTokenCount || inputTokens + outputTokens;

      // Calculate cost
      const cost = calculateCost(model, inputTokens, outputTokens);
      sessionStats.totalTokens += totalTokens;
      sessionStats.totalCost += cost;

      const modelDescriptions: Record<GeminiModel, string> = {
        "gemini-2.0-flash-exp": "Gemini 2.0 Flash - Latest experimental model, fastest, free tier",
        "gemini-1.5-flash": "Gemini 1.5 Flash - Fast and cost-effective",
        "gemini-1.5-pro": "Gemini 1.5 Pro - Most capable, highest quality",
        "gemini-exp-1206": "Gemini Experimental 1206 - Latest experimental features",
      };

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                response: text,
                model,
                model_description: modelDescriptions[model],
                tokens: {
                  prompt: inputTokens,
                  completion: outputTokens,
                  total: totalTokens,
                },
                cost: {
                  this_request: cost,
                  this_request_formatted: `$${cost.toFixed(4)}`,
                  prompt_cost: (inputTokens / 1_000_000) * PRICING[model].input,
                  completion_cost: (outputTokens / 1_000_000) * PRICING[model].output,
                  session_total: sessionStats.totalCost,
                  session_total_formatted: `$${sessionStats.totalCost.toFixed(4)}`,
                },
                pricing_info: {
                  input_rate: `$${PRICING[model].input}/1M tokens`,
                  output_rate: `$${PRICING[model].output}/1M tokens`,
                },
              },
              null,
              2
            ),
          },
        ],
      };
    } catch (error: any) {
      return {
        content: [
          {
            type: "text",
            text: `Error calling Gemini API: ${error.message}`,
          },
        ],
        isError: true,
      };
    }
  }

  if (name === "get_usage_stats") {
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(
            {
              total_tokens: sessionStats.totalTokens,
              total_cost: sessionStats.totalCost,
              formatted_cost: `$${sessionStats.totalCost.toFixed(4)}`,
            },
            null,
            2
          ),
        },
      ],
    };
  }

  return {
    content: [
      {
        type: "text",
        text: `Unknown tool: ${name}`,
      },
    ],
    isError: true,
  };
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Gemini Bridge MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});

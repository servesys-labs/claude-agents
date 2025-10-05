#!/usr/bin/env node
/**
 * OpenAI Bridge MCP Server
 *
 * Provides GPT-5 access to Claude Code for multi-model brainstorming.
 *
 * Tools:
 * - ask_gpt5: Send prompt to GPT-5 and get response
 * - compare_models: Get both Claude and GPT-5 responses side-by-side
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import OpenAI from 'openai';

// Initialize OpenAI client
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

// Token tracking
let totalTokensUsed = 0;
let totalCost = 0;

// OpenAI pricing (as of 2025)
const OPENAI_PRICING = {
  'gpt-5': {
    prompt: 0.030 / 1000,       // $0.030 per 1K prompt tokens (estimated)
    completion: 0.060 / 1000,   // $0.060 per 1K completion tokens (estimated)
    description: 'GPT-5 - Most advanced reasoning and brainstorming'
  },
  'gpt-5-turbo': {
    prompt: 0.015 / 1000,       // $0.015 per 1K prompt tokens (estimated)
    completion: 0.030 / 1000,   // $0.030 per 1K completion tokens (estimated)
    description: 'GPT-5 Turbo - Faster GPT-5 variant'
  },
  'gpt-4o': {
    prompt: 0.0025 / 1000,      // $0.0025 per 1K prompt tokens
    completion: 0.010 / 1000,   // $0.010 per 1K completion tokens
    description: 'GPT-4o - Best balance of cost and quality (fallback if GPT-5 unavailable)'
  },
  'gpt-4-turbo': {
    prompt: 0.01 / 1000,        // $0.01 per 1K prompt tokens
    completion: 0.03 / 1000,    // $0.03 per 1K completion tokens
    description: 'GPT-4 Turbo - Highly capable reasoning'
  },
  'o1-preview': {
    prompt: 0.015 / 1000,       // $0.015 per 1K prompt tokens
    completion: 0.060 / 1000,   // $0.060 per 1K completion tokens
    description: 'o1-preview - Advanced reasoning with chain-of-thought'
  }
};

interface AskGPT5Args {
  prompt: string;
  model?: 'gpt-5' | 'gpt-5-turbo' | 'gpt-4o' | 'gpt-4-turbo' | 'o1-preview';
  max_tokens?: number;
  temperature?: number;
  system_prompt?: string;
}

async function askGPT5(args: AskGPT5Args) {
  const {
    prompt,
    model = 'gpt-5', // Default: GPT-5 (October 2025 - most advanced reasoning)
    max_tokens = 2000,
    temperature = 0.7,
    system_prompt = 'You are a helpful AI assistant specializing in software architecture and engineering.'
  } = args;

  try {
    const response = await openai.chat.completions.create({
      model,
      messages: [
        { role: 'system', content: system_prompt },
        { role: 'user', content: prompt }
      ],
      max_tokens,
      temperature
    });

    const completion = response.choices[0]?.message?.content || '';
    const usage = response.usage;

    // Track tokens and cost
    if (usage) {
      const pricing = OPENAI_PRICING[model] || OPENAI_PRICING['gpt-4o'];
      const promptCost = usage.prompt_tokens * pricing.prompt;
      const completionCost = usage.completion_tokens * pricing.completion;
      const requestCost = promptCost + completionCost;

      totalTokensUsed += usage.total_tokens;
      totalCost += requestCost;

      return {
        response: completion,
        model,
        model_description: pricing.description,
        tokens: {
          prompt: usage.prompt_tokens,
          completion: usage.completion_tokens,
          total: usage.total_tokens
        },
        cost: {
          this_request: requestCost,
          this_request_formatted: `$${requestCost.toFixed(4)}`,
          prompt_cost: promptCost,
          completion_cost: completionCost,
          session_total: totalCost,
          session_total_formatted: `$${totalCost.toFixed(4)}`
        },
        pricing_info: {
          prompt_rate: `$${(pricing.prompt * 1000).toFixed(4)}/1K tokens`,
          completion_rate: `$${(pricing.completion * 1000).toFixed(4)}/1K tokens`
        }
      };
    }

    return { response: completion, model };
  } catch (error: any) {
    throw new Error(`OpenAI API error: ${error.message}`);
  }
}

async function getUsageStats() {
  return {
    total_tokens: totalTokensUsed,
    total_cost: totalCost,
    formatted_cost: `$${totalCost.toFixed(4)}`
  };
}

// Create MCP server
const server = new Server(
  {
    name: 'openai-bridge',
    version: '1.0.0',
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
        name: 'ask_gpt5',
        description: 'Send a prompt to GPT-5 and receive a response. Used for multi-model brainstorming and getting alternative perspectives.',
        inputSchema: {
          type: 'object',
          properties: {
            prompt: {
              type: 'string',
              description: 'The prompt to send to GPT-5'
            },
            model: {
              type: 'string',
              enum: ['gpt-5-turbo', 'gpt-5', 'gpt-4o'],
              description: 'Which GPT model to use (default: gpt-4o for cost efficiency)',
              default: 'gpt-4o'
            },
            max_tokens: {
              type: 'number',
              description: 'Maximum tokens in response (default: 2000)',
              default: 2000
            },
            temperature: {
              type: 'number',
              description: 'Temperature for response creativity (0-2, default: 0.7)',
              default: 0.7,
              minimum: 0,
              maximum: 2
            },
            system_prompt: {
              type: 'string',
              description: 'System prompt to set context (optional)',
            }
          },
          required: ['prompt']
        }
      },
      {
        name: 'get_usage_stats',
        description: 'Get current session usage statistics (tokens used, cost incurred)',
        inputSchema: {
          type: 'object',
          properties: {}
        }
      }
    ]
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    if (name === 'ask_gpt5') {
      const result = await askGPT5(args as unknown as AskGPT5Args);
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2)
          }
        ]
      };
    }

    if (name === 'get_usage_stats') {
      const stats = await getUsageStats();
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(stats, null, 2)
          }
        ]
      };
    }

    throw new Error(`Unknown tool: ${name}`);
  } catch (error: any) {
    return {
      content: [
        {
          type: 'text',
          text: `Error: ${error.message}`
        }
      ],
      isError: true
    };
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('OpenAI Bridge MCP server running on stdio');
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});

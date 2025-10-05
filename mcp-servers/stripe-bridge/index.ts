#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import Stripe from "stripe";

// Initialize Stripe
const apiKey = process.env.STRIPE_SECRET_KEY;
if (!apiKey) {
  console.error("Error: STRIPE_SECRET_KEY environment variable is required");
  process.exit(1);
}

const stripe = new Stripe(apiKey, {
  apiVersion: "2023-10-16",
});

// Create server
const server = new Server(
  {
    name: "stripe-bridge",
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
        name: "get_customer",
        description: "Get customer details by ID or email",
        inputSchema: {
          type: "object",
          properties: {
            customer_id: {
              type: "string",
              description: "Stripe customer ID (cus_...)",
            },
            email: {
              type: "string",
              description: "Customer email (searches if customer_id not provided)",
            },
          },
        },
      },
      {
        name: "list_customers",
        description: "List customers with optional filters",
        inputSchema: {
          type: "object",
          properties: {
            email: {
              type: "string",
              description: "Filter by email",
            },
            limit: {
              type: "number",
              description: "Number of customers to return (default: 10, max: 100)",
              default: 10,
            },
          },
        },
      },
      {
        name: "list_subscriptions",
        description: "List subscriptions for a customer",
        inputSchema: {
          type: "object",
          properties: {
            customer_id: {
              type: "string",
              description: "Stripe customer ID",
            },
            status: {
              type: "string",
              enum: ["all", "active", "canceled", "incomplete", "past_due", "trialing"],
              description: "Filter by subscription status (default: all)",
              default: "all",
            },
          },
          required: ["customer_id"],
        },
      },
      {
        name: "list_charges",
        description: "List recent charges",
        inputSchema: {
          type: "object",
          properties: {
            customer_id: {
              type: "string",
              description: "Filter by customer ID (optional)",
            },
            limit: {
              type: "number",
              description: "Number of charges to return (default: 10, max: 100)",
              default: 10,
            },
          },
        },
      },
      {
        name: "list_invoices",
        description: "List invoices",
        inputSchema: {
          type: "object",
          properties: {
            customer_id: {
              type: "string",
              description: "Filter by customer ID (optional)",
            },
            status: {
              type: "string",
              enum: ["draft", "open", "paid", "uncollectible", "void"],
              description: "Filter by invoice status (optional)",
            },
            limit: {
              type: "number",
              description: "Number of invoices to return (default: 10, max: 100)",
              default: 10,
            },
          },
        },
      },
      {
        name: "get_payment_intent",
        description: "Get payment intent details",
        inputSchema: {
          type: "object",
          properties: {
            payment_intent_id: {
              type: "string",
              description: "Payment intent ID (pi_...)",
            },
          },
          required: ["payment_intent_id"],
        },
      },
      {
        name: "list_payment_methods",
        description: "List payment methods for a customer",
        inputSchema: {
          type: "object",
          properties: {
            customer_id: {
              type: "string",
              description: "Stripe customer ID",
            },
            type: {
              type: "string",
              enum: ["card", "us_bank_account", "sepa_debit"],
              description: "Filter by payment method type (optional)",
            },
          },
          required: ["customer_id"],
        },
      },
      {
        name: "create_test_payment",
        description: "Create a test payment intent (test mode only)",
        inputSchema: {
          type: "object",
          properties: {
            amount: {
              type: "number",
              description: "Amount in cents (e.g., 1000 = $10.00)",
            },
            currency: {
              type: "string",
              description: "Currency code (default: usd)",
              default: "usd",
            },
            customer_id: {
              type: "string",
              description: "Customer ID (optional)",
            },
          },
          required: ["amount"],
        },
      },
      {
        name: "get_balance",
        description: "Get Stripe account balance",
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
    if (name === "get_customer") {
      const { customer_id, email } = args as { customer_id?: string; email?: string };

      if (customer_id) {
        const customer = await stripe.customers.retrieve(customer_id);
        return {
          content: [{ type: "text", text: JSON.stringify(customer, null, 2) }],
        };
      } else if (email) {
        const customers = await stripe.customers.list({ email, limit: 1 });
        return {
          content: [{ type: "text", text: JSON.stringify(customers.data[0] || null, null, 2) }],
        };
      } else {
        return {
          content: [{ type: "text", text: "Error: Either customer_id or email is required" }],
          isError: true,
        };
      }
    }

    if (name === "list_customers") {
      const { email, limit = 10 } = args as { email?: string; limit?: number };

      const params: any = { limit };
      if (email) params.email = email;

      const customers = await stripe.customers.list(params);

      return {
        content: [{ type: "text", text: JSON.stringify(customers.data, null, 2) }],
      };
    }

    if (name === "list_subscriptions") {
      const { customer_id, status = "all" } = args as { customer_id: string; status?: string };

      const params: any = { customer: customer_id };
      if (status !== "all") params.status = status;

      const subscriptions = await stripe.subscriptions.list(params);

      return {
        content: [{ type: "text", text: JSON.stringify(subscriptions.data, null, 2) }],
      };
    }

    if (name === "list_charges") {
      const { customer_id, limit = 10 } = args as { customer_id?: string; limit?: number };

      const params: any = { limit };
      if (customer_id) params.customer = customer_id;

      const charges = await stripe.charges.list(params);

      return {
        content: [{ type: "text", text: JSON.stringify(charges.data, null, 2) }],
      };
    }

    if (name === "list_invoices") {
      const { customer_id, status, limit = 10 } = args as {
        customer_id?: string;
        status?: string;
        limit?: number;
      };

      const params: any = { limit };
      if (customer_id) params.customer = customer_id;
      if (status) params.status = status;

      const invoices = await stripe.invoices.list(params);

      return {
        content: [{ type: "text", text: JSON.stringify(invoices.data, null, 2) }],
      };
    }

    if (name === "get_payment_intent") {
      const { payment_intent_id } = args as { payment_intent_id: string };

      const paymentIntent = await stripe.paymentIntents.retrieve(payment_intent_id);

      return {
        content: [{ type: "text", text: JSON.stringify(paymentIntent, null, 2) }],
      };
    }

    if (name === "list_payment_methods") {
      const { customer_id, type } = args as { customer_id: string; type?: string };

      const params: any = { customer: customer_id };
      if (type) params.type = type;

      const paymentMethods = await stripe.paymentMethods.list(params);

      return {
        content: [{ type: "text", text: JSON.stringify(paymentMethods.data, null, 2) }],
      };
    }

    if (name === "create_test_payment") {
      const { amount, currency = "usd", customer_id } = args as {
        amount: number;
        currency?: string;
        customer_id?: string;
      };

      const params: any = {
        amount,
        currency,
        automatic_payment_methods: { enabled: true },
      };
      if (customer_id) params.customer = customer_id;

      const paymentIntent = await stripe.paymentIntents.create(params);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                id: paymentIntent.id,
                amount: paymentIntent.amount,
                currency: paymentIntent.currency,
                status: paymentIntent.status,
                client_secret: paymentIntent.client_secret,
              },
              null,
              2
            ),
          },
        ],
      };
    }

    if (name === "get_balance") {
      const balance = await stripe.balance.retrieve();

      return {
        content: [{ type: "text", text: JSON.stringify(balance, null, 2) }],
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
          text: `Stripe API error: ${error.message}`,
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
  console.error("Stripe Bridge MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});

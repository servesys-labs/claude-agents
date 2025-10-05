# Vector Bridge MCP Server - Node.js Service
FROM node:20-alpine AS builder

WORKDIR /app

# Install ALL dependencies (including dev deps for build)
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Build TypeScript
RUN npm run build

# Production stage - smaller image without dev deps
FROM node:20-alpine

WORKDIR /app

# Copy package files and install only production deps
COPY package*.json ./
RUN npm ci --only=production

# Copy built artifacts from builder
COPY --from=builder /app/dist ./dist

# Run the MCP server
CMD ["node", "dist/index.js"]

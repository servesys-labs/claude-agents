/**
 * Auto-setup credentials by fetching from Railway MCP
 */
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';
import { execSync } from 'child_process';

const SHELL_CONFIGS = [
  join(homedir(), '.zshrc'),
  join(homedir(), '.bashrc'),
  join(homedir(), '.bash_profile'),
];

function getShellConfig(): string {
  for (const config of SHELL_CONFIGS) {
    if (existsSync(config)) {
      return config;
    }
  }
  return SHELL_CONFIGS[0];
}

function saveEnvVar(varName: string, value: string): void {
  const configPath = getShellConfig();
  let content = existsSync(configPath) ? readFileSync(configPath, 'utf-8') : '';
  
  const regex = new RegExp(`^export ${varName}=.*$`, 'm');
  if (regex.test(content)) {
    content = content.replace(regex, `export ${varName}="${value}"`);
  } else {
    content += `\n# Claude Orchestration Framework - Auto-configured\nexport ${varName}="${value}"\n`;
  }
  
  writeFileSync(configPath, content);
}

export const autoSetupSchema = {
  name: 'auto_setup_credentials',
  description: 'Automatically fetch and configure Vector RAG credentials from Railway. Requires railway-mcp to be configured.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      project_name: {
        type: 'string',
        description: 'Railway project name containing vector-bridge service (e.g., "ai-memory")',
        default: 'ai-memory',
      },
    },
  },
};

export async function autoSetupTool(args: any) {
  const projectName = args.project_name || 'ai-memory';
  
  try {
    // Check if credentials already exist
    const hasDb = !!process.env.DATABASE_URL_MEMORY;
    const hasRedis = !!process.env.REDIS_URL;
    const hasOpenAI = !!process.env.OPENAI_API_KEY;
    
    if (hasDb && hasRedis && hasOpenAI) {
      return {
        success: true,
        message: '✅ All credentials already configured!\n\nNo setup needed.',
        credentials: {
          DATABASE_URL_MEMORY: 'SET',
          REDIS_URL: 'SET',
          OPENAI_API_KEY: 'SET',
        },
      };
    }
    
    // Call Railway MCP to get project details
    // NOTE: This requires claude to invoke railway MCP on our behalf
    // We'll return instructions for Claude to do this
    
    return {
      success: false,
      needs_railway_call: true,
      message: `⚠️ Missing credentials detected!\n\nTo auto-configure, I need to call Railway MCP:\n\n1. Call mcp__monitoring-bridge__railway_list_projects to find "${projectName}" project\n2. Get the project_id\n3. Call mcp__monitoring-bridge__railway_get_deployments with that project_id\n4. Find the "vector-bridge" service\n5. Extract environment variables from the service\n6. Call this tool again with the extracted values\n\nOr you can manually provide:\n- DATABASE_URL_MEMORY\n- REDIS_URL  \n- OPENAI_API_KEY\n\nShould I proceed with auto-discovery via Railway MCP?`,
      missing: {
        DATABASE_URL_MEMORY: !hasDb,
        REDIS_URL: !hasRedis,
        OPENAI_API_KEY: !hasOpenAI,
      },
    };
    
  } catch (error: any) {
    return {
      success: false,
      error: error.message,
    };
  }
}

export async function saveCredentialsFromRailway(credentials: {
  DATABASE_URL_MEMORY?: string;
  REDIS_URL?: string;
  OPENAI_API_KEY?: string;
}) {
  const shellConfig = getShellConfig();
  const saved: string[] = [];
  
  try {
    if (credentials.DATABASE_URL_MEMORY) {
      saveEnvVar('DATABASE_URL_MEMORY', credentials.DATABASE_URL_MEMORY);
      saved.push('DATABASE_URL_MEMORY');
    }
    
    if (credentials.REDIS_URL) {
      saveEnvVar('REDIS_URL', credentials.REDIS_URL);
      saved.push('REDIS_URL');
    }
    
    if (credentials.OPENAI_API_KEY) {
      saveEnvVar('OPENAI_API_KEY', credentials.OPENAI_API_KEY);
      saved.push('OPENAI_API_KEY');
    }
    
    // Enable Vector RAG
    saveEnvVar('ENABLE_VECTOR_RAG', 'true');
    saved.push('ENABLE_VECTOR_RAG');
    
    return {
      success: true,
      message: `✅ Saved credentials to ${shellConfig}\n\nSaved: ${saved.join(', ')}\n\n⚠️ Action required:\n1. Run: source ${shellConfig}\n2. Restart Claude Code\n\nVector RAG Memory will then be active!`,
      saved,
      config_file: shellConfig,
    };
    
  } catch (error: any) {
    return {
      success: false,
      error: error.message,
    };
  }
}

// Additional tool for saving credentials
export const saveCredentialsSchema = {
  name: 'save_credentials',
  description: 'Save Vector RAG credentials to shell configuration file',
  inputSchema: {
    type: 'object' as const,
    properties: {
      DATABASE_URL_MEMORY: {
        type: 'string',
        description: 'PostgreSQL connection string',
      },
      REDIS_URL: {
        type: 'string', 
        description: 'Redis connection string',
      },
      OPENAI_API_KEY: {
        type: 'string',
        description: 'OpenAI API key for embeddings',
      },
    },
    required: ['DATABASE_URL_MEMORY', 'REDIS_URL', 'OPENAI_API_KEY'],
  },
};

export async function saveCredentialsTool(args: any) {
  return saveCredentialsFromRailway(args);
}

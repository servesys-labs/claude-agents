#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';
import { z } from 'zod';
import { promises as fs } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Import services
import { extractZipSafely, extractZipFromFile } from './services/zip-extractor.js';
import { fillSlot, listAllSlots } from './services/slot-filler.js';
import { updateTheme, extractThemeTokens } from './services/theme-updater.js';
import {
  validateBlueprint,
  validateTemplateMeta,
  loadAndValidateBlueprint
} from './services/schema-validator.js';
import { generateScreenshot, closeBrowser } from './services/screenshot.js';
import { insertComponent } from './services/component-inserter.js';
import {
  getTemplate,
  listAllTemplates,
  getCacheStats,
  refreshCache
} from './services/template-cache.js';
import { listComponents, extractComponent } from './services/component-extractor.js';
import { composePage } from './services/page-composer.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Environment configuration
const API_BASE_URL = process.env.UI_TEMPLATE_API_URL ||
  'https://ui-template-api-production-production.up.railway.app';
const TEMPLATES_DIR = process.env.TEMPLATES_DIR ||
  path.join(process.env.HOME || '~', 'vibe', 'ui-templates');

// Local paths
const SCREENSHOTS_PATH = path.join(__dirname, '../screenshots');

// Ensure directories exist
await fs.mkdir(SCREENSHOTS_PATH, { recursive: true });
await fs.mkdir(TEMPLATES_DIR, { recursive: true });

// Zod schemas for tool inputs
const ListTemplatesSchema = z.object({
  filter: z.object({
    capability: z.string().optional(),
    author: z.string().optional(),
    stack: z.string().optional(),
  }).optional(),
});

const GetTemplateSchema = z.object({
  templateId: z.string(),
});

const InitSiteSchema = z.object({
  templateId: z.string(),
  destination: z.string(),
  siteId: z.string(),
  siteName: z.string().optional(),
  overwrite: z.boolean().optional(),
  dryRun: z.boolean().optional(),
});

const ApplyBlueprintSchema = z.object({
  blueprintPath: z.string(),
  destination: z.string(),
  overwrite: z.boolean().optional(),
  dryRun: z.boolean().optional(),
});

const FillSlotSchema = z.object({
  sitePath: z.string(),
  pageId: z.string(),
  slotId: z.string(),
  content: z.string(),
  dryRun: z.boolean().optional(),
});

const UpdateThemeSchema = z.object({
  sitePath: z.string(),
  tokens: z.object({
    colors: z.record(z.string()).optional(),
    typography: z.object({
      fontFamily: z.record(z.string()).optional(),
    }).optional(),
    spacing: z.record(z.string()).optional(),
    borderRadius: z.record(z.string()).optional(),
  }),
  mode: z.enum(['light', 'dark', 'both']).optional(),
  dryRun: z.boolean().optional(),
});

const AddComponentSchema = z.object({
  sitePath: z.string(),
  componentId: z.string(),
  location: z.object({
    pageId: z.string(),
    after: z.string().optional(),
    before: z.string().optional(),
  }),
  props: z.record(z.any()).optional(),
  dryRun: z.boolean().optional(),
});

const GenerateScreenshotSchema = z.object({
  templateId: z.string().optional(),
  sitePath: z.string().optional(),
  url: z.string().optional(),
  outputPath: z.string().optional(),
  viewport: z.object({
    width: z.number(),
    height: z.number(),
  }).optional(),
  fullPage: z.boolean().optional(),
});

const ValidateSiteSchema = z.object({
  sitePath: z.string(),
});

const DiffSummarySchema = z.object({
  sitePath: z.string(),
  staged: z.boolean().optional(),
});

const ListSlotsSchema = z.object({
  sitePath: z.string(),
});

const RefreshCacheSchema = z.object({
  templateId: z.string().optional(),
});

// Phase 1A: New component extraction schemas
const ListComponentsSchema = z.object({
  templateId: z.string(),
});

const ExtractComponentSchema = z.object({
  templateId: z.string(),
  componentPath: z.string(),
  destination: z.string(),
  withDependencies: z.boolean().optional(),
  maxDepth: z.number().optional(),
  overwrite: z.boolean().optional(),
  dryRun: z.boolean().optional(),
});

const ComposePageSchema = z.object({
  sitePath: z.string(),
  pagePath: z.string(),
  sections: z.array(z.object({
    importPath: z.string(),
    componentName: z.string().optional(),
    props: z.record(z.any()).optional(),
  })),
  overwrite: z.boolean().optional(),
  dryRun: z.boolean().optional(),
});

// MCP Server
const server = new Server(
  {
    name: 'ui-template-bridge',
    version: '2.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Helper: Format result for MCP response
function formatResult(result: any) {
  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify(result, null, 2),
      },
    ],
  };
}

// Helper: Format error for MCP response
function formatError(error: string, details?: any) {
  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify(
          {
            ok: false,
            error,
            ...(details && { details }),
          },
          null,
          2
        ),
      },
    ],
    isError: true,
  };
}

// Tool: list_templates
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'list_templates',
      description: 'List all available UI templates (local cache + Railway API)',
      inputSchema: {
        type: 'object',
        properties: {
          filter: {
            type: 'object',
            properties: {
              capability: { type: 'string', description: 'Filter by capability' },
              author: { type: 'string', description: 'Filter by author' },
              stack: { type: 'string', description: 'Filter by stack (next, react-native)' },
            },
          },
        },
      },
    },
    {
      name: 'get_template',
      description: 'Get detailed metadata for a specific template',
      inputSchema: {
        type: 'object',
        properties: {
          templateId: { type: 'string', description: 'Template ID' },
        },
        required: ['templateId'],
      },
    },
    {
      name: 'init_site',
      description: 'Initialize a new site from a template (stamp out template to destination)',
      inputSchema: {
        type: 'object',
        properties: {
          templateId: { type: 'string', description: 'Template ID to use' },
          destination: { type: 'string', description: 'Destination directory path' },
          siteId: { type: 'string', description: 'Unique site identifier (kebab-case)' },
          siteName: { type: 'string', description: 'Display name for the site' },
          overwrite: { type: 'boolean', description: 'Overwrite if destination exists', default: false },
          dryRun: { type: 'boolean', description: 'Preview without writing', default: false },
        },
        required: ['templateId', 'destination', 'siteId'],
      },
    },
    {
      name: 'apply_blueprint',
      description: 'Apply a site.json blueprint to fill slots and configure a site',
      inputSchema: {
        type: 'object',
        properties: {
          blueprintPath: { type: 'string', description: 'Path to site.json blueprint file' },
          destination: { type: 'string', description: 'Site directory to apply blueprint to' },
          overwrite: { type: 'boolean', description: 'Overwrite existing content', default: false },
          dryRun: { type: 'boolean', description: 'Preview without writing', default: false },
        },
        required: ['blueprintPath', 'destination'],
      },
    },
    {
      name: 'fill_slot',
      description: 'Fill a content slot in a page with text, markdown, or component config',
      inputSchema: {
        type: 'object',
        properties: {
          sitePath: { type: 'string', description: 'Path to site directory' },
          pageId: { type: 'string', description: 'Page ID to modify' },
          slotId: { type: 'string', description: 'Slot ID to fill' },
          content: { type: 'string', description: 'Content to insert' },
          dryRun: { type: 'boolean', description: 'Preview without writing', default: false },
        },
        required: ['sitePath', 'pageId', 'slotId', 'content'],
      },
    },
    {
      name: 'list_slots',
      description: 'List all available slots in a site',
      inputSchema: {
        type: 'object',
        properties: {
          sitePath: { type: 'string', description: 'Path to site directory' },
        },
        required: ['sitePath'],
      },
    },
    {
      name: 'update_theme',
      description: 'Update theme tokens (colors, typography) for a site',
      inputSchema: {
        type: 'object',
        properties: {
          sitePath: { type: 'string', description: 'Path to site directory' },
          tokens: {
            type: 'object',
            properties: {
              colors: { type: 'object', description: 'Color token overrides (hex format)' },
              typography: { type: 'object', description: 'Typography token overrides' },
            },
          },
          mode: { type: 'string', enum: ['light', 'dark', 'both'], default: 'both' },
          dryRun: { type: 'boolean', description: 'Preview without writing', default: false },
        },
        required: ['sitePath', 'tokens'],
      },
    },
    {
      name: 'add_component',
      description: 'Add a component to a page at a specific location',
      inputSchema: {
        type: 'object',
        properties: {
          sitePath: { type: 'string', description: 'Path to site directory' },
          componentId: { type: 'string', description: 'Component ID (e.g., shadcn.button)' },
          location: {
            type: 'object',
            properties: {
              pageId: { type: 'string', description: 'Page ID' },
              after: { type: 'string', description: 'Insert after element ID' },
              before: { type: 'string', description: 'Insert before element ID' },
            },
            required: ['pageId'],
          },
          props: { type: 'object', description: 'Component props' },
          dryRun: { type: 'boolean', description: 'Preview without writing', default: false },
        },
        required: ['sitePath', 'componentId', 'location'],
      },
    },
    {
      name: 'generate_screenshot',
      description: 'Generate a screenshot preview of a template or site',
      inputSchema: {
        type: 'object',
        properties: {
          templateId: { type: 'string', description: 'Template ID (if generating from template)' },
          sitePath: { type: 'string', description: 'Site path (if generating from site)' },
          url: { type: 'string', description: 'URL (if generating from live site)' },
          outputPath: { type: 'string', description: 'Output path for screenshot' },
          viewport: {
            type: 'object',
            properties: {
              width: { type: 'number', default: 1280 },
              height: { type: 'number', default: 800 },
            },
          },
          fullPage: { type: 'boolean', default: true },
        },
      },
    },
    {
      name: 'validate_site',
      description: 'Validate site for errors (type check, lint, build)',
      inputSchema: {
        type: 'object',
        properties: {
          sitePath: { type: 'string', description: 'Path to site directory' },
        },
        required: ['sitePath'],
      },
    },
    {
      name: 'diff_summary',
      description: 'Get git diff summary for site changes',
      inputSchema: {
        type: 'object',
        properties: {
          sitePath: { type: 'string', description: 'Path to site directory' },
          staged: { type: 'boolean', description: 'Show only staged changes (default: all)', default: false },
        },
        required: ['sitePath'],
      },
    },
    {
      name: 'cache_stats',
      description: 'Get template cache statistics',
      inputSchema: {
        type: 'object',
        properties: {},
      },
    },
    {
      name: 'refresh_cache',
      description: 'Refresh template cache from Railway API',
      inputSchema: {
        type: 'object',
        properties: {
          templateId: { type: 'string', description: 'Template ID to refresh (all if omitted)' },
        },
      },
    },
    // Phase 1A: New component extraction tools
    {
      name: 'list_components',
      description: 'List all extractable components from a template',
      inputSchema: {
        type: 'object',
        properties: {
          templateId: { type: 'string', description: 'Template ID to scan' },
        },
        required: ['templateId'],
      },
    },
    {
      name: 'extract_component',
      description: 'Extract a component from template with its dependencies',
      inputSchema: {
        type: 'object',
        properties: {
          templateId: { type: 'string', description: 'Template ID' },
          componentPath: { type: 'string', description: 'Component path (e.g., src/components/hero.tsx)' },
          destination: { type: 'string', description: 'Destination path' },
          withDependencies: { type: 'boolean', description: 'Include relative imports', default: true },
          maxDepth: { type: 'number', description: 'Max dependency depth (default: 3)', default: 3 },
          overwrite: { type: 'boolean', description: 'Overwrite existing files', default: false },
          dryRun: { type: 'boolean', description: 'Preview without writing', default: false },
        },
        required: ['templateId', 'componentPath', 'destination'],
      },
    },
    {
      name: 'compose_page',
      description: 'Compose a Next.js page from component sections',
      inputSchema: {
        type: 'object',
        properties: {
          sitePath: { type: 'string', description: 'Site root directory' },
          pagePath: { type: 'string', description: 'Page file path (e.g., app/page.tsx)' },
          sections: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                importPath: { type: 'string', description: 'Import path' },
                componentName: { type: 'string', description: 'Component name (auto-detected if omitted)' },
                props: { type: 'object', description: 'Component props' },
              },
              required: ['importPath'],
            },
          },
          overwrite: { type: 'boolean', description: 'Overwrite existing page', default: true },
          dryRun: { type: 'boolean', description: 'Preview without writing', default: false },
        },
        required: ['sitePath', 'pagePath', 'sections'],
      },
    },
  ],
}));

// Tool handlers
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const startTime = Date.now();

  try {
    switch (name) {
      case 'list_templates': {
        const input = ListTemplatesSchema.parse(args);
        const { cached, available } = await listAllTemplates();

        // Combine and deduplicate
        const templatesMap = new Map();

        // Add cached templates
        for (const template of cached) {
          templatesMap.set(template.id, {
            id: template.id,
            name: template.name,
            version: template.version,
            cached: true,
          });
        }

        // Add API templates
        for (const template of available) {
          if (!templatesMap.has(template.id)) {
            templatesMap.set(template.id, {
              ...template,
              cached: false,
            });
          } else {
            // Merge cached + API data
            templatesMap.set(template.id, {
              ...templatesMap.get(template.id),
              ...template,
              cached: true,
            });
          }
        }

        let templates = Array.from(templatesMap.values());

        // Apply filters
        if (input.filter?.capability) {
          templates = templates.filter((t: any) =>
            t.capabilities?.includes(input.filter!.capability)
          );
        }
        if (input.filter?.author) {
          templates = templates.filter((t: any) =>
            t.author?.toLowerCase().includes(input.filter!.author!.toLowerCase())
          );
        }
        if (input.filter?.stack) {
          templates = templates.filter((t: any) =>
            t.stack?.includes(input.filter!.stack!)
          );
        }

        return formatResult({
          ok: true,
          count: templates.length,
          templates,
          elapsedMs: Date.now() - startTime,
        });
      }

      case 'get_template': {
        const input = GetTemplateSchema.parse(args);

        try {
          const response = await axios.get(
            `${API_BASE_URL}/api/templates/${input.templateId}`
          );

          return formatResult({
            ...response.data,
            elapsedMs: Date.now() - startTime,
          });
        } catch (error: any) {
          return formatError(`TEMPLATE_NOT_FOUND: ${error.message}`);
        }
      }

      case 'init_site': {
        const input = InitSiteSchema.parse(args);

        // Get template from cache or API
        const { buffer, entry, source } = await getTemplate(input.templateId);

        // Extract to destination
        const destPath = path.join(input.destination, input.siteId);

        const extractResult = await extractZipSafely(buffer, {
          destDir: destPath,
          overwrite: input.overwrite || false,
          dryRun: input.dryRun || false,
        });

        if (!extractResult.success) {
          return formatError('EXTRACTION_FAILED', {
            errors: extractResult.errors,
            warnings: extractResult.warnings,
          });
        }

        // Create initial site.json blueprint
        if (!input.dryRun) {
          const blueprint = {
            templateId: input.templateId,
            siteId: input.siteId,
            siteName: input.siteName || input.siteId,
            brand: {
              name: input.siteName || input.siteId,
              tokens: {},
            },
            pages: [],
            metadata: {
              created: new Date().toISOString(),
              version: entry.version,
              schemaVersion: '1.0.0',
            },
          };

          await fs.writeFile(
            path.join(destPath, 'site.json'),
            JSON.stringify(blueprint, null, 2)
          );
        }

        return formatResult({
          ok: true,
          message: `Site initialized at ${destPath}`,
          siteId: input.siteId,
          templateId: input.templateId,
          path: destPath,
          source,
          filesExtracted: extractResult.filesExtracted.length,
          warnings: extractResult.warnings,
          elapsedMs: Date.now() - startTime,
        });
      }

      case 'apply_blueprint': {
        const input = ApplyBlueprintSchema.parse(args);

        // Load and validate blueprint
        const { data: blueprint, validation } = await loadAndValidateBlueprint(
          input.blueprintPath
        );

        if (!validation.valid) {
          return formatError('INVALID_BLUEPRINT', {
            errors: validation.errors,
            warnings: validation.warnings,
          });
        }

        // Apply slots
        const slotsApplied: string[] = [];
        const errors: string[] = [];

        if (blueprint.pages) {
          for (const page of blueprint.pages) {
            if (page.enabled === false) continue;

            if (page.slots) {
              for (const [slotId, slotContent] of Object.entries(page.slots)) {
                const result = await fillSlot({
                  sitePath: input.destination,
                  pageId: page.pageId,
                  slotId,
                  content: (slotContent as any).content,
                  dryRun: input.dryRun,
                });

                if (result.success) {
                  slotsApplied.push(`${page.pageId}:${slotId}`);
                } else {
                  errors.push(...result.errors);
                }
              }
            }
          }
        }

        // Apply theme tokens
        if (blueprint.brand?.tokens) {
          const themeResult = await updateTheme({
            sitePath: input.destination,
            tokens: blueprint.brand.tokens,
            dryRun: input.dryRun,
          });

          if (!themeResult.success) {
            errors.push(...themeResult.errors);
          }
        }

        return formatResult({
          ok: true,
          message: 'Blueprint applied successfully',
          slotsApplied: slotsApplied.length,
          warnings: validation.warnings,
          errors,
          elapsedMs: Date.now() - startTime,
        });
      }

      case 'fill_slot': {
        const input = FillSlotSchema.parse(args);
        const result = await fillSlot(input);

        return formatResult({
          ...result,
          elapsedMs: Date.now() - startTime,
        });
      }

      case 'list_slots': {
        const input = ListSlotsSchema.parse(args);
        const slots = await listAllSlots(input.sitePath);

        const slotsList: any[] = [];
        for (const [file, slotIds] of slots.entries()) {
          slotsList.push({ file, slots: slotIds });
        }

        return formatResult({
          ok: true,
          totalSlots: slotsList.reduce((sum, f) => sum + f.slots.length, 0),
          files: slotsList,
          elapsedMs: Date.now() - startTime,
        });
      }

      case 'update_theme': {
        const input = UpdateThemeSchema.parse(args);
        const result = await updateTheme(input);

        return formatResult({
          ...result,
          elapsedMs: Date.now() - startTime,
        });
      }

      case 'add_component': {
        const input = AddComponentSchema.parse(args);
        const result = await insertComponent(input);

        return formatResult({
          ...result,
          elapsedMs: Date.now() - startTime,
        });
      }

      case 'generate_screenshot': {
        const input = GenerateScreenshotSchema.parse(args);
        const result = await generateScreenshot(input);

        return formatResult(result);
      }

      case 'validate_site': {
        const input = ValidateSiteSchema.parse(args);
        const { spawn } = await import('child_process');
        const { promisify } = await import('util');
        const execAsync = promisify(spawn);

        const checks: Record<string, string> = {};
        const warnings: string[] = [];
        const errors: string[] = [];

        // Check if package.json exists
        const packageJsonPath = path.join(input.sitePath, 'package.json');
        try {
          await fs.access(packageJsonPath);
          checks.packageJson = 'exists';
        } catch {
          return formatError('INVALID_SITE', {
            message: 'No package.json found in site directory',
          });
        }

        // Read package.json to check for scripts
        const packageJson = JSON.parse(await fs.readFile(packageJsonPath, 'utf-8'));
        const hasLint = !!packageJson.scripts?.lint;
        const hasTypecheck = !!packageJson.scripts?.typecheck;
        const hasBuild = !!packageJson.scripts?.build;

        // Run lint if available
        if (hasLint) {
          try {
            const lintProc = spawn('npm', ['run', 'lint'], {
              cwd: input.sitePath,
              stdio: 'pipe',
            });
            const lintOutput = await new Promise<string>((resolve, reject) => {
              let output = '';
              lintProc.stdout?.on('data', (data) => (output += data.toString()));
              lintProc.stderr?.on('data', (data) => (output += data.toString()));
              lintProc.on('close', (code) => {
                if (code === 0) resolve('passed');
                else reject(output);
              });
              setTimeout(() => reject('timeout'), 30000);
            });
            checks.lint = 'passed';
          } catch (error: any) {
            checks.lint = 'failed';
            errors.push(`Lint errors detected`);
          }
        } else {
          checks.lint = 'not available';
          warnings.push('No lint script found in package.json');
        }

        // Run typecheck if available
        if (hasTypecheck) {
          try {
            const typecheckProc = spawn('npm', ['run', 'typecheck'], {
              cwd: input.sitePath,
              stdio: 'pipe',
            });
            await new Promise<string>((resolve, reject) => {
              let output = '';
              typecheckProc.stdout?.on('data', (data) => (output += data.toString()));
              typecheckProc.stderr?.on('data', (data) => (output += data.toString()));
              typecheckProc.on('close', (code) => {
                if (code === 0) resolve('passed');
                else reject(output);
              });
              setTimeout(() => reject('timeout'), 30000);
            });
            checks.typecheck = 'passed';
          } catch (error: any) {
            checks.typecheck = 'failed';
            errors.push(`Type errors detected`);
          }
        } else {
          checks.typecheck = 'not available';
          warnings.push('No typecheck script found in package.json');
        }

        // Check route health (basic file existence)
        const routesDir = path.join(input.sitePath, 'app');
        try {
          await fs.access(routesDir);
          checks.routeHealth = 'passed';
        } catch {
          checks.routeHealth = 'no app directory';
        }

        return formatResult({
          ok: errors.length === 0,
          checks,
          warnings,
          errors,
          elapsedMs: Date.now() - startTime,
        });
      }

      case 'diff_summary': {
        const input = DiffSummarySchema.parse(args);
        const { spawn } = await import('child_process');

        try {
          // Check if it's a git repository
          const gitCheckProc = spawn('git', ['rev-parse', '--git-dir'], {
            cwd: input.sitePath,
            stdio: 'pipe',
          });
          await new Promise((resolve, reject) => {
            gitCheckProc.on('close', (code) => {
              if (code === 0) resolve(null);
              else reject(new Error('Not a git repository'));
            });
          });

          // Get diff
          const diffArgs = input.staged ? ['diff', '--cached'] : ['diff', 'HEAD'];
          const diffProc = spawn('git', diffArgs, {
            cwd: input.sitePath,
            stdio: 'pipe',
          });

          const patch = await new Promise<string>((resolve, reject) => {
            let output = '';
            diffProc.stdout?.on('data', (data) => (output += data.toString()));
            diffProc.on('close', () => resolve(output));
            diffProc.on('error', reject);
            setTimeout(() => reject(new Error('timeout')), 10000);
          });

          // Parse diff stats
          const statsProc = spawn('git', [...diffArgs, '--stat'], {
            cwd: input.sitePath,
            stdio: 'pipe',
          });

          const stats = await new Promise<string>((resolve, reject) => {
            let output = '';
            statsProc.stdout?.on('data', (data) => (output += data.toString()));
            statsProc.on('close', () => resolve(output));
            statsProc.on('error', reject);
            setTimeout(() => reject(new Error('timeout')), 10000);
          });

          return formatResult({
            ok: true,
            patch,
            stats,
            hasChanges: patch.length > 0,
            elapsedMs: Date.now() - startTime,
          });
        } catch (error: any) {
          return formatError('DIFF_FAILED', {
            message: error.message,
            elapsedMs: Date.now() - startTime,
          });
        }
      }

      case 'cache_stats': {
        const stats = await getCacheStats();

        return formatResult({
          ok: true,
          ...stats,
          cachePath: TEMPLATES_DIR,
          elapsedMs: Date.now() - startTime,
        });
      }

      case 'refresh_cache': {
        const input = RefreshCacheSchema.parse(args);

        if (input.templateId) {
          const entry = await refreshCache(input.templateId);
          return formatResult({
            ok: true,
            message: `Refreshed cache for ${input.templateId}`,
            template: entry,
            elapsedMs: Date.now() - startTime,
          });
        } else {
          return formatResult({
            ok: false,
            message: 'Refresh all not yet implemented',
            elapsedMs: Date.now() - startTime,
          });
        }
      }

      // Phase 1A: New component extraction tool handlers
      case 'list_components': {
        const input = ListComponentsSchema.parse(args);
        const result = await listComponents(input.templateId);

        return formatResult({
          ...result,
          elapsedMs: Date.now() - startTime,
        });
      }

      case 'extract_component': {
        const input = ExtractComponentSchema.parse(args);
        const result = await extractComponent(input);

        return formatResult({
          ok: result.success,
          ...result,
          elapsedMs: Date.now() - startTime,
        });
      }

      case 'compose_page': {
        const input = ComposePageSchema.parse(args);
        const result = await composePage(input);

        return formatResult({
          ok: result.success,
          ...result,
          elapsedMs: Date.now() - startTime,
        });
      }

      default:
        return formatError(`Unknown tool: ${name}`);
    }
  } catch (error: any) {
    return formatError('TOOL_EXECUTION_ERROR', {
      message: error.message,
      stack: error.stack,
      elapsedMs: Date.now() - startTime,
    });
  }
});

// Cleanup on exit
process.on('SIGINT', async () => {
  console.error('[Cleanup] Closing browser...');
  await closeBrowser();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.error('[Cleanup] Closing browser...');
  await closeBrowser();
  process.exit(0);
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('UI Template Bridge MCP server v2.0.0 running on stdio');
  console.error(`[Cache] Using templates directory: ${TEMPLATES_DIR}`);
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});

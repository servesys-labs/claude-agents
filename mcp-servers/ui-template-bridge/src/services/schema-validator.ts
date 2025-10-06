import Ajv from 'ajv';
import type { ErrorObject } from 'ajv';
import addFormats from 'ajv-formats';
import { promises as fs } from 'fs';
import path from 'path';

/**
 * Schema validation service with Ajv
 */

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: string[];
}

export interface ValidationError {
  code: string;
  message: string;
  path: string;
  params?: Record<string, any>;
}

const ajv = new Ajv.default({ allErrors: true, strict: false });
addFormats.default(ajv);

// Cache compiled schemas
const schemaCache = new Map<string, any>();

/**
 * Load and compile schema
 */
export async function loadSchema(schemaPath: string): Promise<any> {
  if (schemaCache.has(schemaPath)) {
    return schemaCache.get(schemaPath);
  }

  try {
    const schemaContent = await fs.readFile(schemaPath, 'utf-8');
    const schema = JSON.parse(schemaContent);
    const validate = ajv.compile(schema);
    schemaCache.set(schemaPath, validate);
    return validate;
  } catch (error: any) {
    throw new Error(`Failed to load schema from ${schemaPath}: ${error.message}`);
  }
}

/**
 * Convert Ajv errors to structured format
 */
export function formatAjvErrors(errors: ErrorObject[] | null | undefined): ValidationError[] {
  if (!errors) return [];

  return errors.map((error) => ({
    code: 'SCHEMA_ERROR',
    message: error.message || 'Validation error',
    path: error.instancePath || '/',
    params: error.params,
  }));
}

/**
 * Validate data against schema
 */
export async function validateData(
  data: any,
  schemaPath: string
): Promise<ValidationResult> {
  const result: ValidationResult = {
    valid: false,
    errors: [],
    warnings: [],
  };

  try {
    const validate = await loadSchema(schemaPath);
    const valid = validate(data);

    result.valid = valid;

    if (!valid) {
      result.errors = formatAjvErrors(validate.errors);
    }

    return result;
  } catch (error: any) {
    result.errors.push({
      code: 'VALIDATION_FAILED',
      message: error.message,
      path: '/',
    });
    return result;
  }
}

/**
 * Validate site.json blueprint
 */
export async function validateBlueprint(blueprintData: any): Promise<ValidationResult> {
  const schemaPath = path.join(__dirname, '../schemas/site.json');
  const result = await validateData(blueprintData, schemaPath);

  // Check schema version
  if (blueprintData.metadata?.schemaVersion) {
    const version = blueprintData.metadata.schemaVersion;
    if (!version.match(/^\d+\.\d+\.\d+$/)) {
      result.warnings.push('INVALID_SCHEMA_VERSION: schemaVersion should be semver format (e.g., "1.0.0")');
    }
  } else {
    result.warnings.push('MISSING_SCHEMA_VERSION: Consider adding metadata.schemaVersion for future compatibility');
  }

  // Check for required fields
  if (!blueprintData.templateId) {
    result.errors.push({
      code: 'MISSING_TEMPLATE_ID',
      message: 'Blueprint must specify a templateId',
      path: '/templateId',
    });
  }

  if (!blueprintData.siteId) {
    result.errors.push({
      code: 'MISSING_SITE_ID',
      message: 'Blueprint must specify a siteId',
      path: '/siteId',
    });
  }

  // Validate siteId format (kebab-case)
  if (blueprintData.siteId && !blueprintData.siteId.match(/^[a-z0-9]+(-[a-z0-9]+)*$/)) {
    result.errors.push({
      code: 'INVALID_SITE_ID',
      message: 'siteId must be kebab-case (lowercase with hyphens)',
      path: '/siteId',
    });
  }

  return result;
}

/**
 * Validate template meta.json
 */
export async function validateTemplateMeta(metaData: any): Promise<ValidationResult> {
  const schemaPath = path.join(__dirname, '../schemas/meta.json');
  const result = await validateData(metaData, schemaPath);

  // Check schema version
  if (metaData.version) {
    const version = metaData.version;
    if (!version.match(/^\d+\.\d+\.\d+$/)) {
      result.warnings.push('INVALID_VERSION: version should be semver format (e.g., "1.0.0")');
    }
  } else {
    result.warnings.push('MISSING_VERSION: Template should specify a version');
  }

  // Check for stable component IDs
  if (metaData.components) {
    const componentIds = Object.keys(metaData.components);
    for (const componentId of componentIds) {
      if (!componentId.match(/^[a-z0-9]+(-[a-z0-9]+)*$/)) {
        result.warnings.push(`INVALID_COMPONENT_ID: "${componentId}" should be kebab-case`);
      }
    }
  }

  // Check for stable page IDs
  if (metaData.pages) {
    for (const page of metaData.pages) {
      if (!page.id || !page.id.match(/^[a-z0-9]+(-[a-z0-9]+)*$/)) {
        result.warnings.push(`INVALID_PAGE_ID: "${page.id || 'unknown'}" should be kebab-case`);
      }
    }
  }

  return result;
}

/**
 * Validate color hex format
 */
export function validateHexColor(color: string): boolean {
  return /^#[0-9A-Fa-f]{6}$/.test(color);
}

/**
 * Validate all theme tokens
 */
export function validateThemeTokens(tokens: any): ValidationResult {
  const result: ValidationResult = {
    valid: true,
    errors: [],
    warnings: [],
  };

  // Validate colors
  if (tokens.colors) {
    for (const [colorName, colorValue] of Object.entries(tokens.colors)) {
      if (typeof colorValue === 'string' && colorValue.startsWith('#')) {
        if (!validateHexColor(colorValue)) {
          result.errors.push({
            code: 'INVALID_COLOR',
            message: `Color "${colorName}" must be a valid hex color (e.g., #0070f3)`,
            path: `/colors/${colorName}`,
          });
          result.valid = false;
        }
      }
    }
  }

  // Validate font families
  if (tokens.typography?.fontFamily) {
    const validFontTypes = ['sans', 'mono', 'display'];
    for (const fontType of Object.keys(tokens.typography.fontFamily)) {
      if (!validFontTypes.includes(fontType)) {
        result.warnings.push(`UNKNOWN_FONT_TYPE: "${fontType}" is not a standard font type (sans, mono, display)`);
      }
    }
  }

  return result;
}

/**
 * Load and validate blueprint from file
 */
export async function loadAndValidateBlueprint(
  blueprintPath: string
): Promise<{ data: any; validation: ValidationResult }> {
  try {
    const content = await fs.readFile(blueprintPath, 'utf-8');
    const data = JSON.parse(content);
    const validation = await validateBlueprint(data);

    return { data, validation };
  } catch (error: any) {
    return {
      data: null,
      validation: {
        valid: false,
        errors: [
          {
            code: 'BLUEPRINT_LOAD_ERROR',
            message: error.message,
            path: '/',
          },
        ],
        warnings: [],
      },
    };
  }
}

/**
 * Validate file exists and is readable
 */
export async function validateFileAccess(filePath: string): Promise<ValidationResult> {
  const result: ValidationResult = {
    valid: true,
    errors: [],
    warnings: [],
  };

  try {
    await fs.access(filePath);
    const stats = await fs.stat(filePath);

    if (stats.isDirectory()) {
      result.valid = false;
      result.errors.push({
        code: 'NOT_A_FILE',
        message: 'Path points to a directory, not a file',
        path: filePath,
      });
    }
  } catch (error: any) {
    result.valid = false;
    result.errors.push({
      code: 'FILE_NOT_ACCESSIBLE',
      message: error.message,
      path: filePath,
    });
  }

  return result;
}

import { promises as fs } from 'fs';
import path from 'path';

/**
 * Component insertion service - adds components at stable element IDs
 */

export interface InsertComponentOptions {
  sitePath: string;
  componentId: string;
  location: {
    pageId: string;
    after?: string;
    before?: string;
  };
  props?: Record<string, any>;
  dryRun?: boolean;
}

export interface InsertComponentResult {
  success: boolean;
  changed: boolean;
  changedFiles: string[];
  warnings: string[];
  errors: string[];
  preview?: string;
}

/**
 * Find component import in file
 */
export function findComponentImport(content: string, componentName: string): boolean {
  const importPattern = new RegExp(
    `import\\s+{[^}]*\\b${componentName}\\b[^}]*}\\s+from`,
    'g'
  );
  return importPattern.test(content);
}

/**
 * Add component import to file
 */
export function addComponentImport(
  content: string,
  componentName: string,
  importPath: string
): string {
  const lines = content.split('\n');

  // Find last import statement
  let lastImportIndex = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim().startsWith('import ')) {
      lastImportIndex = i;
    }
  }

  // Add import after last import
  const importStatement = `import { ${componentName} } from '${importPath}';`;

  if (lastImportIndex >= 0) {
    lines.splice(lastImportIndex + 1, 0, importStatement);
  } else {
    // No imports found, add at beginning
    lines.unshift(importStatement, '');
  }

  return lines.join('\n');
}

/**
 * Find element by stable ID in JSX
 */
export function findElementById(content: string, elementId: string): number | null {
  const lines = content.split('\n');

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Look for id={elementId}, id="{elementId}", or data-id="{elementId}"
    if (
      line.includes(`id="${elementId}"`) ||
      line.includes(`id={'${elementId}'}`) ||
      line.includes(`id={\`${elementId}\`}`) ||
      line.includes(`data-id="${elementId}"`)
    ) {
      return i;
    }
  }

  return null;
}

/**
 * Insert component JSX at location
 */
export function insertComponentJSX(
  content: string,
  componentName: string,
  props: Record<string, any>,
  location: { after?: string; before?: string }
): { success: boolean; content: string; error?: string } {
  const lines = content.split('\n');

  let insertIndex: number | null = null;

  if (location.after) {
    const afterIndex = findElementById(content, location.after);
    if (afterIndex === null) {
      return {
        success: false,
        content,
        error: `ELEMENT_NOT_FOUND: Could not find element with id="${location.after}"`,
      };
    }

    // Find closing tag for the element
    let openTags = 0;
    for (let i = afterIndex; i < lines.length; i++) {
      const line = lines[i];
      openTags += (line.match(/<(?!\/)[\w-]+/g) || []).length; // Opening tags
      openTags -= (line.match(/<\/[\w-]+>/g) || []).length; // Closing tags

      if (openTags === 0) {
        insertIndex = i + 1;
        break;
      }
    }

    if (insertIndex === null) {
      insertIndex = afterIndex + 1;
    }
  } else if (location.before) {
    const beforeIndex = findElementById(content, location.before);
    if (beforeIndex === null) {
      return {
        success: false,
        content,
        error: `ELEMENT_NOT_FOUND: Could not find element with id="${location.before}"`,
      };
    }
    insertIndex = beforeIndex;
  } else {
    return {
      success: false,
      content,
      error: 'MISSING_LOCATION: Must specify either "after" or "before"',
    };
  }

  // Get indentation from surrounding lines
  const indent = lines[insertIndex - 1]?.match(/^(\s*)/)?.[1] || '      ';

  // Build component JSX
  let componentJSX = `<${componentName}`;

  if (Object.keys(props).length > 0) {
    for (const [key, value] of Object.entries(props)) {
      if (typeof value === 'string') {
        componentJSX += `\n${indent}  ${key}="${value}"`;
      } else if (typeof value === 'boolean') {
        if (value) {
          componentJSX += `\n${indent}  ${key}`;
        }
      } else {
        componentJSX += `\n${indent}  ${key}={${JSON.stringify(value)}}`;
      }
    }
    componentJSX += `\n${indent}/>`;
  } else {
    componentJSX += ' />';
  }

  // Insert component
  lines.splice(insertIndex, 0, `${indent}${componentJSX}`);

  return {
    success: true,
    content: lines.join('\n'),
  };
}

/**
 * Get component import path
 */
export function getComponentImportPath(componentId: string): string {
  // Parse component ID: vendor.component-name -> @vendor/ui or ../components
  if (componentId.includes('.')) {
    const [vendor, name] = componentId.split('.');

    if (vendor === 'shadcn') {
      return `@/components/ui/${name}`;
    } else if (vendor === 'magicui') {
      return `@/components/magicui/${name}`;
    } else {
      return `@/components/${name}`;
    }
  } else {
    return `@/components/${componentId}`;
  }
}

/**
 * Convert component ID to component name (PascalCase)
 */
export function componentIdToName(componentId: string): string {
  // Remove vendor prefix if present
  const name = componentId.includes('.') ? componentId.split('.')[1] : componentId;

  // Convert kebab-case to PascalCase
  return name
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join('');
}

/**
 * Find page files for component insertion
 */
export async function findPageFilesForInsertion(
  sitePath: string,
  pageId: string
): Promise<string[]> {
  const searchPaths = [
    path.join(sitePath, 'app', `${pageId}.tsx`),
    path.join(sitePath, 'app', `${pageId}.jsx`),
    path.join(sitePath, 'app', pageId, 'page.tsx'),
    path.join(sitePath, 'app', pageId, 'page.jsx'),
    path.join(sitePath, 'src', 'app', `${pageId}.tsx`),
    path.join(sitePath, 'src', 'app', pageId, 'page.tsx'),
    path.join(sitePath, 'pages', `${pageId}.tsx`),
    path.join(sitePath, 'pages', `${pageId}.jsx`),
  ];

  const existingFiles: string[] = [];

  for (const filePath of searchPaths) {
    try {
      await fs.access(filePath);
      existingFiles.push(filePath);
    } catch {
      // File doesn't exist
    }
  }

  return existingFiles;
}

/**
 * Insert component into page
 */
export async function insertComponent(
  options: InsertComponentOptions
): Promise<InsertComponentResult> {
  const { sitePath, componentId, location, props = {}, dryRun = false } = options;

  const result: InsertComponentResult = {
    success: false,
    changed: false,
    changedFiles: [],
    warnings: [],
    errors: [],
  };

  try {
    // Find page file
    const pageFiles = await findPageFilesForInsertion(sitePath, location.pageId);

    if (pageFiles.length === 0) {
      result.errors.push(`PAGE_NOT_FOUND: No files found for page '${location.pageId}'`);
      return result;
    }

    if (pageFiles.length > 1) {
      result.warnings.push(
        `MULTIPLE_FILES: Found ${pageFiles.length} files for page '${location.pageId}', using first match`
      );
    }

    const targetFile = pageFiles[0];

    // Read file content
    let content = await fs.readFile(targetFile, 'utf-8');

    // Get component name and import path
    const componentName = componentIdToName(componentId);
    const importPath = getComponentImportPath(componentId);

    // Check if component is already imported
    const hasImport = findComponentImport(content, componentName);

    // Add import if missing
    if (!hasImport) {
      content = addComponentImport(content, componentName, importPath);
    }

    // Insert component JSX
    const { success, content: newContent, error } = insertComponentJSX(
      content,
      componentName,
      props,
      location
    );

    if (!success) {
      result.errors.push(error || 'Unknown error');
      return result;
    }

    // Check if content changed
    if (newContent === content) {
      result.success = true;
      result.changed = false;
      result.warnings.push('NO_CHANGES: Component may already exist at this location');
      return result;
    }

    // Dry run: return preview
    if (dryRun) {
      result.success = true;
      result.changed = true;
      result.changedFiles = [path.relative(sitePath, targetFile)];
      result.warnings.push('DRY_RUN: No files were modified');
      result.preview = newContent;
      return result;
    }

    // Write updated content
    await fs.writeFile(targetFile, newContent, 'utf-8');

    result.success = true;
    result.changed = true;
    result.changedFiles = [path.relative(sitePath, targetFile)];

    return result;
  } catch (error: any) {
    result.errors.push(`INSERT_COMPONENT_ERROR: ${error.message}`);
    return result;
  }
}

/**
 * Check if component already exists in page
 */
export async function componentExistsInPage(
  sitePath: string,
  pageId: string,
  componentId: string
): Promise<boolean> {
  const pageFiles = await findPageFilesForInsertion(sitePath, pageId);

  if (pageFiles.length === 0) return false;

  const componentName = componentIdToName(componentId);

  for (const filePath of pageFiles) {
    try {
      const content = await fs.readFile(filePath, 'utf-8');
      if (content.includes(`<${componentName}`)) {
        return true;
      }
    } catch {
      // Skip files we can't read
    }
  }

  return false;
}

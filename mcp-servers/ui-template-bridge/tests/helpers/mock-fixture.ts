import { vi } from 'vitest';
import JSZip from 'jszip';

/**
 * Mock Template Registry
 * Maps template IDs to ZIP buffers for testing without network calls
 */
const mockTemplateRegistry = new Map<string, Buffer>();

/**
 * Creates a mock ZIP buffer from file structure
 * @param files - Record of file paths to contents
 * @returns ZIP buffer
 */
export async function createMockZip(files: Record<string, string>): Promise<Buffer> {
  const zip = new JSZip();

  for (const [path, content] of Object.entries(files)) {
    zip.file(path, content);
  }

  const buffer = await zip.generateAsync({
    type: 'nodebuffer',
    compression: 'DEFLATE',
    compressionOptions: { level: 6 }
  });

  return buffer;
}

/**
 * Registers a mock template in the registry
 * @param templateId - Unique template identifier
 * @param files - Record of file paths to contents
 */
export async function registerMockTemplate(
  templateId: string,
  files: Record<string, string>
): Promise<void> {
  const buffer = await createMockZip(files);
  mockTemplateRegistry.set(templateId, buffer);
}

/**
 * Unregisters a mock template from the registry
 * @param templateId - Template identifier to remove
 */
export function unregisterMockTemplate(templateId: string): void {
  mockTemplateRegistry.delete(templateId);
}

/**
 * Retrieves a mock template buffer from the registry
 * @param templateId - Template identifier
 * @returns ZIP buffer or undefined if not found
 */
export function getMockTemplateBuffer(templateId: string): Buffer | undefined {
  return mockTemplateRegistry.get(templateId);
}

/**
 * Clears all mock templates from the registry
 */
export function clearMockTemplates(): void {
  mockTemplateRegistry.clear();
}

/**
 * Gets all registered template IDs
 * @returns Array of template IDs
 */
export function getRegisteredTemplateIds(): string[] {
  return Array.from(mockTemplateRegistry.keys());
}

/**
 * Mock implementation for template-cache.ts
 * Use this in vi.mock() to intercept template fetches
 */
export const mockTemplateCache = {
  getTemplate: vi.fn(async (templateId: string) => {
    const buffer = getMockTemplateBuffer(templateId);

    if (!buffer) {
      throw new Error(`Mock template not found: ${templateId}`);
    }

    return {
      buffer,
      entry: {
        id: templateId,
        name: `Mock ${templateId}`,
        description: `Mock template for testing`,
        framework: 'next',
        version: '1.0.0',
        author: 'Test Suite',
        tags: ['mock', 'test'],
        timestamp: new Date().toISOString()
      },
      source: 'cache' as const
    };
  })
};

/**
 * Sets up template-cache mocking for tests
 * Call this in your test setup (beforeAll/beforeEach)
 */
export function setupTemplateCacheMock(): void {
  vi.mock('../../src/services/template-cache.js', () => ({
    getTemplate: mockTemplateCache.getTemplate
  }));
}

/**
 * Resets the template cache mock
 * Call this in your test teardown (afterEach/afterAll)
 */
export function resetTemplateCacheMock(): void {
  mockTemplateCache.getTemplate.mockClear();
}

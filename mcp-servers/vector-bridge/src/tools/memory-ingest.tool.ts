/**
 * MCP Tool: memory_ingest
 * Ingest text content into vector store
 */

import { z } from 'zod';
import { MemoryProvider } from '../providers/memory-provider.interface.js';

export const memoryIngestSchema = z.object({
  project_root: z.string().describe('Absolute path to project root (e.g., /Users/name/project)'),
  path: z.string().describe('Relative path within project (e.g., src/utils/helper.ts)'),
  text: z.string().describe('Text content to chunk and index'),
  meta: z.record(z.any()).optional().describe('Optional metadata to attach to chunks'),
});

export async function memoryIngestTool(
  args: z.infer<typeof memoryIngestSchema>,
  provider: MemoryProvider
): Promise<string> {
  try {
    const result = await provider.ingest(
      args.project_root,
      args.path,
      args.text,
      args.meta
    );

    return JSON.stringify({
      success: true,
      chunks: result.chunks,
      project_id: result.project_id,
      message: `Ingested ${result.chunks} chunks from ${args.path}`,
    }, null, 2);
  } catch (error: any) {
    return JSON.stringify({
      success: false,
      error: error.message,
    }, null, 2);
  }
}

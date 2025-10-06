/**
 * MCP Tool: memory_search
 * Search for similar chunks using semantic similarity
 */

import { z } from 'zod';
import { MemoryProvider } from '../providers/memory-provider.interface.js';

export const memorySearchSchema = z.object({
  project_root: z.string().nullable().describe('Project root to search within (null for global search)'),
  query: z.string().describe('Search query text'),
  k: z.number().optional().default(8).describe('Number of results (max 20)'),
  global: z.boolean().optional().default(false).describe('Search across all projects (default: false)'),
});

export async function memorySearchTool(
  args: z.infer<typeof memorySearchSchema>,
  provider: MemoryProvider
): Promise<string> {
  try {
    const result = await provider.search(
      args.project_root as string | null,
      args.query,
      args.k,
      args.global
    );

    if (result.results.length === 0) {
      return JSON.stringify({
        success: true,
        results: [],
        message: 'No results found',
      }, null, 2);
    }

    return JSON.stringify({
      success: true,
      results: result.results.map((r) => ({
        path: r.path,
        chunk: r.chunk.substring(0, 200) + (r.chunk.length > 200 ? '...' : ''),
        score: r.score,
        meta: {
          ...r.meta,
          chunk_id: r.meta?.id || r.meta?.chunk_id, // Include chunk_id for feedback
        },
      })),
      total: result.results.length,
      project_id: result.project_id,
    }, null, 2);
  } catch (error: any) {
    return JSON.stringify({
      success: false,
      error: error.message,
    }, null, 2);
  }
}

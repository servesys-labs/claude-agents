/**
 * MCP Tool: memory_patterns
 * Detect recurring patterns across projects
 * Analyzes global search results to find common solutions
 */

import { z } from 'zod';
import { MemoryProvider } from '../providers/memory-provider.interface.js';

export const memoryPatternsSchema = z.object({
  min_occurrences: z.number().optional().default(3).describe('Minimum times a pattern must appear (default: 3)'),
  category: z.string().optional().describe('Filter by category (decision, code, docs, etc.)'),
});

export async function memoryPatternsTool(
  args: z.infer<typeof memoryPatternsSchema>,
  provider: any // Will need to extend MemoryProvider interface
): Promise<string> {
  try {
    const patterns = await provider.detectPatterns(
      args.min_occurrences,
      args.category
    );

    if (patterns.length === 0) {
      return JSON.stringify({
        success: true,
        patterns: [],
        message: 'No recurring patterns found',
      }, null, 2);
    }

    return JSON.stringify({
      success: true,
      patterns: patterns.map((p: any) => ({
        pattern: p.pattern,
        occurrences: p.occurrences,
        projects: p.projects,
        category: p.category,
        avg_helpfulness: p.avg_helpfulness,
        example_chunks: p.example_chunks.slice(0, 2), // Limit examples
      })),
      total: patterns.length,
    }, null, 2);
  } catch (error: any) {
    return JSON.stringify({
      success: false,
      error: error.message,
    }, null, 2);
  }
}

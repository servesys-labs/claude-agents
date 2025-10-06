/**
 * MCP Tool: memory_feedback
 * Record feedback on memory search results (helpful/not helpful)
 * Used for learning which memories are most valuable
 */

import { z } from 'zod';
import { MemoryProvider } from '../providers/memory-provider.interface.js';

export const memoryFeedbackSchema = z.object({
  chunk_id: z.number().describe('ID of the memory chunk'),
  helpful: z.boolean().describe('Was this memory helpful? (true/false)'),
  context: z.string().optional().describe('Optional context about how it was used'),
});

export async function memoryFeedbackTool(
  args: z.infer<typeof memoryFeedbackSchema>,
  provider: any // Will need to extend MemoryProvider interface
): Promise<string> {
  try {
    // Record feedback in database
    await provider.recordFeedback(
      args.chunk_id,
      args.helpful,
      args.context || null
    );

    return JSON.stringify({
      success: true,
      message: `Feedback recorded for chunk ${args.chunk_id}`,
      helpful: args.helpful,
    }, null, 2);
  } catch (error: any) {
    return JSON.stringify({
      success: false,
      error: error.message,
    }, null, 2);
  }
}

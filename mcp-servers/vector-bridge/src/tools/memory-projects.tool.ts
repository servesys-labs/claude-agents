/**
 * MCP Tool: memory_projects
 * List all indexed projects with statistics
 */

import { z } from 'zod';
import { MemoryProvider } from '../providers/memory-provider.interface.js';

export const memoryProjectsSchema = z.object({});

export async function memoryProjectsTool(
  args: z.infer<typeof memoryProjectsSchema>,
  provider: MemoryProvider
): Promise<string> {
  try {
    const projects = await provider.listProjects();

    return JSON.stringify({
      success: true,
      projects: projects.map((p) => ({
        id: p.id,
        root_path: p.root_path,
        label: p.label,
        doc_count: p.doc_count,
      })),
      total: projects.length,
    }, null, 2);
  } catch (error: any) {
    return JSON.stringify({
      success: false,
      error: error.message,
    }, null, 2);
  }
}

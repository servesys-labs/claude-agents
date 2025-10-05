/**
 * Category Inference Service
 * Auto-detect component and category from file paths and content
 */

export type Component = 'backend' | 'mobile' | 'web' | 'infra' | 'data' | 'docs' | 'tests' | 'other';
export type Category = 'code' | 'docs' | 'ops' | 'tests' | 'data-model' | 'decision';

export class CategoryInferenceService {
  /**
   * Infer component from file path
   */
  inferComponent(path: string): Component {
    const normalized = path.toLowerCase();

    if (normalized.match(/^(mobile|app|ios|android)\//)) {
      return 'mobile';
    }
    if (normalized.match(/^(backend|server|api)\//)) {
      return 'backend';
    }
    if (normalized.match(/^(web|frontend|client)\//)) {
      return 'web';
    }
    if (normalized.match(/^(infra|infrastructure|deploy|docker|k8s|\.github|\.railway)\//)) {
      return 'infra';
    }
    if (normalized.match(/^(data|migrations|seeds|prisma)\//)) {
      return 'data';
    }
    if (normalized.match(/^(docs|documentation)\//)) {
      return 'docs';
    }
    if (normalized.match(/^(test|spec|__tests__|\.test|\.spec)\//)) {
      return 'tests';
    }

    return 'other';
  }

  /**
   * Infer category from file path and content
   */
  inferCategory(path: string, content?: string): Category {
    const normalized = path.toLowerCase();

    // Prioritize by file extension
    if (normalized.match(/\.(md|txt|rst)$/)) {
      return 'docs';
    }
    if (normalized.match(/\.(test|spec)\.(ts|js|tsx|jsx|py)$/)) {
      return 'tests';
    }
    if (normalized.match(/\.(sql|prisma)$/) || normalized.includes('schema')) {
      return 'data-model';
    }
    if (normalized.match(/\.(ya?ml|json|toml|conf|config)$/)) {
      return 'ops';
    }

    // Check content if provided
    if (content) {
      // DIGEST blocks are decisions
      if (content.includes('```json DIGEST') || content.includes('"agent":')) {
        return 'decision';
      }
      // Test files by content
      if (content.match(/describe\(|it\(|test\(|expect\(/)) {
        return 'tests';
      }
    }

    return 'code';
  }

  /**
   * Infer component from multiple file paths (for DIGESTs with multiple files)
   * Returns most common component, or 'other' if mixed
   */
  inferComponentFromFiles(paths: string[]): Component {
    if (paths.length === 0) {
      return 'other';
    }

    const components = paths.map((p) => this.inferComponent(p));
    const counts = new Map<Component, number>();

    for (const comp of components) {
      counts.set(comp, (counts.get(comp) || 0) + 1);
    }

    // Return most common
    let maxCount = 0;
    let maxComponent: Component = 'other';

    for (const [comp, count] of counts.entries()) {
      if (count > maxCount) {
        maxCount = count;
        maxComponent = comp;
      }
    }

    return maxComponent;
  }

  /**
   * Extract tags from text (simple keyword extraction)
   * TODO: Use NLP for better extraction
   */
  extractTags(text: string, maxTags: number = 5): string[] {
    // Common technical keywords
    const keywords = [
      'auth',
      'authentication',
      'api',
      'database',
      'deploy',
      'deployment',
      'test',
      'testing',
      'migration',
      'schema',
      'type',
      'typescript',
      'react',
      'node',
      'express',
      'prisma',
      'postgres',
      'railway',
      'vercel',
      'docker',
      'ci',
      'cd',
      'build',
      'error',
      'fix',
      'bug',
      'feature',
      'refactor',
      'performance',
      'security',
      'ui',
      'ux',
      'mobile',
      'backend',
      'frontend',
      'monorepo',
      'workspace',
      'pnpm',
      'npm',
      'yarn',
    ];

    const normalized = text.toLowerCase();
    const found = new Set<string>();

    for (const keyword of keywords) {
      if (normalized.includes(keyword)) {
        found.add(keyword);
      }
    }

    return Array.from(found).slice(0, maxTags);
  }
}

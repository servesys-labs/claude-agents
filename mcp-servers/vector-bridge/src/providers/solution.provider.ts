/**
 * SolutionProvider - Manages fixpack solutions with vector-based error matching
 * Stores reusable remediation templates for recurring issues
 */

import pg from 'pg';
import { EmbeddingService } from '../services/embedding.service.js';
import { RedisCacheService } from '../services/redis-cache.service.js';

const { Pool } = pg;

export interface Solution {
  id: number;
  title: string;
  description: string;
  category: 'devops' | 'deploy' | 'workspace' | 'tsconfig' | 'migration' | 'build' | 'runtime' | 'test' | 'security' | 'performance';
  component?: string;
  tags: string[];
  project_root?: string;
  repo_name?: string;
  package_manager?: string;
  monorepo_tool?: string;
  success_count: number;
  failure_count: number;
  success_rate: number;
  last_applied_at?: Date;
  verified_on?: Date;
  created_at: Date;
  updated_at: Date;
}

export interface ErrorSignature {
  id: number;
  solution_id: number;
  text: string;
  regexes: string[];
  embedding?: number[];
  meta?: Record<string, any>;
  created_at: Date;
}

export interface RemediationStep {
  id: number;
  solution_id: number;
  step_order: number;
  kind: 'cmd' | 'patch' | 'copy' | 'script' | 'env';
  payload: Record<string, any>;
  description?: string;
  timeout_ms: number;
  created_at: Date;
}

export interface ValidationCheck {
  id: number;
  solution_id: number;
  check_order: number;
  cmd: string;
  expect_substring?: string;
  expect_exit_code: number;
  timeout_ms: number;
  created_at: Date;
}

export interface SolutionMatch {
  solution: Solution;
  score: number;
  signature_text: string;
  step_count: number;
  steps?: RemediationStep[];
  checks?: ValidationCheck[];
}

export interface CreateSolutionInput {
  title: string;
  description?: string;
  category: Solution['category'];
  component?: string;
  tags?: string[];
  project_root?: string;
  repo_name?: string;
  package_manager?: string;
  monorepo_tool?: string;
  signatures: {
    text: string;
    regexes?: string[];
    meta?: Record<string, any>;
  }[];
  steps: {
    step_order: number;
    kind: RemediationStep['kind'];
    payload: Record<string, any>;
    description?: string;
    timeout_ms?: number;
  }[];
  checks?: {
    check_order: number;
    cmd: string;
    expect_substring?: string;
    expect_exit_code?: number;
    timeout_ms?: number;
  }[];
}

export interface SolutionFilters {
  project_root?: string;
  category?: Solution['category'];
  component?: string;
  package_manager?: string;
  monorepo_tool?: string;
}

export class SolutionProvider {
  private pool: pg.Pool;
  private embedding: EmbeddingService;
  private cache?: RedisCacheService;

  constructor(databaseUrl?: string, redisUrl?: string) {
    this.pool = new Pool({
      connectionString: databaseUrl || process.env.DATABASE_URL_MEMORY,
    });

    // Initialize Redis cache if URL provided
    if (redisUrl || process.env.REDIS_URL) {
      this.cache = new RedisCacheService(redisUrl || process.env.REDIS_URL);
      console.log('[SolutionProvider] Redis cache enabled');
    }

    // EmbeddingService with cache for signature matching
    this.embedding = new EmbeddingService(
      process.env.OPENAI_API_KEY,
      'text-embedding-3-small',
      this.cache
    );
  }

  /**
   * Find solutions matching an error message
   * Returns ranked matches by semantic similarity + regex matching
   */
  async findSolutions(
    errorMessage: string,
    filters: SolutionFilters = {},
    limit: number = 5
  ): Promise<SolutionMatch[]> {
    // Generate embedding for error message
    console.log(`[SolutionProvider] Searching for solutions matching: "${errorMessage.substring(0, 100)}..."`);
    const errorEmbedding = await this.embedding.embed(errorMessage);

    // Build filter conditions
    const filterConditions: string[] = [];
    const params: any[] = [JSON.stringify(errorEmbedding), limit];
    let paramIndex = 3;

    if (filters.project_root) {
      filterConditions.push(`(s.project_root IS NULL OR s.project_root = $${paramIndex})`);
      params.push(filters.project_root);
      paramIndex++;
    }

    if (filters.category) {
      filterConditions.push(`s.category = $${paramIndex}`);
      params.push(filters.category);
      paramIndex++;
    }

    if (filters.component) {
      filterConditions.push(`(s.component IS NULL OR s.component = $${paramIndex})`);
      params.push(filters.component);
      paramIndex++;
    }

    if (filters.package_manager) {
      filterConditions.push(`(s.package_manager IS NULL OR s.package_manager = $${paramIndex})`);
      params.push(filters.package_manager);
      paramIndex++;
    }

    if (filters.monorepo_tool) {
      filterConditions.push(`(s.monorepo_tool IS NULL OR s.monorepo_tool = $${paramIndex})`);
      params.push(filters.monorepo_tool);
      paramIndex++;
    }

    const whereClause = filterConditions.length > 0
      ? 'AND ' + filterConditions.join(' AND ')
      : '';

    // Direct SQL query to avoid plpgsql variable ambiguity issues
    const query = `
      SELECT
        s.id as solution_id,
        s.title,
        s.description,
        s.category,
        s.component,
        s.tags,
        (1 - (sig.embedding <=> $1::vector))::numeric AS score,
        CASE
          WHEN (s.success_count + s.failure_count) > 0
          THEN (s.success_count::numeric / (s.success_count + s.failure_count))
          ELSE 0.0
        END AS success_rate,
        sig.text AS signature_text,
        (SELECT COUNT(*) FROM steps WHERE steps.solution_id = s.id) AS step_count
      FROM solutions s
      JOIN signatures sig ON s.id = sig.solution_id
      WHERE sig.embedding IS NOT NULL
        ${whereClause}
      ORDER BY
        sig.embedding <=> $1::vector,
        s.success_count DESC,
        s.verified_on DESC NULLS LAST
      LIMIT $2
    `;

    const result = await this.pool.query(query, params);

    console.log(`[SolutionProvider] Found ${result.rows.length} matching solutions`);

    // Map results to SolutionMatch interface
    const matches: SolutionMatch[] = result.rows.map(row => ({
      solution: {
        id: row.solution_id,
        title: row.title,
        description: row.description || '',
        category: row.category,
        component: row.component,
        tags: row.tags || [],
        success_count: 0, // Will be populated if needed
        failure_count: 0,
        success_rate: row.success_rate || 0,
        created_at: new Date(),
        updated_at: new Date(),
      },
      score: parseFloat(row.score),
      signature_text: row.signature_text,
      step_count: parseInt(row.step_count, 10),
    }));

    return matches;
  }

  /**
   * Create a new solution (fixpack)
   */
  async createSolution(input: CreateSolutionInput): Promise<number> {
    const client = await this.pool.connect();

    try {
      await client.query('BEGIN');

      console.log(`[SolutionProvider] Creating solution: ${input.title}`);

      // Insert solution
      const solutionResult = await client.query(
        `INSERT INTO solutions (
          title, description, category, component, tags,
          project_root, repo_name, package_manager, monorepo_tool,
          success_count, failure_count
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 0, 0)
        RETURNING id`,
        [
          input.title,
          input.description || null,
          input.category,
          input.component || null,
          input.tags || [],
          input.project_root || null,
          input.repo_name || null,
          input.package_manager || null,
          input.monorepo_tool || null,
        ]
      );

      const solutionId = solutionResult.rows[0].id;
      console.log(`[SolutionProvider] Created solution #${solutionId}`);

      // Insert signatures with embeddings
      for (const sig of input.signatures) {
        // Generate embedding for semantic matching
        const embedding = await this.embedding.embed(sig.text);
        const embeddingJson = JSON.stringify(embedding);

        await client.query(
          `INSERT INTO signatures (solution_id, text, regexes, embedding, meta)
           VALUES ($1, $2, $3, $4::vector, $5)`,
          [
            solutionId,
            sig.text,
            sig.regexes || [],
            embeddingJson,
            sig.meta || {},
          ]
        );

        console.log(`[SolutionProvider] Added signature: "${sig.text.substring(0, 60)}..."`);
      }

      // Insert steps
      for (const step of input.steps) {
        await client.query(
          `INSERT INTO steps (solution_id, step_order, kind, payload, description, timeout_ms)
           VALUES ($1, $2, $3, $4, $5, $6)`,
          [
            solutionId,
            step.step_order,
            step.kind,
            step.payload,
            step.description || null,
            step.timeout_ms || 120000, // Default 2 minutes
          ]
        );

        console.log(`[SolutionProvider] Added step #${step.step_order}: ${step.kind}`);
      }

      // Insert checks (if provided)
      if (input.checks) {
        for (const check of input.checks) {
          await client.query(
            `INSERT INTO checks (solution_id, check_order, cmd, expect_substring, expect_exit_code, timeout_ms)
             VALUES ($1, $2, $3, $4, $5, $6)`,
            [
              solutionId,
              check.check_order,
              check.cmd,
              check.expect_substring || null,
              check.expect_exit_code ?? 0,
              check.timeout_ms || 30000, // Default 30 seconds
            ]
          );

          console.log(`[SolutionProvider] Added check #${check.check_order}`);
        }
      }

      await client.query('COMMIT');
      console.log(`[SolutionProvider] Successfully created solution #${solutionId}: ${input.title}`);

      return solutionId;
    } catch (error) {
      await client.query('ROLLBACK');
      console.error('[SolutionProvider] Error creating solution:', error);
      throw error;
    } finally {
      client.release();
    }
  }

  /**
   * Get solution details including steps and checks
   */
  async getSolution(solutionId: number, includeSteps: boolean = true): Promise<SolutionMatch | null> {
    // Use get_solution_details function from migration 003
    const result = await this.pool.query(
      'SELECT * FROM get_solution_details($1)',
      [solutionId]
    );

    if (result.rows.length === 0) {
      return null;
    }

    const row = result.rows[0];
    const solutionData = row.solution;
    const stepsData = row.steps || [];
    const checksData = row.checks || [];

    const match: SolutionMatch = {
      solution: {
        id: solutionData.id,
        title: solutionData.title,
        description: solutionData.description || '',
        category: solutionData.category,
        component: solutionData.component,
        tags: solutionData.tags || [],
        success_count: solutionData.success_count || 0,
        failure_count: solutionData.failure_count || 0,
        success_rate: solutionData.success_count + solutionData.failure_count > 0
          ? solutionData.success_count / (solutionData.success_count + solutionData.failure_count)
          : 0,
        verified_on: solutionData.verified_on,
        created_at: new Date(solutionData.created_at),
        updated_at: new Date(solutionData.updated_at),
      },
      score: 1.0, // Exact match
      signature_text: '',
      step_count: stepsData.length,
    };

    if (includeSteps) {
      match.steps = stepsData.map((s: any) => ({
        id: 0, // Not needed from JSONB
        solution_id: solutionId,
        step_order: s.order,
        kind: s.kind,
        payload: s.payload,
        description: s.description,
        timeout_ms: s.timeout_ms,
        created_at: new Date(),
      }));

      match.checks = checksData.map((c: any) => ({
        id: 0,
        solution_id: solutionId,
        check_order: c.order,
        cmd: c.cmd,
        expect_substring: c.expect_substring,
        expect_exit_code: c.expect_exit_code,
        timeout_ms: c.timeout_ms,
        created_at: new Date(),
      }));
    }

    return match;
  }

  /**
   * Get all steps for a solution
   */
  async getSteps(solutionId: number): Promise<RemediationStep[]> {
    const result = await this.pool.query(
      'SELECT * FROM steps WHERE solution_id = $1 ORDER BY step_order ASC',
      [solutionId]
    );

    return result.rows.map(row => ({
      id: row.id,
      solution_id: row.solution_id,
      step_order: row.step_order,
      kind: row.kind,
      payload: row.payload,
      description: row.description,
      timeout_ms: row.timeout_ms,
      created_at: row.created_at,
    }));
  }

  /**
   * Get all validation checks for a solution
   */
  async getChecks(solutionId: number): Promise<ValidationCheck[]> {
    const result = await this.pool.query(
      'SELECT * FROM checks WHERE solution_id = $1 ORDER BY check_order ASC',
      [solutionId]
    );

    return result.rows.map(row => ({
      id: row.id,
      solution_id: row.solution_id,
      check_order: row.check_order,
      cmd: row.cmd,
      expect_substring: row.expect_substring,
      expect_exit_code: row.expect_exit_code,
      timeout_ms: row.timeout_ms,
      created_at: row.created_at,
    }));
  }

  /**
   * Record solution application (for success rate tracking)
   */
  async recordApplication(solutionId: number, success: boolean): Promise<void> {
    console.log(`[SolutionProvider] Recording ${success ? 'SUCCESS' : 'FAILURE'} for solution #${solutionId}`);

    await this.pool.query(
      'SELECT record_solution_outcome($1, $2)',
      [solutionId, success]
    );

    console.log(`[SolutionProvider] Application recorded`);
  }

  /**
   * Link a pattern to a solution (for pattern-solution learning)
   */
  async linkPatternToSolution(
    patternTag: string,
    patternCategory: string,
    solutionId: number,
    success: boolean
  ): Promise<void> {
    console.log(`[SolutionProvider] Linking pattern "${patternTag}" (${patternCategory}) to solution #${solutionId} - ${success ? 'SUCCESS' : 'FAILURE'}`);

    await this.pool.query(
      'SELECT link_pattern_to_solution($1, $2, $3, $4)',
      [patternTag, patternCategory, solutionId, success]
    );

    console.log(`[SolutionProvider] Pattern-solution link recorded`);
  }

  /**
   * Get solutions for a specific pattern (ranked by success rate for this pattern)
   */
  async getSolutionsForPattern(
    patternTag: string,
    patternCategory?: string,
    limit: number = 5
  ): Promise<SolutionMatch[]> {
    console.log(`[SolutionProvider] Finding solutions for pattern: ${patternTag}${patternCategory ? ` (${patternCategory})` : ''}`);

    const result = await this.pool.query(
      'SELECT * FROM get_solutions_for_pattern($1, $2, $3)',
      [patternTag, patternCategory || null, limit]
    );

    console.log(`[SolutionProvider] Found ${result.rows.length} solutions for pattern`);

    return result.rows.map(row => ({
      solution: {
        id: row.solution_id,
        title: row.title,
        description: row.description || '',
        category: row.category,
        component: undefined,
        tags: [],
        success_count: row.applications || 0,
        failure_count: 0,
        success_rate: row.success_rate || 0,
        created_at: new Date(),
        updated_at: new Date(),
      },
      score: row.success_rate || 0,
      signature_text: '',
      step_count: 0,
    }));
  }

  /**
   * Detect patterns in query text and suggest solutions
   * Returns patterns found in the query with their top solutions
   */
  async detectPatternsInQuery(
    queryText: string,
    limit: number = 3
  ): Promise<Array<{
    patternTag: string;
    patternCategory: string;
    matchScore: number;
    solutionCount: number;
    topSolutionId: number | null;
    topSolutionTitle: string | null;
    topSolutionSuccessRate: number;
  }>> {
    console.log(`[SolutionProvider] Detecting patterns in query: "${queryText.substring(0, 100)}..."`);

    const result = await this.pool.query(
      'SELECT * FROM detect_patterns_in_query($1, $2)',
      [queryText, limit]
    );

    console.log(`[SolutionProvider] Detected ${result.rows.length} patterns`);

    return result.rows.map(row => ({
      patternTag: row.pattern_tag,
      patternCategory: row.pattern_category,
      matchScore: parseFloat(row.match_score),
      solutionCount: parseInt(row.solution_count, 10),
      topSolutionId: row.top_solution_id,
      topSolutionTitle: row.top_solution_title,
      topSolutionSuccessRate: parseFloat(row.top_solution_success_rate || 0),
    }));
  }

  /**
   * Get golden paths (best pattern-solution combinations)
   */
  async getGoldenPaths(
    minApplications: number = 3,
    limit: number = 20
  ): Promise<Array<{
    patternTag: string;
    patternCategory: string;
    solutionId: number;
    solutionTitle: string;
    successRate: number;
    applications: number;
    avgHelpfulRatio: number;
    projectsCount: number;
  }>> {
    console.log(`[SolutionProvider] Fetching golden paths (min ${minApplications} applications)`);

    const result = await this.pool.query(
      'SELECT * FROM get_golden_paths($1, $2)',
      [minApplications, limit]
    );

    console.log(`[SolutionProvider] Found ${result.rows.length} golden paths`);

    return result.rows.map(row => ({
      patternTag: row.pattern_tag,
      patternCategory: row.pattern_category,
      solutionId: row.solution_id,
      solutionTitle: row.solution_title,
      successRate: parseFloat(row.success_rate),
      applications: parseInt(row.applications, 10),
      avgHelpfulRatio: parseFloat(row.avg_helpful_ratio || 0),
      projectsCount: parseInt(row.projects_count, 10),
    }));
  }

  /**
   * Update pattern-solution helpfulness scores from feedback
   */
  async updatePatternSolutionHelpfulness(): Promise<void> {
    console.log(`[SolutionProvider] Updating pattern-solution helpfulness scores from feedback`);

    await this.pool.query('SELECT update_pattern_solution_helpfulness()');

    console.log(`[SolutionProvider] Helpfulness scores updated`);
  }

  /**
   * Update solution metadata
   */
  async updateSolution(
    solutionId: number,
    updates: Partial<Pick<Solution, 'title' | 'description' | 'tags' | 'verified_on'>>
  ): Promise<void> {
    const setClauses: string[] = [];
    const params: any[] = [];
    let paramIndex = 1;

    if (updates.title !== undefined) {
      setClauses.push(`title = $${paramIndex}`);
      params.push(updates.title);
      paramIndex++;
    }

    if (updates.description !== undefined) {
      setClauses.push(`description = $${paramIndex}`);
      params.push(updates.description);
      paramIndex++;
    }

    if (updates.tags !== undefined) {
      setClauses.push(`tags = $${paramIndex}`);
      params.push(updates.tags);
      paramIndex++;
    }

    if (updates.verified_on !== undefined) {
      setClauses.push(`verified_on = $${paramIndex}`);
      params.push(updates.verified_on);
      paramIndex++;
    }

    if (setClauses.length === 0) {
      return;
    }

    setClauses.push('updated_at = now()');
    params.push(solutionId);

    await this.pool.query(
      `UPDATE solutions SET ${setClauses.join(', ')} WHERE id = $${paramIndex}`,
      params
    );

    console.log(`[SolutionProvider] Updated solution #${solutionId}`);
  }

  /**
   * Delete a solution and all its related data (cascade)
   */
  async deleteSolution(solutionId: number): Promise<void> {
    const result = await this.pool.query(
      'DELETE FROM solutions WHERE id = $1 RETURNING title',
      [solutionId]
    );

    if (result.rows.length > 0) {
      console.log(`[SolutionProvider] Deleted solution #${solutionId}: ${result.rows[0].title}`);
    } else {
      console.warn(`[SolutionProvider] Solution #${solutionId} not found`);
    }
  }

  /**
   * List all solutions with optional filters
   */
  async listSolutions(filters: SolutionFilters = {}, limit: number = 50): Promise<Solution[]> {
    const filterConditions: string[] = [];
    const params: any[] = [];
    let paramIndex = 1;

    if (filters.category) {
      filterConditions.push(`category = $${paramIndex}`);
      params.push(filters.category);
      paramIndex++;
    }

    if (filters.component) {
      filterConditions.push(`component = $${paramIndex}`);
      params.push(filters.component);
      paramIndex++;
    }

    if (filters.project_root) {
      filterConditions.push(`(project_root IS NULL OR project_root = $${paramIndex})`);
      params.push(filters.project_root);
      paramIndex++;
    }

    params.push(limit);

    const whereClause = filterConditions.length > 0
      ? 'WHERE ' + filterConditions.join(' AND ')
      : '';

    const result = await this.pool.query(
      `SELECT
         id, title, description, category, component, tags,
         project_root, repo_name, package_manager, monorepo_tool,
         success_count, failure_count, last_applied_at, verified_on,
         created_at, updated_at,
         CASE
           WHEN (success_count + failure_count) > 0
           THEN (success_count::numeric / (success_count + failure_count))
           ELSE 0.0
         END as success_rate
       FROM solutions
       ${whereClause}
       ORDER BY success_count DESC, verified_on DESC NULLS LAST, created_at DESC
       LIMIT $${paramIndex}`,
      params
    );

    return result.rows.map(row => ({
      id: row.id,
      title: row.title,
      description: row.description || '',
      category: row.category,
      component: row.component,
      tags: row.tags || [],
      project_root: row.project_root,
      repo_name: row.repo_name,
      package_manager: row.package_manager,
      monorepo_tool: row.monorepo_tool,
      success_count: row.success_count,
      failure_count: row.failure_count,
      success_rate: parseFloat(row.success_rate),
      last_applied_at: row.last_applied_at,
      verified_on: row.verified_on,
      created_at: row.created_at,
      updated_at: row.updated_at,
    }));
  }

  /**
   * Close database connection
   */
  async close(): Promise<void> {
    await this.pool.end();
    if (this.cache) {
      await this.cache.close();
    }
    console.log('[SolutionProvider] Closed database and cache connections');
  }
}

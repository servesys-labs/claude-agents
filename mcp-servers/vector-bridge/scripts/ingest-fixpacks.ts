#!/usr/bin/env npx tsx
/**
 * Ingest Solution Fixpacks from JSON files into database
 * Reads all fixpacks/*.json and creates solution records with signatures, steps, checks
 */

import { SolutionProvider } from '../src/providers/solution.provider.js';
import { readFileSync, readdirSync } from 'fs';
import { join } from 'path';
import 'dotenv/config';

async function ingestFixpacks() {
  console.log('\n📦 Ingesting Solution Fixpacks\n');
  console.log('═'.repeat(60));

  const DATABASE_URL = process.env.DATABASE_URL_MEMORY || process.env.DATABASE_URL;
  const REDIS_URL = process.env.REDIS_URL;

  if (!DATABASE_URL) {
    console.error('❌ DATABASE_URL_MEMORY or DATABASE_URL not set');
    process.exit(1);
  }

  const solutionProvider = new SolutionProvider(DATABASE_URL, REDIS_URL);

  try {
    // Read all fixpack JSON files
    const fixpacksDir = join(process.cwd(), 'fixpacks');
    const files = readdirSync(fixpacksDir)
      .filter(f => f.endsWith('.json'))
      .sort();

    console.log(`Found ${files.length} fixpack files:\n`);

    let successCount = 0;
    let errorCount = 0;

    for (const file of files) {
      const filepath = join(fixpacksDir, file);
      console.log(`\n📄 Processing: ${file}`);
      console.log('─'.repeat(60));

      try {
        const content = readFileSync(filepath, 'utf-8');
        const fixpack = JSON.parse(content);

        // Validate required fields
        if (!fixpack.title || !fixpack.category || !fixpack.signatures || !fixpack.steps) {
          console.error(`❌ Invalid fixpack: missing required fields`);
          errorCount++;
          continue;
        }

        // Convert to CreateSolutionInput format
        const solutionInput = {
          title: fixpack.title,
          description: fixpack.description || '',
          category: fixpack.category,
          component: fixpack.component,
          tags: fixpack.tags || [],
          project_root: fixpack.project_root,
          repo_name: fixpack.repo_name,
          package_manager: fixpack.package_manager,
          monorepo_tool: fixpack.monorepo_tool,
          signatures: fixpack.signatures.map((sig: any) => ({
            text: sig.text,
            regexes: sig.regexes || [],
            meta: sig.meta || {},
          })),
          steps: fixpack.steps.map((step: any) => ({
            step_order: step.step_order,
            kind: step.kind,
            payload: step.payload,
            description: step.description,
            timeout_ms: step.timeout_ms,
          })),
          checks: fixpack.checks?.map((check: any) => ({
            check_order: check.check_order,
            cmd: check.cmd,
            expect_substring: check.expect_substring,
            expect_exit_code: check.expect_exit_code,
            timeout_ms: check.timeout_ms,
          })) || [],
        };

        // Create solution
        const solutionId = await solutionProvider.createSolution(solutionInput);

        console.log(`✅ Created solution #${solutionId}`);
        console.log(`   Title: ${fixpack.title}`);
        console.log(`   Category: ${fixpack.category}`);
        console.log(`   Signatures: ${fixpack.signatures.length}`);
        console.log(`   Steps: ${fixpack.steps.length}`);
        console.log(`   Checks: ${fixpack.checks?.length || 0}`);

        successCount++;
      } catch (error: any) {
        console.error(`❌ Error processing ${file}:`, error.message);
        errorCount++;
      }
    }

    console.log('\n' + '═'.repeat(60));
    console.log(`\n📊 Summary:`);
    console.log(`   ✅ Success: ${successCount} fixpacks`);
    console.log(`   ❌ Errors: ${errorCount} fixpacks`);
    console.log(`   📦 Total: ${files.length} fixpacks\n`);

    await solutionProvider.close();
    process.exit(errorCount > 0 ? 1 : 0);
  } catch (error: any) {
    console.error('\n❌ Fatal error:', error.message);
    console.error(error.stack);
    await solutionProvider.close();
    process.exit(1);
  }
}

ingestFixpacks();

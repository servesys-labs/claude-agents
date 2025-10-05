#!/usr/bin/env tsx
/**
 * Ingest Script - Called by Stop Hook
 *
 * Ingests session context into vector memory
 * Called by: stop_ingest_memory.py hook
 */

import 'dotenv/config';
import { PgVectorProvider } from '../src/providers/pgvector.provider.js';
import { readFileSync } from 'fs';

interface IngestPayload {
  project_root: string;
  documents: {
    path: string;
    content: string;
    meta: {
      component: string;
      category: string;
      tags: string[];
      timestamp: string;
    };
  }[];
  timestamp: string;
}

async function ingestFromHook() {
  const payloadFile = process.argv[2];

  if (!payloadFile) {
    console.error('Usage: ingest-from-hook.ts <payload.json>');
    process.exit(1);
  }

  const DATABASE_URL = process.env.DATABASE_URL_MEMORY;
  const REDIS_URL = process.env.REDIS_URL;

  if (!DATABASE_URL) {
    console.error('[ERROR] DATABASE_URL_MEMORY not set');
    process.exit(1);
  }

  try {
    // Read payload
    const payload: IngestPayload = JSON.parse(readFileSync(payloadFile, 'utf-8'));

    const provider = new PgVectorProvider(DATABASE_URL, REDIS_URL);

    let totalChunks = 0;

    for (const doc of payload.documents) {
      const result = await provider.ingest(
        payload.project_root,
        doc.path,
        doc.content,
        doc.meta
      );

      totalChunks += result.chunks;
    }

    await provider.close();

    console.log(`[SUCCESS] Ingested ${totalChunks} chunks from ${payload.documents.length} documents`);
    process.exit(0);

  } catch (error) {
    console.error(`[ERROR] Ingestion failed: ${error.message}`);
    process.exit(1);
  }
}

ingestFromHook();

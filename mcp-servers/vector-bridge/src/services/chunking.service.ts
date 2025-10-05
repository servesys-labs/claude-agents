/**
 * Chunking service - splits text into overlapping chunks for embedding
 */

export interface ChunkResult {
  chunks: string[];
  metadata: {
    total_chars: number;
    total_chunks: number;
    avg_chunk_size: number;
  };
}

export class ChunkingService {
  private readonly targetChunkSize: number;
  private readonly overlapSize: number;

  constructor(
    targetChunkSize: number = 600, // ~600 tokens = ~2400 chars
    overlapSize: number = 75 // ~75 tokens = ~300 chars
  ) {
    this.targetChunkSize = targetChunkSize;
    this.overlapSize = overlapSize;
  }

  /**
   * Normalize text before chunking
   * - Remove excessive whitespace
   * - Normalize line breaks
   * - Preserve code structure
   */
  private normalizeText(text: string): string {
    return text
      .replace(/\r\n/g, '\n') // Normalize line endings
      .replace(/\n{3,}/g, '\n\n') // Max 2 consecutive newlines
      .replace(/[ \t]+/g, ' ') // Collapse spaces
      .trim();
  }

  /**
   * Split text into sentences (rough heuristic)
   */
  private splitIntoSentences(text: string): string[] {
    // Split on sentence boundaries while preserving code blocks
    const sentences: string[] = [];
    const parts = text.split(/(?<=[.!?])\s+(?=[A-Z])/);

    for (const part of parts) {
      if (part.trim()) {
        sentences.push(part.trim());
      }
    }

    return sentences.length > 0 ? sentences : [text];
  }

  /**
   * Chunk text with sliding window and overlap
   */
  chunk(text: string): ChunkResult {
    const normalized = this.normalizeText(text);

    if (normalized.length === 0) {
      return {
        chunks: [],
        metadata: { total_chars: 0, total_chunks: 0, avg_chunk_size: 0 },
      };
    }

    // If text is shorter than target, return as single chunk
    if (normalized.length <= this.targetChunkSize) {
      return {
        chunks: [normalized],
        metadata: {
          total_chars: normalized.length,
          total_chunks: 1,
          avg_chunk_size: normalized.length,
        },
      };
    }

    const sentences = this.splitIntoSentences(normalized);
    const chunks: string[] = [];
    let currentChunk: string[] = [];
    let currentSize = 0;

    for (const sentence of sentences) {
      const sentenceSize = sentence.length;

      // If adding this sentence exceeds target, finalize current chunk
      if (currentSize + sentenceSize > this.targetChunkSize && currentChunk.length > 0) {
        chunks.push(currentChunk.join(' '));

        // Create overlap by keeping last few sentences
        const overlapSentences: string[] = [];
        let overlapSize = 0;

        for (let i = currentChunk.length - 1; i >= 0; i--) {
          const s = currentChunk[i];
          if (overlapSize + s.length <= this.overlapSize) {
            overlapSentences.unshift(s);
            overlapSize += s.length;
          } else {
            break;
          }
        }

        currentChunk = overlapSentences;
        currentSize = overlapSize;
      }

      currentChunk.push(sentence);
      currentSize += sentenceSize;
    }

    // Add final chunk
    if (currentChunk.length > 0) {
      chunks.push(currentChunk.join(' '));
    }

    const totalChars = chunks.reduce((sum, c) => sum + c.length, 0);
    const avgChunkSize = chunks.length > 0 ? Math.round(totalChars / chunks.length) : 0;

    return {
      chunks,
      metadata: {
        total_chars: normalized.length,
        total_chunks: chunks.length,
        avg_chunk_size: avgChunkSize,
      },
    };
  }

  /**
   * Estimate token count (rough: 1 token ≈ 4 chars)
   */
  estimateTokens(text: string): number {
    return Math.ceil(text.length / 4);
  }
}

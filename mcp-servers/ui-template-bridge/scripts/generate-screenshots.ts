#!/usr/bin/env npx tsx

/**
 * Generate screenshots for all templates
 * Creates visual references for AI agents to understand template appearance
 */

import { promises as fs } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { spawn } from 'child_process';
import { createHash } from 'crypto';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const TEMPLATES_DIR = process.env.TEMPLATES_DIR ||
  path.join(process.env.HOME!, 'vibe', 'ui-templates');

// Save screenshots in multiple locations for agent access
const SCREENSHOTS_DIR = path.join(__dirname, '../screenshots');
const VIBE_SCREENSHOTS_DIR = path.join(process.env.HOME!, 'vibe', 'ui-screenshots');
const TEMP_EXTRACT_DIR = path.join(__dirname, '../.temp-screenshots');

// Cache file locations (dual sync)
const CACHE_FILE_LOCAL = path.join(SCREENSHOTS_DIR, '.screenshot-cache.json');
const CACHE_FILE_VIBE = path.join(VIBE_SCREENSHOTS_DIR, '.screenshot-cache.json');

interface ScreenshotTask {
  templateId: string;
  extractPath: string;
  framework: 'next.js' | 'react-native';
  screenshots: Array<{
    name: string;
    route: string;
    description: string;
  }>;
}

interface CacheEntry {
  templateId: string;
  page: string;
  viewport: 'desktop' | 'mobile';
  filename: string;
  sha256: string;
  capturedAt: string;
  fileSize: number;
}

interface CacheManifest {
  version: string;
  lastUpdated: string;
  screenshots: Record<string, CacheEntry>;
}

interface ScreenshotStats {
  captured: number;
  skipped: number;
  total: number;
}

/**
 * Wait for dev server to be ready
 */
async function waitForServer(url: string, maxAttempts = 30): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        console.log(`  ✅ Server ready at ${url}`);
        return true;
      }
    } catch {
      // Server not ready yet
    }
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  return false;
}

/**
 * Load cache manifest from disk
 */
async function loadCache(): Promise<CacheManifest> {
  try {
    // Try local cache first
    const content = await fs.readFile(CACHE_FILE_LOCAL, 'utf-8');
    const cache = JSON.parse(content) as CacheManifest;

    // Validate version
    if (cache.version !== '1.0.0') {
      console.log('  ⚠️  Cache version mismatch, recreating cache');
      return createEmptyCache();
    }

    return cache;
  } catch (error: any) {
    // Cache doesn't exist or is corrupt
    if (error.code !== 'ENOENT') {
      console.log('  ⚠️  Cache file corrupt, recreating cache');
    }
    return createEmptyCache();
  }
}

/**
 * Create empty cache manifest
 */
function createEmptyCache(): CacheManifest {
  return {
    version: '1.0.0',
    lastUpdated: new Date().toISOString(),
    screenshots: {},
  };
}

/**
 * Save cache manifest to disk (both locations)
 */
async function saveCache(cache: CacheManifest): Promise<void> {
  cache.lastUpdated = new Date().toISOString();
  const content = JSON.stringify(cache, null, 2);

  // Save to both locations
  await fs.writeFile(CACHE_FILE_LOCAL, content, 'utf-8');
  await fs.writeFile(CACHE_FILE_VIBE, content, 'utf-8');
}

/**
 * Compute SHA256 hash of file
 */
async function computeFileHash(filePath: string): Promise<string> {
  const buffer = await fs.readFile(filePath);
  return createHash('sha256').update(buffer).digest('hex');
}

/**
 * Generate cache key for a screenshot
 */
function getCacheKey(templateId: string, page: string, viewport: 'desktop' | 'mobile'): string {
  return `${templateId}-${page}-${viewport}`;
}

/**
 * Check if screenshot should be skipped (cached and valid)
 */
async function shouldSkipScreenshot(
  cacheKey: string,
  filePath: string,
  cache: CacheManifest,
  force: boolean
): Promise<boolean> {
  // Never skip if force flag is set
  if (force) {
    return false;
  }

  // Check if cache entry exists
  const entry = cache.screenshots[cacheKey];
  if (!entry) {
    return false;
  }

  // Check if file exists on disk
  try {
    await fs.access(filePath);
  } catch {
    console.log(`  ⚠️  Cached file missing: ${path.basename(filePath)}`);
    return false;
  }

  // Verify file hash matches
  try {
    const currentHash = await computeFileHash(filePath);
    if (currentHash !== entry.sha256) {
      console.log(`  ⚠️  File modified: ${path.basename(filePath)}`);
      return false;
    }
  } catch (error) {
    console.log(`  ⚠️  Hash verification failed: ${path.basename(filePath)}`);
    return false;
  }

  // File is cached and valid
  return true;
}

/**
 * Update cache with newly captured screenshot
 */
async function updateCache(
  cache: CacheManifest,
  cacheKey: string,
  templateId: string,
  page: string,
  viewport: 'desktop' | 'mobile',
  filePath: string
): Promise<void> {
  const stats = await fs.stat(filePath);
  const hash = await computeFileHash(filePath);

  cache.screenshots[cacheKey] = {
    templateId,
    page,
    viewport,
    filename: path.basename(filePath),
    sha256: hash,
    capturedAt: new Date().toISOString(),
    fileSize: stats.size,
  };
}

/**
 * Start Next.js dev server
 */
async function startNextDevServer(projectPath: string): Promise<{
  process: any;
  url: string;
  port: number;
}> {
  let lastErr: any = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    const port = 3000 + Math.floor(Math.random() * 1000); // Random port to avoid conflicts

    console.log(`  Starting Next.js dev server on port ${port} (attempt ${attempt + 1})...`);

    const devProcess = spawn('npm', ['run', 'dev', '--', '-p', port.toString()], {
      cwd: projectPath,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, PORT: port.toString(), NEXT_TELEMETRY_DISABLED: '1' },
    });

    devProcess.stdout?.on('data', (data) => {
      const output = data.toString();
      if (output.toLowerCase().includes('ready') || output.includes('started server')) {
        console.log('  📡 Dev server output:', output.trim());
      }
    });

    devProcess.stderr?.on('data', (data) => {
      const output = data.toString();
      if (!output.toLowerCase().includes('warn')) {
        console.error('  ⚠️ Dev server error:', output.trim());
      }
    });

    const url = `http://localhost:${port}`;

    // Wait for server to be ready
    const ready = await waitForServer(url, 60); // 60 seconds max

    if (!ready) {
      try { devProcess.kill(); } catch {}
      lastErr = new Error('Dev server failed to start');
      continue;
    }

    return { process: devProcess, url, port };
  }
  throw lastErr ?? new Error('Dev server failed to start');
}

/**
 * Start Expo web dev server
 */
async function startExpoWebServer(projectPath: string): Promise<{
  process: any;
  url: string;
  port: number;
}> {
  let lastErr: any = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    const port = 19006 + Math.floor(Math.random() * 100); // Expo default is 19006

    console.log(`  Starting Expo web server on port ${port} (attempt ${attempt + 1})...`);

    const devProcess = spawn('npx', ['expo', 'start', '--web', '--port', port.toString()], {
      cwd: projectPath,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, PORT: port.toString(), EXPO_NO_TELEMETRY: '1' },
    });

    devProcess.stdout?.on('data', (data) => {
      const output = data.toString();
      if (output.toLowerCase().includes('expo') || output.includes('localhost')) {
        console.log('  📡 Expo server output:', output.trim());
      }
    });

    devProcess.stderr?.on('data', (data) => {
      const output = data.toString();
      if (!output.toLowerCase().includes('warn')) {
        console.error('  ⚠️ Expo server error:', output.trim());
      }
    });

    const url = `http://localhost:${port}`;

    // Wait for server to be ready (Expo can take longer to start)
    const ready = await waitForServer(url, 90); // 90 seconds max for Expo

    if (!ready) {
      try { devProcess.kill(); } catch {}
      lastErr = new Error('Expo web server failed to start');
      continue;
    }

    return { process: devProcess, url, port };
  }
  throw lastErr ?? new Error('Expo web server failed to start');
}

/**
 * Capture desktop and mobile screenshots with a single navigation.
 * Avoids relaunching browser and reloading route twice.
 */
async function captureDesktopAndMobile(
  url: string,
  desktopPath: string,
  mobilePath: string,
  enableWebP: boolean,
  cache: CacheManifest,
  stats: ScreenshotStats,
  templateId: string,
  pageName: string,
  force: boolean,
  desktopViewport = { width: 1280, height: 800 },
  mobileViewport = { width: 375, height: 667 }
): Promise<void> {
  // Check cache for desktop
  const desktopCacheKey = getCacheKey(templateId, pageName, 'desktop');
  const skipDesktop = await shouldSkipScreenshot(desktopCacheKey, desktopPath, cache, force);

  // Check cache for mobile
  const mobileCacheKey = getCacheKey(templateId, pageName, 'mobile');
  const skipMobile = await shouldSkipScreenshot(mobileCacheKey, mobilePath, cache, force);

  // If both are cached and valid, skip entirely
  if (skipDesktop && skipMobile) {
    console.log(`  ✅ Cached (skipped): ${path.basename(desktopPath)}`);
    console.log(`  ✅ Cached (skipped): ${path.basename(mobilePath)}`);
    stats.skipped += 2;
    stats.total += 2;
    return;
  }

  const browser = await ensureBrowser();

  // Desktop context (standard DPI)
  if (!skipDesktop) {
    const desktopContext = await browser.newContext({
      viewport: desktopViewport,
      deviceScaleFactor: 1,
    });

    const desktopPage = await desktopContext.newPage();

    try {
      // Block external network; allow localhost only
      try {
        const allowedHosts = new Set<string>(['localhost', '127.0.0.1']);
        await desktopPage.route('**/*', (route) => {
          try {
            const raw = route.request().url();
            if (raw.startsWith('data:') || raw.startsWith('blob:') || raw.startsWith('file:')) {
              return route.continue();
            }
            const u = new URL(raw);
            if (allowedHosts.has(u.hostname)) return route.continue();
            return route.abort();
          } catch {
            // If URL cannot be parsed, play safe and allow it (avoid breaking inline resources)
            return route.continue();
          }
        });
      } catch {}

      // Navigate with improved wait conditions
      let waitStrategy = 'domcontentloaded';
      try {
        await desktopPage.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
        console.log('  ⏳ Waiting for main content...');

        // Try to wait for hero element or main content
        await desktopPage.waitForSelector('h1, [data-hero], main', { timeout: 5000 });
        waitStrategy = 'selector-based (h1/hero/main)';

        // Small delay for animations to settle
        await desktopPage.waitForTimeout(500);
      } catch {
        // Fallback: hero not found, use domcontentloaded + fixed delay
        waitStrategy = 'domcontentloaded + delay';
        await desktopPage.waitForTimeout(500);
      }

      console.log(`  🎯 Wait strategy: ${waitStrategy}`);

      // Force light mode to prevent dark background
      await desktopPage.emulateMedia({ colorScheme: 'light' });

      // Scroll to bottom to trigger lazy loading, then back to top
      await desktopPage.evaluate(() => {
        window.scrollTo(0, document.body.scrollHeight);
      });
      await desktopPage.waitForTimeout(1000);
      await desktopPage.evaluate(() => {
        window.scrollTo(0, 0);
      });
      await desktopPage.waitForTimeout(500);

      // Log page dimensions for debugging
      const dimensions = await desktopPage.evaluate(() => ({
        bodyHeight: document.body.scrollHeight,
        documentHeight: document.documentElement.scrollHeight,
        viewportHeight: window.innerHeight,
        hasContent: document.querySelector('main')?.scrollHeight || 0
      }));
      console.log(`  📏 Desktop page dimensions:`, dimensions);

      // Capture desktop screenshot
      await desktopPage.screenshot({ path: desktopPath, fullPage: true });
      console.log(`  🖥️  Desktop screenshot saved: ${path.basename(desktopPath)}`);
      await copyToVibe(desktopPath);
      await updateCache(cache, desktopCacheKey, templateId, pageName, 'desktop', desktopPath);
      stats.captured++;

      // Capture desktop WebP if enabled
      if (enableWebP) {
        const desktopWebpPath = desktopPath.replace('.png', '.webp');
        await desktopPage.screenshot({ path: desktopWebpPath, fullPage: true });
        console.log(`  🖼️  Desktop WebP saved: ${path.basename(desktopWebpPath)}`);
        await copyToVibe(desktopWebpPath);
      }
    } finally {
      await desktopPage.close();
      await desktopContext.close();
    }
    stats.total++;
  } else {
    console.log(`  ✅ Cached (skipped): ${path.basename(desktopPath)}`);
    stats.skipped++;
    stats.total++;
  }

  // Mobile context (retina display with 2x pixel density)
  if (!skipMobile) {
    const mobileContext = await browser.newContext({
      viewport: mobileViewport,
      deviceScaleFactor: 2, // High DPI for mobile (retina display)
    });

    const mobilePage = await mobileContext.newPage();

    try {
      // Block external network; allow localhost only
      try {
        const allowedHosts = new Set<string>(['localhost', '127.0.0.1']);
        await mobilePage.route('**/*', (route) => {
          try {
            const raw = route.request().url();
            if (raw.startsWith('data:') || raw.startsWith('blob:') || raw.startsWith('file:')) {
              return route.continue();
            }
            const u = new URL(raw);
            if (allowedHosts.has(u.hostname)) return route.continue();
            return route.abort();
          } catch {
            return route.continue();
          }
        });
      } catch {}

      // Navigate with improved wait conditions
      try {
        await mobilePage.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
        console.log('  ⏳ Waiting for mobile content...');

        // Try to wait for hero element or main content
        await mobilePage.waitForSelector('h1, [data-hero], main', { timeout: 5000 });

        // Small delay for animations to settle
        await mobilePage.waitForTimeout(500);
      } catch {
        await mobilePage.waitForTimeout(500);
      }

      // Force light mode to prevent dark background
      await mobilePage.emulateMedia({ colorScheme: 'light' });

      // Scroll to bottom to trigger lazy loading, then back to top
      await mobilePage.evaluate(() => {
        window.scrollTo(0, document.body.scrollHeight);
      });
      await mobilePage.waitForTimeout(1000);
      await mobilePage.evaluate(() => {
        window.scrollTo(0, 0);
      });
      await mobilePage.waitForTimeout(500);

      // Log page dimensions for debugging
      const dimensions = await mobilePage.evaluate(() => ({
        bodyHeight: document.body.scrollHeight,
        documentHeight: document.documentElement.scrollHeight,
        viewportHeight: window.innerHeight,
        hasContent: document.querySelector('main')?.scrollHeight || 0
      }));
      console.log(`  📏 Mobile page dimensions:`, dimensions);

      // Capture mobile screenshot
      await mobilePage.screenshot({ path: mobilePath, fullPage: true });
      console.log(`  📱 Mobile screenshot saved: ${path.basename(mobilePath)}`);
      await copyToVibe(mobilePath);
      await updateCache(cache, mobileCacheKey, templateId, pageName, 'mobile', mobilePath);
      stats.captured++;

      // Capture mobile WebP if enabled
      if (enableWebP) {
        const mobileWebpPath = mobilePath.replace('.png', '.webp');
        await mobilePage.screenshot({ path: mobileWebpPath, fullPage: true });
        console.log(`  🖼️  Mobile WebP saved: ${path.basename(mobileWebpPath)}`);
        await copyToVibe(mobileWebpPath);
      }
    } finally {
      await mobilePage.close();
      await mobileContext.close();
    }
    stats.total++;
  } else {
    console.log(`  ✅ Cached (skipped): ${path.basename(mobilePath)}`);
    stats.skipped++;
    stats.total++;
  }
}

async function copyToVibe(localPath: string) {
  const vibeOutputPath = path.join(VIBE_SCREENSHOTS_DIR, path.basename(localPath));
  await fs.copyFile(localPath, vibeOutputPath);
  console.log(`  💾 Copied to: ${vibeOutputPath}`);
}

/**
 * Install dependencies for template
 */
async function installDependencies(projectPath: string): Promise<boolean> {
  console.log('  📦 Installing dependencies...');
  const { cmd, args } = await detectPackageManager(projectPath);

  // First attempt: standard install
  const firstAttempt = await attemptInstall(cmd, args, projectPath);
  if (firstAttempt) {
    console.log('  ✅ Dependencies installed');
    return true;
  }

  // Second attempt: retry with --legacy-peer-deps for npm (handles React 19 peer dependency issues)
  if (cmd === 'npm') {
    console.log('  ⚠️  Retrying with --legacy-peer-deps...');
    const legacyArgs = [...args, '--legacy-peer-deps'];
    const secondAttempt = await attemptInstall(cmd, legacyArgs, projectPath);
    if (secondAttempt) {
      console.log('  ✅ Dependencies installed (with --legacy-peer-deps)');
      return true;
    }
  }

  console.error('  ❌ Failed to install dependencies');
  return false;
}

async function attemptInstall(cmd: string, args: string[], projectPath: string): Promise<boolean> {
  return new Promise((resolve) => {
    const install = spawn(cmd, args, {
      cwd: projectPath,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    const timer = setTimeout(() => {
      try { install.kill(); } catch {}
      resolve(false);
    }, 300000);

    install.on('close', (code) => {
      clearTimeout(timer);
      resolve(code === 0);
    });
  });
}

/**
 * Extract template for screenshot capture
 */
async function extractTemplate(
  templateId: string,
  zipPath: string
): Promise<string> {
  const { extractZipSafely } = await import('../dist/services/zip-extractor.js');

  const extractPath = path.join(TEMP_EXTRACT_DIR, templateId);

  console.log(`\n📦 Extracting ${templateId}...`);

  // Clean existing
  try {
    await fs.rm(extractPath, { recursive: true, force: true });
  } catch {}

  const buffer = await fs.readFile(zipPath);
  const result = await extractZipSafely(buffer, {
    destDir: extractPath,
    overwrite: true,
  });

  if (!result.success) {
    throw new Error(`Extraction failed: ${result.errors.join(', ')}`);
  }

  console.log(`  ✅ Extracted ${result.filesExtracted.length} files`);

  // Find the actual project directory (GitHub ZIPs extract to subdirectory with commit hash)
  const entries = await fs.readdir(extractPath, { withFileTypes: true });
  const subdirs = entries.filter(e => e.isDirectory());

  // Look for directory containing package.json
  for (const subdir of subdirs) {
    const subdirPath = path.join(extractPath, subdir.name);
    const packageJsonPath = path.join(subdirPath, 'package.json');

    try {
      await fs.access(packageJsonPath);
      console.log(`  📁 Found project in subdirectory: ${subdir.name}`);
      return subdirPath; // Return the actual project directory
    } catch {
      // Keep looking
    }
  }

  // Fallback: return extractPath if package.json is at root
  return extractPath;
}

/**
 * Generate screenshots for a template
 */
async function generateScreenshotsForTemplate(
  task: ScreenshotTask,
  enableWebP: boolean,
  cache: CacheManifest,
  stats: ScreenshotStats,
  force: boolean
): Promise<void> {
  console.log(`\n🎨 Generating screenshots for ${task.templateId}`);

  // Install dependencies
  const installed = await installDependencies(task.extractPath);
  if (!installed) {
    console.error(`  ❌ Skipping ${task.templateId} - dependency installation failed`);
    return;
  }

  // Start dev server (Next.js or Expo Web)
  let server: { process: any; url: string } | null = null;

  try {
    if (task.framework === 'react-native') {
      console.log('  📱 Starting Expo Web server...');
      server = await startExpoWebServer(task.extractPath);
    } else {
      server = await startNextDevServer(task.extractPath);
    }

    // Take screenshots
    for (const screenshot of task.screenshots) {
      const url = `${server.url}${screenshot.route}`;
      const desktopFilename = `${task.templateId}-${screenshot.name}.png`;
      const desktopOutputPath = path.join(SCREENSHOTS_DIR, desktopFilename);
      const mobileFilename = `${task.templateId}-${screenshot.name}-mobile.png`;
      const mobileOutputPath = path.join(SCREENSHOTS_DIR, mobileFilename);

      console.log(`\n  📸 ${force ? 'Capturing (forced)' : 'Checking'}: ${screenshot.name}`);
      console.log(`     URL: ${url}`);
      console.log(`     Description: ${screenshot.description}`);

      try {
        await captureDesktopAndMobile(
          url,
          desktopOutputPath,
          mobileOutputPath,
          enableWebP,
          cache,
          stats,
          task.templateId,
          screenshot.name,
          force
        );
      } catch (error: any) {
        console.error(`  ❌ Screenshot failed: ${error.message}`);
      }
    }

  } finally {
    // Kill dev server
    if (server) {
      console.log('  🛑 Stopping dev server...');
      server.process.kill();

      // Wait for process to die
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }
}

/**
 * Parse CLI arguments
 */
function parseCLIArgs() {
  const args = process.argv.slice(2);
  const flags: {
    help: boolean;
    testOne: boolean;
    template?: string;
    route?: string;
    webp: boolean;
    force: boolean;
    clean: boolean;
  } = {
    help: false,
    testOne: false,
    webp: false,
    force: false,
    clean: false,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (arg === '--help' || arg === '-h') {
      flags.help = true;
    } else if (arg === '--test-one') {
      flags.testOne = true;
    } else if (arg === '--webp') {
      flags.webp = true;
    } else if (arg === '--force') {
      flags.force = true;
    } else if (arg === '--clean') {
      flags.clean = true;
    } else if (arg === '--template' && i + 1 < args.length) {
      flags.template = args[++i];
    } else if (arg === '--route' && i + 1 < args.length) {
      flags.route = args[++i];
    }
  }

  return flags;
}

/**
 * Show help text
 */
function showHelp() {
  console.log(`
🎬 Screenshot Generation Script

USAGE:
  npx tsx scripts/generate-screenshots.ts [OPTIONS]

OPTIONS:
  --help, -h              Show this help message
  --test-one              Process only the first template (for testing)
  --template <id>         Process only the specified template ID
                          Example: --template dillionverma-portfolio
  --route <path>          Capture only the specified route
                          Example: --route /blog
  --webp                  Generate WebP versions alongside PNG (smaller file size)
  --force                 Regenerate all screenshots (ignore cache)
  --clean                 Delete all screenshots and cache before generating

CACHING:
  Screenshots are cached to avoid redundant generation. The script will:
  - Skip screenshots that already exist and haven't changed
  - Verify file integrity using SHA256 hashes
  - Automatically recapture if files are missing or modified
  - Cache location: ${CACHE_FILE_LOCAL}

EXAMPLES:
  # Generate all screenshots (uses cache)
  npx tsx scripts/generate-screenshots.ts

  # Test with first template only
  npx tsx scripts/generate-screenshots.ts --test-one

  # Force regenerate all (ignore cache)
  npx tsx scripts/generate-screenshots.ts --force

  # Clean and regenerate from scratch
  npx tsx scripts/generate-screenshots.ts --clean

  # Generate screenshots for specific template
  npx tsx scripts/generate-screenshots.ts --template dillionverma-portfolio

  # Generate screenshots for specific route only
  npx tsx scripts/generate-screenshots.ts --route /

  # Generate WebP versions for faster loading
  npx tsx scripts/generate-screenshots.ts --test-one --webp

  # Combine filters
  npx tsx scripts/generate-screenshots.ts --template dillionverma-portfolio --route /blog --force

SCREENSHOT LOCATIONS:
  1. ${SCREENSHOTS_DIR}
  2. ${VIBE_SCREENSHOTS_DIR} (permanent storage)
  3. Cache: ${CACHE_FILE_LOCAL}
`);
  process.exit(0);
}

/**
 * Main function
 */
async function main() {
  // Parse CLI arguments
  const flags = parseCLIArgs();

  if (flags.help) {
    showHelp();
  }

  console.log('🎬 Screenshot Generation Script\n');
  console.log('This will extract templates, start dev servers, and capture screenshots');
  console.log('Expected time: ~5-10 minutes per Next.js template\n');

  // Ensure directories
  await fs.mkdir(SCREENSHOTS_DIR, { recursive: true });
  await fs.mkdir(VIBE_SCREENSHOTS_DIR, { recursive: true });
  await fs.mkdir(TEMP_EXTRACT_DIR, { recursive: true });

  // Handle --clean flag: delete all screenshots and cache
  if (flags.clean) {
    console.log('🧹 Clean mode: Deleting all screenshots and cache...');
    try {
      // Delete all PNG and WebP files
      const files = await fs.readdir(SCREENSHOTS_DIR);
      const mediaFiles = files.filter(f => f.endsWith('.png') || f.endsWith('.webp'));
      for (const file of mediaFiles) {
        await fs.unlink(path.join(SCREENSHOTS_DIR, file));
        const vibeFile = path.join(VIBE_SCREENSHOTS_DIR, file);
        try {
          await fs.unlink(vibeFile);
        } catch {}
      }
      // Delete cache files
      try {
        await fs.unlink(CACHE_FILE_LOCAL);
      } catch {}
      try {
        await fs.unlink(CACHE_FILE_VIBE);
      } catch {}
      console.log(`  ✅ Deleted ${mediaFiles.length} screenshots and cache\n`);
    } catch (error: any) {
      console.error(`  ⚠️  Clean failed: ${error.message}\n`);
    }
  }

  console.log('📁 Screenshot locations:');
  console.log(`   1. ${SCREENSHOTS_DIR}`);
  console.log(`   2. ${VIBE_SCREENSHOTS_DIR} (permanent storage)`);
  console.log(`   3. Cache: ${CACHE_FILE_LOCAL}`);
  console.log();

  // Load cache
  const cache = await loadCache();
  const cachedCount = Object.keys(cache.screenshots).length;
  if (cachedCount > 0) {
    console.log(`💾 Loaded cache: ${cachedCount} screenshots`);
    if (flags.force) {
      console.log('   ⚠️  Force mode: Cache will be ignored\n');
    } else {
      console.log('   ✅ Cache enabled: Will skip unchanged screenshots\n');
    }
  } else {
    console.log('💾 No cache found, will capture all screenshots\n');
  }

  // Show active filters
  if (flags.template || flags.route || flags.testOne || flags.webp || flags.force || flags.clean) {
    console.log('🔍 Active options:');
    if (flags.testOne) console.log('   - Test mode: First template only');
    if (flags.template) console.log(`   - Template: ${flags.template}`);
    if (flags.route) console.log(`   - Route: ${flags.route}`);
    if (flags.webp) console.log('   - WebP: Enabled');
    if (flags.force) console.log('   - Force: Regenerate all');
    if (flags.clean) console.log('   - Clean: Deleted existing screenshots');
    console.log();
  }

  // Initialize statistics
  const stats: ScreenshotStats = {
    captured: 0,
    skipped: 0,
    total: 0,
  };

  // Load manifest
  const manifestPath = path.join(TEMPLATES_DIR, 'index.json');
  const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf-8'));

  // Define screenshot tasks (Next.js templates only)
  const tasks: ScreenshotTask[] = [
    {
      templateId: 'dillionverma-portfolio',
      extractPath: '',
      framework: 'next.js',
      screenshots: [
        { name: 'home', route: '/', description: 'Portfolio homepage with hero, experience, projects' },
        { name: 'blog', route: '/blog', description: 'Blog listing page' },
      ],
    },
    {
      templateId: 'dillionverma-startup-template',
      extractPath: '',
      framework: 'next.js',
      screenshots: [
        { name: 'home', route: '/', description: 'Startup landing page with hero, features, pricing' },
        { name: 'login', route: '/login', description: 'Authentication page' },
      ],
    },
    {
      templateId: 'magicuidesign-agent-template',
      extractPath: '',
      framework: 'next.js',
      screenshots: [
        { name: 'home', route: '/', description: 'Agent template with hero, bento grid, features' },
      ],
    },
    {
      templateId: 'magicuidesign-devtool-template',
      extractPath: '',
      framework: 'next.js',
      screenshots: [
        { name: 'home', route: '/', description: 'Dev tool landing page' },
        { name: 'blog', route: '/blog', description: 'Blog section' },
      ],
    },
    {
      templateId: 'magicuidesign-saas-template',
      extractPath: '',
      framework: 'next.js',
      screenshots: [
        { name: 'home', route: '/', description: 'SaaS landing page with features, pricing, testimonials' },
      ],
    },
    {
      templateId: 'magicuidesign-mobile-template',
      extractPath: '',
      framework: 'next.js',
      screenshots: [
        { name: 'home', route: '/', description: 'Mobile-first Next.js template with bottom drawer navigation' },
      ],
    },
  ];

  // Filter tasks to only those with templates in manifest
  let availableTasks = tasks.filter(task =>
    manifest.templates[task.templateId]
  );

  // Apply template filter if specified
  if (flags.template) {
    availableTasks = availableTasks.filter(task => task.templateId === flags.template);

    if (availableTasks.length === 0) {
      console.error(`❌ Template '${flags.template}' not found`);
      console.log('\nAvailable templates:');
      tasks.forEach(t => console.log(`   - ${t.templateId}`));
      process.exit(1);
    }
  }

  // Apply route filter if specified
  if (flags.route) {
    availableTasks = availableTasks.map(task => ({
      ...task,
      screenshots: task.screenshots.filter(s => s.route === flags.route),
    })).filter(task => task.screenshots.length > 0);

    if (availableTasks.length === 0) {
      console.error(`❌ Route '${flags.route}' not found in any template`);
      process.exit(1);
    }
  }

  // Apply test-one filter (after other filters to allow combining)
  if (flags.testOne) {
    availableTasks = availableTasks.slice(0, 1);
    console.log(`🧪 TEST MODE: Processing ONE template only\n`);
  }

  const nextjsCount = availableTasks.filter(t => t.framework === 'next.js').length;
  const reactNativeCount = availableTasks.filter(t => t.framework === 'react-native').length;

  console.log(`Found ${availableTasks.length} templates to screenshot:`);
  if (nextjsCount > 0) console.log(`   - ${nextjsCount} Next.js (web)`);
  if (reactNativeCount > 0) console.log(`   - ${reactNativeCount} React Native (Expo Web preview)\n`);
  console.log();

  // Process each template
  for (const task of availableTasks) {
    const templateData = manifest.templates[task.templateId];

    try {
      // Extract template
      task.extractPath = await extractTemplate(task.templateId, templateData.localPath);

      // Generate screenshots
      await generateScreenshotsForTemplate(task, flags.webp, cache, stats, flags.force);

      console.log(`\n✅ Completed ${task.templateId}`);

    } catch (error: any) {
      console.error(`\n❌ Failed to process ${task.templateId}:`, error.message);
    }
  }

  // Save cache
  console.log('\n💾 Saving cache...');
  await saveCache(cache);
  console.log('  ✅ Cache saved');

  // Show summary
  console.log('\n📊 Summary:');
  console.log(`   Captured: ${stats.captured}`);
  console.log(`   Skipped: ${stats.skipped}`);
  console.log(`   Total: ${stats.total}`);

  // Cleanup temp directory
  console.log('\n🧹 Cleaning up...');
  await fs.rm(TEMP_EXTRACT_DIR, { recursive: true, force: true });

  // Generate index file with all screenshots
  console.log('\n📝 Generating screenshot index...');
  await generateScreenshotIndex(flags.webp, tasks);

  console.log('\n✅ Screenshot generation complete!');
  console.log(`   Screenshots saved to: ${SCREENSHOTS_DIR}`);
  console.log(`   Cache saved to: ${CACHE_FILE_LOCAL}`);
}

/**
 * Generate index file listing all screenshots with descriptions
 */
async function generateScreenshotIndex(includeWebP: boolean, tasks: ScreenshotTask[]) {
  const files = await fs.readdir(SCREENSHOTS_DIR);
  const screenshots = files.filter(f => f.endsWith('.png'));
  const webpFiles = includeWebP ? files.filter(f => f.endsWith('.webp')) : [];

  // Create JSON catalog for programmatic access
  const catalog: Record<string, any> = {
    generated: new Date().toISOString(),
    total: screenshots.length,
    totalWebP: webpFiles.length,
    locations: {
      primary: SCREENSHOTS_DIR,
      permanent: VIBE_SCREENSHOTS_DIR,
    },
    templates: {},
  };

  // Group by template
  const grouped = new Map<string, string[]>();
  for (const screenshot of screenshots) {
    const parts = screenshot.replace('.png', '').split('-');
    const isMobile = screenshot.includes('-mobile');

    // Extract template ID (everything before -home/-blog/-login/-mobile)
    let templateId = '';
    let pageName = '';

    for (let i = parts.length - 1; i >= 0; i--) {
      if (['home', 'blog', 'login', 'mobile'].includes(parts[i])) {
        if (parts[i] === 'mobile') continue;
        pageName = parts[i];
        templateId = parts.slice(0, i).join('-');
        break;
      }
    }

    if (!templateId) {
      templateId = parts.slice(0, -1).join('-');
      pageName = parts[parts.length - 1];
    }

    if (!grouped.has(templateId)) {
      grouped.set(templateId, []);

      // Find matching task to get framework type
      const matchingTask = tasks.find(t => t.templateId === templateId);
      const framework = matchingTask?.framework || 'next.js';

      catalog.templates[templateId] = {
        framework,
        isWeb: framework === 'next.js',
        isMobile: framework === 'react-native',
        note: framework === 'react-native'
          ? 'Expo Web preview - NOT native iOS/Android rendering'
          : 'Next.js web application',
        screenshots: [],
      };
    }
    grouped.get(templateId)!.push(screenshot);

    // Check for corresponding WebP file
    const webpFilename = screenshot.replace('.png', '.webp');
    const hasWebP = includeWebP && webpFiles.includes(webpFilename);

    // Find matching task definition to get description
    const matchingTask = tasks.find(t => t.templateId === templateId);
    const matchingScreenshot = matchingTask?.screenshots.find(s => s.name === pageName);

    // Add to catalog
    const entry: any = {
      filename: screenshot,
      page: pageName,
      viewport: isMobile ? 'mobile' : 'desktop',
      dimensions: isMobile ? '375x667' : '1280x800',
      description: matchingScreenshot?.description || '', // Include description from task definition
      path: path.join(SCREENSHOTS_DIR, screenshot),
      permanentPath: path.join(VIBE_SCREENSHOTS_DIR, screenshot),
    };

    if (hasWebP) {
      entry.webpFilename = webpFilename;
      entry.webpPath = path.join(SCREENSHOTS_DIR, webpFilename);
      entry.webpPermanentPath = path.join(VIBE_SCREENSHOTS_DIR, webpFilename);
    }

    catalog.templates[templateId].screenshots.push(entry);
  }

  // Write JSON catalog
  await fs.writeFile(
    path.join(SCREENSHOTS_DIR, 'catalog.json'),
    JSON.stringify(catalog, null, 2)
  );

  // Also write to vibe directory
  await fs.writeFile(
    path.join(VIBE_SCREENSHOTS_DIR, 'catalog.json'),
    JSON.stringify(catalog, null, 2)
  );

  console.log('  ✅ Screenshot catalog created (catalog.json)');

  // Create markdown index
  let indexContent = '# Template Screenshots\n\n';
  indexContent += 'Visual references for AI agents working with these templates.\n\n';
  indexContent += `**Generated**: ${new Date().toISOString()}\n\n`;
  indexContent += `**Total screenshots**: ${screenshots.length}\n\n`;
  indexContent += '## Screenshot Locations\n\n';
  indexContent += `1. **Project**: \`${SCREENSHOTS_DIR}\`\n`;
  indexContent += `2. **Permanent**: \`${VIBE_SCREENSHOTS_DIR}\`\n`;
  indexContent += `3. **Catalog**: \`catalog.json\` (programmatic access)\n\n`;
  indexContent += '---\n\n';

  for (const [templateId, images] of grouped.entries()) {
    indexContent += `## ${templateId}\n\n`;

    const templateScreenshots = catalog.templates[templateId].screenshots;

    for (const screenshot of templateScreenshots.sort((a: any, b: any) =>
      a.filename.localeCompare(b.filename)
    )) {
      const viewport = screenshot.viewport === 'mobile' ? '📱 Mobile' : '🖥️ Desktop';
      indexContent += `### ${screenshot.page} - ${viewport} (${screenshot.dimensions})\n\n`;
      indexContent += `**File**: \`${screenshot.filename}\`\n\n`;
      indexContent += `**Paths**:\n`;
      indexContent += `- Project: \`${screenshot.path}\`\n`;
      indexContent += `- Permanent: \`${screenshot.permanentPath}\`\n\n`;
      indexContent += `![${screenshot.filename}](${screenshot.filename})\n\n`;
      indexContent += '---\n\n';
    }
  }

  // Usage instructions
  indexContent += '## For AI Agents\n\n';
  indexContent += 'To reference screenshots when working with templates:\n\n';
  indexContent += '```typescript\n';
  indexContent += '// Load catalog\n';
  indexContent += `const catalog = JSON.parse(await fs.readFile('${VIBE_SCREENSHOTS_DIR}/catalog.json', 'utf-8'));\n\n`;
  indexContent += '// Get screenshots for a template\n';
  indexContent += `const screenshots = catalog.templates['dillionverma-portfolio'].screenshots;\n\n`;
  indexContent += '// Access desktop home screenshot\n';
  indexContent += `const desktopHome = screenshots.find(s => s.page === 'home' && s.viewport === 'desktop');\n`;
  indexContent += `console.log(desktopHome.permanentPath);\n`;
  indexContent += '```\n\n';

  await fs.writeFile(
    path.join(SCREENSHOTS_DIR, 'INDEX.md'),
    indexContent
  );

  await fs.writeFile(
    path.join(VIBE_SCREENSHOTS_DIR, 'INDEX.md'),
    indexContent
  );

  console.log('  ✅ Screenshot index created (INDEX.md)');
}

main().catch((error) => {
  console.error('💥 Fatal error:', error);
  process.exit(1);
});

// Singleton Playwright browser + helpers
let browserSingleton: any | null = null;
async function ensureBrowser() {
  if (browserSingleton) return browserSingleton;
  const { chromium } = await import('playwright');
  browserSingleton = await chromium.launch({ headless: true });
  const shutdown = async () => {
    try { await browserSingleton?.close(); } catch {}
    browserSingleton = null;
  };
  process.on('exit', () => { void shutdown(); });
  process.on('SIGINT', async () => { await shutdown(); process.exit(1); });
  process.on('SIGTERM', async () => { await shutdown(); process.exit(1); });
  return browserSingleton;
}

async function detectPackageManager(projectPath: string): Promise<{cmd: string; args: string[]}> {
  const join = (...p: string[]) => path.join(projectPath, ...p);
  const exists = async (p: string) => !!(await fs.stat(p).catch(() => null));

  // Check for lockfiles but fall back to npm if manager not installed
  if (await exists(join('pnpm-lock.yaml'))) {
    const ok = await new Promise<boolean>((resolve) => {
      const p = spawn('pnpm', ['--version'], { stdio: 'ignore' });
      p.on('error', () => resolve(false));
      p.on('close', (code) => resolve(code === 0));
    });
    if (ok) return { cmd: 'pnpm', args: ['install', '--frozen-lockfile'] };
    console.log('  ⚠️  pnpm not found, falling back to npm');
    return { cmd: 'npm', args: ['install'] };
  }

  if (await exists(join('yarn.lock'))) return { cmd: 'yarn', args: ['install', '--frozen-lockfile'] };
  if (await exists(join('package-lock.json'))) return { cmd: 'npm', args: ['ci'] };
  return { cmd: 'npm', args: ['install'] };
}

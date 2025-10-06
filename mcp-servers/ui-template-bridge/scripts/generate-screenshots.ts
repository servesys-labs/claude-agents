#!/usr/bin/env npx tsx

/**
 * Generate screenshots for all templates
 * Creates visual references for AI agents to understand template appearance
 */

import { promises as fs } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { spawn } from 'child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const TEMPLATES_DIR = process.env.TEMPLATES_DIR ||
  path.join(process.env.HOME!, 'vibe', 'ui-templates');

// Save screenshots in multiple locations for agent access
const SCREENSHOTS_DIR = path.join(__dirname, '../screenshots');
const VIBE_SCREENSHOTS_DIR = path.join(process.env.HOME!, 'vibe', 'ui-screenshots');
const TEMP_EXTRACT_DIR = path.join(__dirname, '../.temp-screenshots');

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
 * Start Next.js dev server
 */
async function startNextDevServer(projectPath: string): Promise<{
  process: any;
  url: string;
  port: number;
}> {
  const port = 3000 + Math.floor(Math.random() * 1000); // Random port to avoid conflicts

  console.log(`  Starting Next.js dev server on port ${port}...`);

  const devProcess = spawn('npm', ['run', 'dev', '--', '-p', port.toString()], {
    cwd: projectPath,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, PORT: port.toString() },
  });

  devProcess.stdout?.on('data', (data) => {
    const output = data.toString();
    if (output.includes('Ready') || output.includes('started server')) {
      console.log('  📡 Dev server output:', output.trim());
    }
  });

  devProcess.stderr?.on('data', (data) => {
    const output = data.toString();
    if (!output.includes('warn')) {
      console.error('  ⚠️ Dev server error:', output.trim());
    }
  });

  const url = `http://localhost:${port}`;

  // Wait for server to be ready
  const ready = await waitForServer(url, 60); // 60 seconds max

  if (!ready) {
    devProcess.kill();
    throw new Error('Dev server failed to start');
  }

  return { process: devProcess, url, port };
}

/**
 * Take screenshot using Playwright and save to multiple locations
 */
async function takeScreenshot(
  url: string,
  outputPath: string,
  viewport = { width: 1280, height: 800 }
): Promise<void> {
  const { chromium } = await import('playwright');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport,
    deviceScaleFactor: 1,
  });

  const page = await context.newPage();

  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    await page.screenshot({ path: outputPath, fullPage: false });
    console.log(`  📸 Screenshot saved: ${path.basename(outputPath)}`);

    // Also save to vibe screenshots directory for permanent storage
    const vibeOutputPath = path.join(
      VIBE_SCREENSHOTS_DIR,
      path.basename(outputPath)
    );
    await fs.copyFile(outputPath, vibeOutputPath);
    console.log(`  💾 Copied to: ${vibeOutputPath}`);

  } finally {
    await page.close();
    await context.close();
    await browser.close();
  }
}

/**
 * Install dependencies for template
 */
async function installDependencies(projectPath: string): Promise<boolean> {
  console.log('  📦 Installing dependencies...');

  return new Promise((resolve) => {
    const install = spawn('npm', ['install'], {
      cwd: projectPath,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    install.on('close', (code) => {
      if (code === 0) {
        console.log('  ✅ Dependencies installed');
        resolve(true);
      } else {
        console.error('  ❌ Failed to install dependencies');
        resolve(false);
      }
    });

    // Timeout after 5 minutes
    setTimeout(() => {
      install.kill();
      console.error('  ❌ Dependency installation timed out');
      resolve(false);
    }, 300000);
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

  return extractPath;
}

/**
 * Generate screenshots for a template
 */
async function generateScreenshotsForTemplate(task: ScreenshotTask): Promise<void> {
  console.log(`\n🎨 Generating screenshots for ${task.templateId}`);

  if (task.framework === 'react-native') {
    console.log('  ⏭️  Skipping React Native template (requires Expo Go)');
    return;
  }

  // Install dependencies
  const installed = await installDependencies(task.extractPath);
  if (!installed) {
    console.error(`  ❌ Skipping ${task.templateId} - dependency installation failed`);
    return;
  }

  // Start dev server
  let server: { process: any; url: string } | null = null;

  try {
    server = await startNextDevServer(task.extractPath);

    // Take screenshots
    for (const screenshot of task.screenshots) {
      const url = `${server.url}${screenshot.route}`;
      const filename = `${task.templateId}-${screenshot.name}.png`;
      const outputPath = path.join(SCREENSHOTS_DIR, filename);

      console.log(`\n  📸 Capturing: ${screenshot.name}`);
      console.log(`     URL: ${url}`);
      console.log(`     Description: ${screenshot.description}`);

      try {
        await takeScreenshot(url, outputPath);

        // Also capture mobile viewport
        const mobileFilename = `${task.templateId}-${screenshot.name}-mobile.png`;
        const mobileOutputPath = path.join(SCREENSHOTS_DIR, mobileFilename);
        await takeScreenshot(url, mobileOutputPath, { width: 375, height: 667 });
        console.log(`  📱 Mobile screenshot saved: ${path.basename(mobileOutputPath)}`);

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
 * Main function
 */
async function main() {
  console.log('🎬 Screenshot Generation Script\n');
  console.log('This will extract templates, start dev servers, and capture screenshots');
  console.log('Expected time: ~5-10 minutes per Next.js template\n');

  // Ensure directories
  await fs.mkdir(SCREENSHOTS_DIR, { recursive: true });
  await fs.mkdir(VIBE_SCREENSHOTS_DIR, { recursive: true });
  await fs.mkdir(TEMP_EXTRACT_DIR, { recursive: true });

  console.log('📁 Screenshot locations:');
  console.log(`   1. ${SCREENSHOTS_DIR}`);
  console.log(`   2. ${VIBE_SCREENSHOTS_DIR} (permanent storage)`);
  console.log();

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
  ];

  // Filter tasks to only those with templates in manifest
  const availableTasks = tasks.filter(task =>
    manifest.templates[task.templateId]
  );

  console.log(`Found ${availableTasks.length} Next.js templates to screenshot\n`);

  // Process each template
  for (const task of availableTasks) {
    const templateData = manifest.templates[task.templateId];

    try {
      // Extract template
      task.extractPath = await extractTemplate(task.templateId, templateData.localPath);

      // Generate screenshots
      await generateScreenshotsForTemplate(task);

      console.log(`\n✅ Completed ${task.templateId}`);

    } catch (error: any) {
      console.error(`\n❌ Failed to process ${task.templateId}:`, error.message);
    }
  }

  // Cleanup temp directory
  console.log('\n🧹 Cleaning up...');
  await fs.rm(TEMP_EXTRACT_DIR, { recursive: true, force: true });

  // Generate index file with all screenshots
  console.log('\n📝 Generating screenshot index...');
  await generateScreenshotIndex();

  console.log('\n✅ Screenshot generation complete!');
  console.log(`   Screenshots saved to: ${SCREENSHOTS_DIR}`);
}

/**
 * Generate index file listing all screenshots with descriptions
 */
async function generateScreenshotIndex() {
  const files = await fs.readdir(SCREENSHOTS_DIR);
  const screenshots = files.filter(f => f.endsWith('.png'));

  // Create JSON catalog for programmatic access
  const catalog: Record<string, any> = {
    generated: new Date().toISOString(),
    total: screenshots.length,
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
      catalog.templates[templateId] = {
        screenshots: [],
      };
    }
    grouped.get(templateId)!.push(screenshot);

    // Add to catalog
    catalog.templates[templateId].screenshots.push({
      filename: screenshot,
      page: pageName,
      viewport: isMobile ? 'mobile' : 'desktop',
      dimensions: isMobile ? '375x667' : '1280x800',
      path: path.join(SCREENSHOTS_DIR, screenshot),
      permanentPath: path.join(VIBE_SCREENSHOTS_DIR, screenshot),
    });
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

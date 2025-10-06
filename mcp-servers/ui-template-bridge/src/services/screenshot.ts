import { chromium, Browser, Page } from 'playwright';
import { promises as fs } from 'fs';
import path from 'path';

/**
 * Playwright screenshot service with sandboxing
 */

export interface ScreenshotOptions {
  templateId?: string;
  sitePath?: string;
  url?: string;
  outputPath?: string;
  viewport?: { width: number; height: number };
  fullPage?: boolean;
  deviceScaleFactor?: number;
  timeout?: number;
}

export interface ScreenshotResult {
  success: boolean;
  path?: string;
  dataUri?: string;
  width?: number;
  height?: number;
  elapsedMs?: number;
  errors: string[];
  warnings: string[];
}

// Singleton browser instance
let browserInstance: Browser | null = null;
let browserLaunchPromise: Promise<Browser> | null = null;

/**
 * Get or create browser instance (singleton)
 */
async function getBrowser(): Promise<Browser> {
  if (browserInstance && browserInstance.isConnected()) {
    return browserInstance;
  }

  // If already launching, wait for it
  if (browserLaunchPromise) {
    return browserLaunchPromise;
  }

  // Launch new browser
  browserLaunchPromise = chromium.launch({
    headless: true,
    args: [
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-web-security', // Allow local file access
    ],
  });

  try {
    browserInstance = await browserLaunchPromise;
    browserLaunchPromise = null;
    return browserInstance;
  } catch (error) {
    browserLaunchPromise = null;
    throw error;
  }
}

/**
 * Close browser instance
 */
export async function closeBrowser(): Promise<void> {
  if (browserInstance) {
    await browserInstance.close();
    browserInstance = null;
  }
}

/**
 * Start local dev server for template
 */
async function startDevServer(sitePath: string): Promise<{ url: string; kill: () => void }> {
  const { spawn } = await import('child_process');

  // Check if package.json has dev script
  const packageJsonPath = path.join(sitePath, 'package.json');
  let devCommand = 'npm run dev';

  try {
    const packageJson = JSON.parse(await fs.readFile(packageJsonPath, 'utf-8'));
    if (!packageJson.scripts?.dev) {
      throw new Error('No dev script found in package.json');
    }
  } catch {
    throw new Error('Could not read package.json or no dev script found');
  }

  // Start dev server
  const proc = spawn('npm', ['run', 'dev'], {
    cwd: sitePath,
    stdio: 'pipe',
  });

  // Wait for server to start
  return new Promise((resolve, reject) => {
    let output = '';
    const timeout = setTimeout(() => {
      proc.kill();
      reject(new Error('Dev server did not start within 30 seconds'));
    }, 30000);

    proc.stdout?.on('data', (data) => {
      output += data.toString();
      // Look for localhost URL
      const match = output.match(/https?:\/\/localhost:\d+/);
      if (match) {
        clearTimeout(timeout);
        resolve({
          url: match[0],
          kill: () => proc.kill(),
        });
      }
    });

    proc.stderr?.on('data', (data) => {
      output += data.toString();
    });

    proc.on('error', (error) => {
      clearTimeout(timeout);
      reject(error);
    });
  });
}

/**
 * Generate screenshot of a template or site
 */
export async function generateScreenshot(
  options: ScreenshotOptions
): Promise<ScreenshotResult> {
  const {
    sitePath,
    url,
    outputPath,
    viewport = { width: 1280, height: 800 },
    fullPage = true,
    deviceScaleFactor = 1,
    timeout = 30000,
  } = options;

  const result: ScreenshotResult = {
    success: false,
    errors: [],
    warnings: [],
  };

  const startTime = Date.now();
  let page: Page | null = null;
  let devServer: { url: string; kill: () => void } | null = null;

  try {
    const browser = await getBrowser();

    // Create new page with sandboxing
    const context = await browser.newContext({
      viewport,
      deviceScaleFactor,
      ignoreHTTPSErrors: true,
    });

    page = await context.newPage();

    // Set timeout
    page.setDefaultTimeout(timeout);

    // Determine URL to screenshot
    let targetUrl = url;

    if (!targetUrl && sitePath) {
      // Start local dev server
      result.warnings.push('Starting local dev server (this may take 30+ seconds)');
      devServer = await startDevServer(sitePath);
      targetUrl = devServer.url;
    }

    if (!targetUrl) {
      result.errors.push('MISSING_URL: Must provide either url or sitePath');
      return result;
    }

    // Navigate to page
    await page.goto(targetUrl, { waitUntil: 'networkidle', timeout });

    // Wait for content to load
    await page.waitForTimeout(2000);

    // Take screenshot
    const screenshotBuffer = await page.screenshot({
      fullPage,
      type: 'png',
    });

    // Save or return as data URI
    if (outputPath) {
      await fs.mkdir(path.dirname(outputPath), { recursive: true });
      await fs.writeFile(outputPath, screenshotBuffer);
      result.path = outputPath;
    } else {
      result.dataUri = `data:image/png;base64,${screenshotBuffer.toString('base64')}`;
    }

    result.success = true;
    result.width = viewport.width;
    result.height = viewport.height;
    result.elapsedMs = Date.now() - startTime;

    return result;
  } catch (error: any) {
    result.errors.push(`SCREENSHOT_ERROR: ${error.message}`);
    result.elapsedMs = Date.now() - startTime;
    return result;
  } finally {
    // Cleanup
    if (page) {
      await page.close();
    }
    if (devServer) {
      devServer.kill();
    }
  }
}

/**
 * Generate screenshots for all templates
 */
export async function generateTemplateScreenshots(
  templatesDir: string,
  outputDir: string
): Promise<Map<string, ScreenshotResult>> {
  const results = new Map<string, ScreenshotResult>();

  try {
    const templates = await fs.readdir(templatesDir);

    for (const templateId of templates) {
      const templatePath = path.join(templatesDir, templateId);
      const stats = await fs.stat(templatePath);

      if (!stats.isDirectory()) continue;

      const outputPath = path.join(outputDir, `${templateId}-preview.png`);

      const result = await generateScreenshot({
        templateId,
        sitePath: templatePath,
        outputPath,
        viewport: { width: 1280, height: 800 },
        fullPage: true,
      });

      results.set(templateId, result);
    }

    return results;
  } catch (error: any) {
    throw new Error(`Failed to generate template screenshots: ${error.message}`);
  }
}

/**
 * Generate multiple viewport screenshots (responsive preview)
 */
export async function generateResponsiveScreenshots(
  options: Omit<ScreenshotOptions, 'viewport'>
): Promise<Map<string, ScreenshotResult>> {
  const viewports = [
    { name: 'mobile', width: 375, height: 667 },
    { name: 'tablet', width: 768, height: 1024 },
    { name: 'desktop', width: 1280, height: 800 },
    { name: 'wide', width: 1920, height: 1080 },
  ];

  const results = new Map<string, ScreenshotResult>();

  for (const viewport of viewports) {
    const outputPath = options.outputPath
      ? options.outputPath.replace(/\.png$/, `-${viewport.name}.png`)
      : undefined;

    const result = await generateScreenshot({
      ...options,
      viewport: { width: viewport.width, height: viewport.height },
      outputPath,
    });

    results.set(viewport.name, result);
  }

  return results;
}

import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { guard, privateDirectory } from './fixtures.js';
guard();
const output = privateDirectory('browser-private-output');
export default defineConfig({
  testDir: '.',
  testMatch: ['journey.spec.js', 'accessibility.spec.js'],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  timeout: 300_000,
  globalTimeout: 1_800_000,
  expect: { timeout: 15_000 },
  reporter: [[path.resolve('sanitized-reporter.js')]],
  outputDir: output,
  use: {
    browserName: 'chromium',
    baseURL: 'http://127.0.0.1:15500',
    headless: true,
    viewport: { width: 1440, height: 1000 },
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    trace: 'off',
    video: 'off',
    screenshot: 'off',
    acceptDownloads: false,
    serviceWorkers: 'block'
  }
});

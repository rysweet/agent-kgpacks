import { defineConfig } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: 1,
  workers: 1,
  use: {
    baseURL: 'http://localhost:5173',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
  webServer: [
    {
      command: `WIKIGR_DATABASE_PATH=${projectRoot}/data/test_10_articles.db WIKIGR_RATE_LIMIT_ENABLED=false python3.10 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`,
      cwd: projectRoot,
      port: 8000,
      timeout: 30_000,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npm run dev',
      port: 5173,
      timeout: 30_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
});

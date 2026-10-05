import { defineConfig, devices } from '@playwright/test';

// End-to-end tests against the real stack: Django on :8000 and a production Next build on :3000.
// Needs a Postgres reachable at DATABASE_URL and `npm run build` beforehand.
// PYTHON picks the interpreter for the backend (e.g. a virtualenv's python).
const python = process.env.PYTHON || 'python';

export default defineConfig({
    testDir: './e2e',
    timeout: 60_000,
    fullyParallel: false,
    retries: process.env.CI ? 1 : 0,
    reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
    use: {
        baseURL: 'http://localhost:3000',
        trace: 'retain-on-failure',
        launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } : {},
    },
    projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
    webServer: [
        {
            command: `${python} manage.py migrate --noinput && ${python} manage.py runserver 8000 --noreload`,
            cwd: '../backend',
            url: 'http://localhost:8000/api/rankings/',
            reuseExistingServer: !process.env.CI,
            timeout: 120_000,
        },
        {
            command: 'npm run start',
            url: 'http://localhost:3000/login',
            // NEXT_PUBLIC_API_URL is baked in at build time and defaults to http://localhost:8000.
            reuseExistingServer: !process.env.CI,
        },
    ],
});

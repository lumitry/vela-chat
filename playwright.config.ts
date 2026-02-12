import { defineConfig, devices } from '@playwright/test';

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// import dotenv from 'dotenv';
// dotenv.config({ path: '.env' });

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
	testDir: './tests',
	/* Run tests in files in parallel */
	fullyParallel: true,
	/* Fail the build on CI if you accidentally left test.only in the source code. */
	forbidOnly: !!process.env.CI,
	/* Retry on CI only */
	retries: process.env.CI ? 2 : 0,
	/* Opt out of parallel tests on CI. */
	workers: process.env.CI ? 1 : undefined,
	/* Reporter to use. See https://playwright.dev/docs/test-reporters */
	reporter: 'html',
	/* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
	use: {
		/* Base URL to use in actions like `await page.goto('/')`. */
		/* Using localhost instead of 127.0.0.1 to match CORS configuration */
		baseURL: 'http://localhost:5173',

		/* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
		trace: 'on-first-retry',
		screenshot: 'only-on-failure',

		/* Bypass CSP and other security restrictions that might block requests */
		bypassCSP: true,

		/* Ignore HTTPS errors (if any) */
		ignoreHTTPSErrors: true,

		/* Set a longer timeout for navigation */
		navigationTimeout: 30000
	},

	/* Configure projects for major browsers */
	projects: [
		{
			name: 'setup',
			testMatch: /.*\.setup\.ts/
			// This project runs before all others
		},
		{
			name: 'chromium',
			testMatch: /.*\.spec\.ts/,
			testIgnore: [/.*\.signupsDisabled\.spec\.ts/, /.*\.defaultRole\.spec\.ts/], // Exclude special test files
			dependencies: ['setup'], // Run setup project first
			use: { ...devices['Desktop Chrome'] }
		},

		{
			name: 'firefox',
			testMatch: /.*\.spec\.ts/,
			testIgnore: [/.*\.signupsDisabled\.spec\.ts/, /.*\.defaultRole\.spec\.ts/], // Exclude special test files
			dependencies: ['setup'],
			use: { ...devices['Desktop Firefox'] }
		},

		{
			name: 'webkit',
			testMatch: /.*\.spec\.ts/,
			testIgnore: [/.*\.signupsDisabled\.spec\.ts/, /.*\.defaultRole\.spec\.ts/], // Exclude special test files
			dependencies: ['setup'],
			use: { ...devices['Desktop Safari'] }
		},

		{
			name: 'chromium-signups-disabled',
			testMatch: /.*\.signupsDisabled\.spec\.ts/,
			dependencies: ['setup', 'chromium'], // Run after regular chromium tests to avoid interference
			use: { ...devices['Desktop Chrome'] }
		},

		{
			name: 'firefox-signups-disabled',
			testMatch: /.*\.signupsDisabled\.spec\.ts/,
			dependencies: ['setup', 'firefox'], // Run after regular firefox tests
			use: { ...devices['Desktop Firefox'] }
		},

		{
			name: 'webkit-signups-disabled',
			testMatch: /.*\.signupsDisabled\.spec\.ts/,
			dependencies: ['setup', 'webkit'], // Run after regular webkit tests
			use: { ...devices['Desktop Safari'] }
		},

		{
			name: 'default-role-tests',
			testMatch: /.*\.defaultRole\.spec\.ts/,
			dependencies: [
				'setup',
				'chromium',
				'firefox',
				'webkit',
				'chromium-signups-disabled',
				'firefox-signups-disabled',
				'webkit-signups-disabled'
			], // Run after all regular tests AND signups-disabled tests (to ensure signups are re-enabled)
			workers: 1, // CRITICAL: Run sequentially across browsers to avoid global state conflicts
			use: { ...devices['Desktop Chrome'] } // Just use one browser since we're testing backend behavior
		}

		/* Test against mobile viewports. */
		// {
		//   name: 'Mobile Chrome',
		//   use: { ...devices['Pixel 5'] },
		// },
		// {
		//   name: 'Mobile Safari',
		//   use: { ...devices['iPhone 12'] },
		// },

		/* Test against branded browsers. */
		// {
		//   name: 'Microsoft Edge',
		//   use: { ...devices['Desktop Edge'], channel: 'msedge' },
		// },
		// {
		//   name: 'Google Chrome',
		//   use: { ...devices['Desktop Chrome'], channel: 'chrome' },
		// },
	]
});

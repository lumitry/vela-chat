import { test as base } from '@playwright/test';
import { AuthPage, AuthMode } from '../pages/AuthPage';
import { generateUserWithTestContext, type TestUser } from '../data/users';

/**
 * Extended test type that includes automatic test user authentication.
 * The testUser is available but optional - you don't need to request it.
 */
export type TestWithUser = {
	testUser: TestUser;
};

/**
 * Fixture that automatically creates and signs up a test user for each test.
 * The user's name and email are generated based on the test context
 * (suite name, test name, etc.) to prevent collisions and make debugging easier.
 *
 * This fixture runs automatically - you don't need to request it unless you need
 * access to the user object (email, name, etc.).
 *
 * Usage (most common - just use the page):
 * ```typescript
 * import { test } from '../fixtures/testUser';
 *
 * test('my test', async ({ page }) => {
 *   // User is already signed up and authenticated - no need to request testUser!
 *   // Just use the page and you're good to go
 * });
 * ```
 *
 * If you need access to the user object (e.g., email, name):
 * ```typescript
 * test('my test', async ({ page, testUser }) => {
 *   console.log(testUser.email);
 * });
 * ```
 *
 * To create additional users in a single test with custom identifiers:
 * ```typescript
 * import { test } from '../fixtures/testUser';
 * import { generateUserWithTestContext } from '../data/users';
 * import { AuthPage, AuthMode } from '../pages/AuthPage';
 *
 * test('my test', async ({ page, testUser, testInfo }) => {
 *   // testUser is the default user (already signed up)
 *   // Create additional users with custom identifiers
 *   const user2 = generateUserWithTestContext(testInfo, 'user2');
 *   const authPage = new AuthPage(page);
 *   // ... sign up user2 if needed
 * });
 * ```
 */
export const test = base.extend<TestWithUser>({
	testUser: [
		async ({ page }, use, testInfo) => {
			// Generate user based on test context
			const user = generateUserWithTestContext(testInfo);

			// Navigate to home page (which will redirect to auth if not logged in)
			await page.goto('/', { waitUntil: 'load' });

			// Sign up the user
			const authPage = new AuthPage(page);
			await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
			await authPage.signUp(user);
			await authPage.toast.assertToastIsVisible('success');

			// Verify we're logged in (should be redirected to home page)
			await page.waitForURL('/', { timeout: 10000 });

			// Provide the user to the test (if requested)
			await use(user);

			// Teardown: The user remains in the database, but that's fine for E2E tests.
			// If needed, we could add cleanup logic here, but typically E2E tests
			// rely on database resets between test runs rather than per-test cleanup.
		},
		{ auto: true } // This makes it run automatically even if not requested
	]
});

export { expect } from '@playwright/test';

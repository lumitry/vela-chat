import { test, expect } from '@playwright/test';
import { AuthPage } from '../pages/AuthPage';
import { SHARED_USERS } from '../data/users';
import { HomePage } from '../pages/HomePage';
import { AdminSettingsGeneralTab } from '../pages/Admin/AdminSettingsGeneralTab';

/**
 * Tests for when new user signups are disabled.
 *
 * This is in a separate test file to isolate it from other auth tests.
 * Tests within this file can run in parallel with each other, but the file
 * itself runs separately from AuthTest.spec.ts, preventing interference.
 *
 * The beforeAll/afterAll hooks ensure signups are disabled once before all
 * tests and re-enabled after all tests complete.
 */
test.describe('Sign up (new signups are disabled)', () => {
	/**
	 * One-time setup: Login as admin and disable new user signups.
	 * This runs once before all tests in this describe block.
	 */
	test.beforeAll(async ({ browser }) => {
		// Create a new page context for setup
		const context = await browser.newContext();
		const page = await context.newPage();

		try {
			// Navigate to home page
			await page.goto('/', { waitUntil: 'load' });

			// Sign in as admin
			const authPage = new AuthPage(page);
			await authPage.signIn(SHARED_USERS.preExistingAdmin);
			await authPage.toast.assertToastIsVisible('success');
			await expect(page).toHaveURL('/');

			// Navigate to admin settings
			const homePage = new HomePage(page);
			await homePage.clickUserMenuButton();
			await homePage.userMenu.clickAdminPanel();

			// Disable new user signups
			const adminSettings = new AdminSettingsGeneralTab(page);
			await adminSettings.setEnableNewSignUps(false);
			await adminSettings.save();
			await adminSettings.toast.assertToastIsVisible('success');
		} finally {
			// Close the setup context (but keep the browser open)
			await context.close();
		}
	});

	/**
	 * One-time cleanup: Re-enable new user signups.
	 * This runs once after all tests in this describe block complete.
	 */
	test.afterAll(async ({ browser }) => {
		// Create a new page context for cleanup
		const context = await browser.newContext();
		const page = await context.newPage();

		try {
			// Navigate to home page
			await page.goto('/', { waitUntil: 'load' });

			// Sign in as admin
			const authPage = new AuthPage(page);
			await authPage.signIn(SHARED_USERS.preExistingAdmin);
			await authPage.toast.assertToastIsVisible('success');
			await expect(page).toHaveURL('/');

			// Navigate to admin settings
			const homePage = new HomePage(page);
			await homePage.clickUserMenuButton();
			await homePage.userMenu.clickAdminPanel();

			// Re-enable new user signups
			const adminSettings = new AdminSettingsGeneralTab(page);
			await adminSettings.setEnableNewSignUps(true);
			await adminSettings.save();
			await adminSettings.toast.assertToastIsVisible('success');
		} finally {
			// Close the cleanup context
			await context.close();
		}
	});

	test.beforeEach(async ({ page }) => {
		await page.goto('/', { waitUntil: 'load' });
	});

	test('Sign up button/switch should not be visible on auth page', async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.assertSwitchModeButtonIsNotVisible();
		await authPage.assertSignInFormIsVisible();
	});

	// TODO: Direct API calls to signup endpoint should be rejected
});

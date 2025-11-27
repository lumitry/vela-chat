import { test, expect } from '@playwright/test';
import { AuthMode, AuthPage } from '../pages/AuthPage';
import { SHARED_USERS, generateRandomValidUser } from '../data/users';
import { HomePage } from '../pages/HomePage';
import { AdminSettingsGeneralTab } from '../pages/Admin/AdminSettingsGeneralTab';

/**
 * Tests for default user role configuration.
 *
 * These tests modify a global backend setting (default user role), so they must run
 * sequentially across all browsers to avoid interference. This is achieved by:
 * 1. Putting them in a separate file
 * 2. Configuring a project with workers: 1 in playwright.config.ts
 * 3. Adding dependencies on signups-disabled tests to ensure new user signups are re-enabled
 */
test.describe('Sign up - default user role', () => {
	test('Sign up flow with all default role permutations', async ({ browser }) => {
		const roles: Array<'admin' | 'user' | 'pending'> = ['user', 'pending', 'admin'];

		// Restore default role to 'user' after all tests complete
		let cleanupContext: Awaited<ReturnType<typeof browser.newContext>> | null = null;

		for (const expectedRole of roles) {
			await test.step(`Test with default role: ${expectedRole}`, async () => {
				// Setup: Change global setting
				const adminContext = await browser.newContext();
				const adminPage = await adminContext.newPage();

				try {
					await adminPage.goto('/', { waitUntil: 'load' });

					// Sign in as admin
					const adminAuthPage = new AuthPage(adminPage);
					await adminAuthPage.signIn(SHARED_USERS.preExistingAdmin);
					await adminAuthPage.toast.assertToastIsVisible('success');
					await expect(adminPage).toHaveURL('/');

					// Navigate to admin settings
					const adminHomePage = new HomePage(adminPage);
					await adminHomePage.clickUserMenuButton();
					await adminHomePage.userMenu.clickAdminPanel();

					// Set default user role
					const adminSettings = new AdminSettingsGeneralTab(adminPage);
					await adminSettings.setDefaultUserRole(expectedRole);
					await adminSettings.clickSaveButton();
					await adminSettings.toast.assertToastIsVisible('success');
				} finally {
					await adminContext.close();
				}

				// Test: Sign up and verify
				// Use a fresh context for each iteration to avoid cookie/session state
				const testContext = await browser.newContext();
				const testPage = await testContext.newPage();

				try {
					await testPage.goto('/', { waitUntil: 'load' });
					const authPage = new AuthPage(testPage);
					await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
					await authPage.signUp(generateRandomValidUser());
					await authPage.toast.assertToastIsVisible('success');
					await expect(testPage).toHaveURL('/');

					const homePage = new HomePage(testPage);
					await homePage.assertUserRole(expectedRole);
				} finally {
					await testContext.close();
				}
			});
		}

		// Cleanup: Restore default role to 'admin'
		try {
			cleanupContext = await browser.newContext();
			const cleanupPage = await cleanupContext.newPage();

			await cleanupPage.goto('/', { waitUntil: 'load' });

			const cleanupAuthPage = new AuthPage(cleanupPage);
			await cleanupAuthPage.signIn(SHARED_USERS.preExistingAdmin);
			await cleanupAuthPage.toast.assertToastIsVisible('success');
			await expect(cleanupPage).toHaveURL('/');

			const cleanupHomePage = new HomePage(cleanupPage);
			await cleanupHomePage.clickUserMenuButton();
			await cleanupHomePage.userMenu.clickAdminPanel();

			const cleanupSettings = new AdminSettingsGeneralTab(cleanupPage);
			await cleanupSettings.setDefaultUserRole('admin');
			await cleanupSettings.clickSaveButton();
			await cleanupSettings.toast.assertToastIsVisible('success');
		} catch (error) {
			// Log but don't fail the test if cleanup fails
			console.warn('Failed to restore default user role during cleanup:', error);
		} finally {
			if (cleanupContext) {
				await cleanupContext.close();
			}
		}
	});
});

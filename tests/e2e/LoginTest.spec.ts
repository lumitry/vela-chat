import { test, expect } from '@playwright/test';
import { LoginPage } from '../pages/LoginPage';
import { SHARED_USERS } from '../data/users';

test('login', async ({ page }) => {
	await page.goto('/', { waitUntil: 'networkidle' });
	const loginPage = new LoginPage(page);

	// Expect a title "to contain" a substring.
	await expect(page).toHaveTitle(/VelaChat/);
	await loginPage.assertEmailInputIsVisible();
	await loginPage.assertPasswordInputIsVisible();
	await loginPage.assertSignInButtonIsVisible();
	await loginPage.login(SHARED_USERS.preExistingAdmin);
	await loginPage.toast.assertToastIsVisible('success');
	await expect(page).toHaveTitle(/FAIL/); // TODO IT'S ALIVE! NOW GET TESTING!
});

// TODO add actual tests for login page, e.g. invalid email or password, etc.

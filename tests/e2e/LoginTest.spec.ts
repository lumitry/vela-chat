import { test, expect } from '@playwright/test';
import { AuthMode, AuthPage } from '../pages/AuthPage';
import { SHARED_USERS, generateRandomValidUser } from '../data/users';

test.describe('Sign in', () => {
	test('Sign in with valid credentials', async ({ page }) => {
		await page.goto('/', { waitUntil: 'networkidle' });
		const authPage = new AuthPage(page);

		await expect(page).toHaveTitle(/VelaChat/);
		await authPage.assertEmailInputIsVisible();
		await authPage.assertPasswordInputIsVisible();
		await authPage.assertSubmitButtonIsVisible();
		await authPage.signIn(SHARED_USERS.preExistingAdmin);
		await authPage.toast.assertToastIsVisible('success');
		await expect(page).toHaveURL('/');
	});

	test('Sign in with non-existent user', async ({ page }) => {
		await page.goto('/', { waitUntil: 'networkidle' });
		const authPage = new AuthPage(page);
		await authPage.signIn(SHARED_USERS.nonExistentUser);
		await authPage.toast.assertToastIsVisible('error');
		await expect(page).toHaveURL('/auth?redirect=%2F');
	});
});

test.describe('Sign up', () => {
	// success case
	test('Sign up with valid credentials', async ({ page }) => {
		await page.goto('/', { waitUntil: 'networkidle' });
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		await authPage.signUp(generateRandomValidUser());
		await authPage.toast.assertToastIsVisible('success');
		await expect(page).toHaveURL('/');
	});

	// invalid cases

	test('Sign up with invalid email', async ({ page }) => {
		await page.goto('/', { waitUntil: 'networkidle' });
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		await authPage.signUp(SHARED_USERS.badEmailUser);
		// Assert that the email field shows a validation error
		await authPage.assertEmailInputIsInvalid();
		await expect(page).toHaveURL('/auth?redirect=%2F');
	});

	test('Sign up with invalid password', async ({ page }) => {
		await page.goto('/', { waitUntil: 'networkidle' });
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		await authPage.signUp(SHARED_USERS.badPasswordUser);
		// Assert that the password field shows a validation error
		await authPage.assertPasswordInputIsInvalid();
		await expect(page).toHaveURL('/auth?redirect=%2F');
	});

	test('Sign up with invalid name', async ({ page }) => {
		await page.goto('/', { waitUntil: 'networkidle' });
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		await authPage.signUp(SHARED_USERS.badNameUser);
		// Assert that the name field shows a validation error
		await authPage.assertNameInputIsInvalid();
		await expect(page).toHaveURL('/auth?redirect=%2F');
	});
});

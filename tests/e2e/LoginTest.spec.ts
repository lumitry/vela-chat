import { test, expect } from '@playwright/test';
import { AuthMode, AuthPage } from '../pages/AuthPage';
import { SHARED_USERS, generateRandomValidUser } from '../data/users';

test.describe('Sign in', { tag: '@smoke' }, () => {
	test('Sign in with valid credentials', async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.signIn(SHARED_USERS.preExistingAdmin);
		await authPage.toast.assertToastIsVisible('success');
		await expect(page).toHaveURL('/');
	});

	test('Sign in with non-existent user', async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.signIn(SHARED_USERS.nonExistentUser);
		await authPage.toast.assertToastIsVisible('error');
		await expect(page).toHaveURL('/auth?redirect=%2F');
	});

	test('Sign in with wrong password', async ({ page }) => {
		const authPage = new AuthPage(page);
		const wrongPasswordUser = {
			...SHARED_USERS.preExistingAdmin,
			password: 'wrongpassword123'
		};
		await authPage.signIn(wrongPasswordUser);
		await authPage.toast.assertToastIsVisible('error');
		await expect(page).toHaveURL('/auth?redirect=%2F');
	});

	test('Sign in with empty email', async ({ page }) => {
		const authPage = new AuthPage(page);
		const emptyEmailUser = {
			...SHARED_USERS.preExistingAdmin,
			email: ''
		};
		await authPage.signIn(emptyEmailUser);
		await authPage.assertEmailInputIsInvalid();
		await expect(page).toHaveURL('/auth?redirect=%2F');
	});

	test('Sign in with empty password', async ({ page }) => {
		const authPage = new AuthPage(page);
		const emptyPasswordUser = {
			...SHARED_USERS.preExistingAdmin,
			password: ''
		};
		await authPage.signIn(emptyPasswordUser);
		await authPage.assertPasswordInputIsInvalid();
		await expect(page).toHaveURL('/auth?redirect=%2F');
	});
});

test.describe('Sign up', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/', { waitUntil: 'load' });
	});

	// only tagging the critical test case as smoke
	test('Sign up with valid credentials', { tag: ['@smoke'] }, async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		await authPage.signUp(generateRandomValidUser());
		await authPage.toast.assertToastIsVisible('success');
		await expect(page).toHaveURL('/');
	});

	test('Sign up with duplicate email', async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		// Try to sign up with an email that already exists
		await authPage.signUp({
			...SHARED_USERS.preExistingAdmin,
			name: 'Duplicate Email User'
		});
		await authPage.toast.assertToastIsVisible('error');
		await expect(page).toHaveURL('/auth?redirect=%2F');
	});

	test('Sign up with invalid email', async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		await authPage.signUp(SHARED_USERS.badEmailUser);
		await authPage.assertEmailInputIsInvalid();
		await expect(page).toHaveURL('/auth?redirect=%2F');
	});

	test('Sign up with invalid password', async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		await authPage.signUp(SHARED_USERS.badPasswordUser);
		await authPage.assertPasswordInputIsInvalid();
		await expect(page).toHaveURL('/auth?redirect=%2F');
	});

	test('Sign up with invalid name', async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		await authPage.signUp(SHARED_USERS.badNameUser);
		await authPage.assertNameInputIsInvalid();
		await expect(page).toHaveURL('/auth?redirect=%2F');
	});

	test('Sign up with multiple invalid fields', async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		const invalidUser = {
			name: '',
			email: 'notanemail',
			password: '',
			role: 'user' as const
		};
		await authPage.signUp(invalidUser);
		// All three fields should be invalid
		await authPage.assertNameInputIsInvalid();
		await authPage.assertEmailInputIsInvalid();
		await authPage.assertPasswordInputIsInvalid();
		await expect(page).toHaveURL('/auth?redirect=%2F');
	});
});

// TODO consider: passwords with emojis (they should work)
// TODO and also passwords with other unicode buffoonery
// TODO more importantly... test that if someone logs out, their token/session is invalidated and future API requests are ignored! probably a separate bespoke test for that.
// TODO: names longer than 255 chars
// TODO: emails longer than 255 chars
// TODO: names longer than 255 CODE POINTS (e.g. via many-codepoint emojis)

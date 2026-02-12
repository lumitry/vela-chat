import { test, expect } from '@playwright/test';
import { AuthMode, AuthPage } from '../pages/AuthPage';
import { SHARED_USERS, generateRandomValidUser } from '../data/users';
import { ERROR_MESSAGES } from '../data/messages';

const AUTH_FAIL_REDIRECT_URL = '/auth?redirect=%2F';

test.describe('Sign in', { tag: '@smoke' }, () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/', { waitUntil: 'load' });
	});

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
		await expect(page).toHaveURL(AUTH_FAIL_REDIRECT_URL);
	});

	test('Sign in with wrong password', async ({ page }) => {
		const authPage = new AuthPage(page);
		const wrongPasswordUser = {
			...SHARED_USERS.preExistingAdmin,
			password: 'wrongpassword123'
		};
		await authPage.signIn(wrongPasswordUser);
		await authPage.toast.assertToastIsVisible('error');
		await expect(page).toHaveURL(AUTH_FAIL_REDIRECT_URL);
	});

	test('Sign in with empty email', async ({ page }) => {
		const authPage = new AuthPage(page);
		const emptyEmailUser = {
			...SHARED_USERS.preExistingAdmin,
			email: ''
		};
		await authPage.signIn(emptyEmailUser);
		await authPage.assertEmailInputIsInvalid();
		await expect(page).toHaveURL(AUTH_FAIL_REDIRECT_URL);
	});

	test('Sign in with empty password', async ({ page }) => {
		const authPage = new AuthPage(page);
		const emptyPasswordUser = {
			...SHARED_USERS.preExistingAdmin,
			password: ''
		};
		await authPage.signIn(emptyPasswordUser);
		await authPage.assertPasswordInputIsInvalid();
		await expect(page).toHaveURL(AUTH_FAIL_REDIRECT_URL);
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
		await expect(page).toHaveURL(AUTH_FAIL_REDIRECT_URL);
	});

	test('Sign up with invalid email', async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		await authPage.signUp({
			name: 'Bad Email User',
			email: 'bad.email at test dot example dot com',
			password: 'bad.email.password',
			role: 'user' as const
		});
		await authPage.assertEmailInputIsInvalid();
		await expect(page).toHaveURL(AUTH_FAIL_REDIRECT_URL);
	});

	test('Sign up with invalid password', async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		await authPage.signUp({
			name: 'Bad Password User',
			email: 'bad.password@test.example.com',
			password: '', // as of right now, the backend DOES allow empty passwords, but the frontend prevents it unless you use inspect element to remove the required attribute
			role: 'user' as const
		});
		await authPage.assertPasswordInputIsInvalid();
		await expect(page).toHaveURL(AUTH_FAIL_REDIRECT_URL);
	});

	test('Sign up with invalid name', async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		await authPage.signUp({
			// we like to have fun around here
			name: '', // name is required
			email: 'you_give_love@bad.name',
			password: 'j0vi4l_p455w0rd',
			role: 'user' as const
		});
		await authPage.assertNameInputIsInvalid();
		await expect(page).toHaveURL(AUTH_FAIL_REDIRECT_URL);
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
		await expect(page).toHaveURL(AUTH_FAIL_REDIRECT_URL);
	});

	test('Sign up with name too long', async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		await authPage.signUp({
			name: 'a'.repeat(256),
			email: 'name.too.long@test.example.com',
			password: 'test',
			role: 'user' as const
		});
		await authPage.toast.assertToastIsVisible('error');
		await authPage.toast.assertToastText('error', ERROR_MESSAGES.USERNAME_TOO_LONG);
		await expect(page).toHaveURL(AUTH_FAIL_REDIRECT_URL);
	});

	test('Sign up with email too long', async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		await authPage.signUp({
			name: 'email.too.long.user',
			email: 'a'.repeat(256) + '@test.example.com',
			password: 'test',
			role: 'user' as const
		});
		await authPage.toast.assertToastIsVisible('error');
		await authPage.toast.assertToastText('error', ERROR_MESSAGES.EMAIL_TOO_LONG);
		await expect(page).toHaveURL(AUTH_FAIL_REDIRECT_URL);
	});

	test('Sign up with name too long w/ unicode', async ({ page }) => {
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignUp);
		await authPage.signUp({
			name: '🧑🏻‍❤️‍💋‍🧑🏼'.repeat(255), // each of these emojis is 15 code points, so 255 * 15 = 3825 code points. this is well above the 255 code point limit which is what varchar(255) in postgres supports.
			email: 'unicode.buffoonery@test.example.com',
			password: 'test',
			role: 'user' as const
		});
		await authPage.toast.assertToastIsVisible('error');
		await authPage.toast.assertToastText('error', ERROR_MESSAGES.USERNAME_TOO_LONG);
		// note: this error technically is bad because the username isn't actually over 255 "characters", but we can't expect the backend to be pedantic about code points versus characters.
		await expect(page).toHaveURL(AUTH_FAIL_REDIRECT_URL);
	});
});

// TODO consider: passwords with emojis (they should work)
// TODO and also passwords with other unicode buffoonery
// TODO more importantly... test that if someone logs out, their token/session is invalidated and future API requests are ignored! probably a separate bespoke test for that.

import { expect, type Page } from '@playwright/test';
import { BasePage } from './BasePage';
import type { TestUser } from '../data/users';
import { testId } from '$lib/utils/testId';

/**
 * Onboarding Flow - Page after the user clicks "Get Started" on the landing page.
 * Technically in the Svelte code this is the same as LoginPage, but we'll keep it separate since they're totally different in purpose.
 * TODO: is this always the create account flow? if so, RENAME IT!
 */
export class GetStartedPage extends BasePage {
	private nameInput = this.page.getByTestId(testId('Onboarding', 'NameInput'));
	private emailInput = this.page.getByTestId(testId('Onboarding', 'EmailInput'));
	private passwordInput = this.page.getByTestId(testId('Onboarding', 'PasswordInput'));
	private createAccountButton = this.page.getByTestId(testId('Onboarding', 'SubmitButton'));

	constructor(page: Page) {
		super(page);
	}

	async createAccount(user: TestUser): Promise<void> {
		await this.nameInput.fill(user.name);
		await this.emailInput.fill(user.email);
		await this.passwordInput.fill(user.password);
		await this.createAccountButton.click();
	}

	async assertNameInputIsVisible(): Promise<void> {
		await expect(this.nameInput).toBeVisible();
	}

	async assertEmailInputIsVisible(): Promise<void> {
		await expect(this.emailInput).toBeVisible();
	}

	async assertPasswordInputIsVisible(): Promise<void> {
		await expect(this.passwordInput).toBeVisible();
	}

	async assertCreateAccountButtonIsVisible(): Promise<void> {
		await expect(this.createAccountButton).toBeVisible();
	}
}

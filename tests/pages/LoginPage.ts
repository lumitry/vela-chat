import { expect, type Page } from '@playwright/test';
import { BasePage } from './BasePage';
import type { TestUser } from '../data/users';

export class LoginPage extends BasePage {
	constructor(page: Page) {
		super(page);
	}

	private emailInput = this.page.getByRole('textbox', { name: 'Enter Your Email' });
	private passwordInput = this.page.getByRole('textbox', { name: 'Enter Your Password' });
	private signInButton = this.page.getByRole('button', { name: 'Sign in' });

	async login(user: TestUser): Promise<void> {
		await this.emailInput.fill(user.email);
		await this.passwordInput.fill(user.password);
		await this.signInButton.click();
	}

	async assertEmailInputIsVisible(): Promise<void> {
		await expect(this.emailInput).toBeVisible();
	}

	async assertPasswordInputIsVisible(): Promise<void> {
		await expect(this.passwordInput).toBeVisible();
	}

	async assertSignInButtonIsVisible(): Promise<void> {
		await expect(this.signInButton).toBeVisible();
	}
}

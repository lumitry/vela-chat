import { expect, type Page } from '@playwright/test';
import { BasePage } from './BasePage';
import { testId } from '$lib/utils/testId';

/**
 * The page that users see when they first start the app, before any users have been created.
 */
export class OnboardingPage extends BasePage {
	private getStartedButton = this.page.getByTestId(testId('Onboarding', 'GetStartedButton'));

	constructor(page: Page) {
		super(page);
	}

	async clickGetStartedButton(): Promise<void> {
		await this.getStartedButton.click();
	}

	async assertGetStartedButtonIsVisible(): Promise<void> {
		await expect(this.getStartedButton).toBeVisible();
	}
}

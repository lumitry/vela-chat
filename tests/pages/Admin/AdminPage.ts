import type { Page } from '@playwright/test';
import { BasePage } from '../BasePage';
import { testId } from '$lib/utils/testId';

/**
 * Common parent page object for the admin panel pages.
 * URL base: /admin
 */
export abstract class AdminPage extends BasePage {
	constructor(page: Page) {
		super(page);
	}

	// the page buttons along the top of the page
	private usersPageButton = this.page.getByTestId(testId('Admin', 'PageButton', 'Users'));
	private evaluationsPageButton = this.page.getByTestId(
		testId('Admin', 'PageButton', 'Evaluations')
	);
	private functionsPageButton = this.page.getByTestId(testId('Admin', 'PageButton', 'Functions'));
	private settingsPageButton = this.page.getByTestId(testId('Admin', 'PageButton', 'Settings'));

	async clickUsersPageButton(): Promise<void> {
		await this.usersPageButton.click();
	}

	/**
	 * Takes you to the admin panel - evaluations page.
	 *
	 * NOT the admin settings - evaluations tab! Those are two separate things. Very distinct from one another. Related, but separate.
	 *
	 * URL: /admin/evaluations
	 *
	 * PageObject: AdminEvaluationsPage
	 */
	async clickEvaluationsPageButton(): Promise<void> {
		await this.evaluationsPageButton.click();
	}

	async clickFunctionsPageButton(): Promise<void> {
		await this.functionsPageButton.click();
	}

	async clickSettingsPageButton(): Promise<void> {
		await this.settingsPageButton.click();
	}
}

import { expect, type Page } from '@playwright/test';
import { BaseChatPage } from './BaseChatPage';

/**
 * The home page, AKA the new chat page.
 */
export class HomePage extends BaseChatPage {
	private placeholderCurrentModelName = this.getPageLocator('Placeholder', 'CurrentModelName');
	private placeholderDescription = this.getPageLocator('Placeholder', 'Description');

	constructor(page: Page) {
		super(page);
	}

	async assertPlaceholderCurrentModelName(modelName: string): Promise<void> {
		await expect(this.placeholderCurrentModelName).toHaveText(modelName);
	}

	async assertPlaceholderDescription(description: string | null): Promise<void> {
		if (description === null) {
			// When description is null, the element should not exist
			await expect(this.placeholderDescription).not.toBeVisible();
		} else {
			await expect(this.placeholderDescription).toHaveText(description);
		}
	}
}

import { expect, type Page } from '@playwright/test';
import { BaseChatPage } from './BaseChatPage';

/**
 * The home page, AKA the new chat page.
 */
export class HomePage extends BaseChatPage {
	private placeholderCurrentModelName = this.getPageLocator('Placeholder', 'CurrentModelName');

	constructor(page: Page) {
		super(page);
	}

	async assertPlaceholderCurrentModelName(modelName: string): Promise<void> {
		await expect(this.placeholderCurrentModelName).toHaveText(modelName);
	}
}

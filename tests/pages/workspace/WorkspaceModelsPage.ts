import type { Page } from '@playwright/test';
import { WorkspacePage } from './WorkspacePage';

/**
 * Represents the workspace models page. The default page when the user clicks the workspace button.
 *
 * URL: /workspace/models
 */
export class WorkspaceModelsPage extends WorkspacePage {
	private createModelButton = this.getPageLocator('Models', 'CreateModelButton');
	// TODO more page elements etc.

	constructor(page: Page) {
		super(page);
	}

	/**
	 * Clicks the create model button.
	 *
	 * Page Object: ModelEditorPage
	 */
	async clickCreateModelButton(): Promise<void> {
		await this.createModelButton.click();
	}
}

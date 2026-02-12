import type { Locator, Page } from '@playwright/test';
import { BasePage } from '../BasePage';
import { testId } from '$lib/utils/testId';

export abstract class WorkspacePage extends BasePage {
	// helper functions to get test id and locator for the current page
	protected getPageTestId = (...args: string[]): string => {
		return testId('Workspace', ...args);
	};
	protected getPageLocator = (...args: string[]): Locator => {
		return this.page.getByTestId(this.getPageTestId(...args));
	};

	// page buttons along the top of the page
	private modelsPageButton = this.getPageLocator('PageButton', 'Models');
	private knowledgePageButton = this.getPageLocator('PageButton', 'Knowledge');
	private promptsPageButton = this.getPageLocator('PageButton', 'Prompts');
	private toolsPageButton = this.getPageLocator('PageButton', 'Tools');
	private metricsPageButton = this.getPageLocator('PageButton', 'Metrics');

	constructor(page: Page) {
		super(page);
	}

	/** WorkspaceModelsPage */
	async clickModelsPageButton(): Promise<void> {
		await this.modelsPageButton.click();
	}

	/** WorkspaceKnowledgePage */
	async clickKnowledgePageButton(): Promise<void> {
		await this.knowledgePageButton.click();
	}

	/** WorkspacePromptsPage */
	async clickPromptsPageButton(): Promise<void> {
		await this.promptsPageButton.click();
	}

	/** WorkspaceToolsPage */
	async clickToolsPageButton(): Promise<void> {
		await this.toolsPageButton.click();
	}

	/** WorkspaceMetricsPage */
	async clickMetricsPageButton(): Promise<void> {
		await this.metricsPageButton.click();
	}
}

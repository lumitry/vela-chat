import type { Locator, Page } from '@playwright/test';
import { expect } from '@playwright/test';
import { testId } from '$lib/utils/testId';
import { AdminSettingsPage } from './AdminSettingsPage';

/**
 * Represents the Admin Settings - Settings - Models page.
 *
 * URL: /admin/settings#models
 */
export class AdminSettingsModelsTab extends AdminSettingsPage {
	// helper functions to get test id and locator for the current page
	private getPageTestId = (...args: string[]): string => {
		return testId('AdminSettings', 'Models', ...args);
	};
	private getPageLocator = (...args: string[]): Locator => {
		return this.page.getByTestId(this.getPageTestId(...args));
	};

	//---------------//
	// Page Elements //
	//---------------//

	private modelCount = this.getPageLocator('ModelCount');
	/** Opens the Ollama model manager. Useless for us since we're using Mini-Mediator which does not support the endpoints this uses. */
	private manageModelsButton = this.getPageLocator('ManageModelsButton');
	private settingsButton = this.getPageLocator('SettingsButton');
	private searchInput = this.getPageLocator('SearchInput');
	private importPresetsInput = this.getPageLocator('ImportPresetsInput');
	private exportPresetsButton = this.getPageLocator('ExportPresetsButton');
	private importPresetsButton = this.getPageLocator('ImportPresetsButton');

	// -o-o-o- below are model-dependent locators! -o-o-o- //
	// -o- note that the model.id includes the prefix! -o- //
	private getModelItem = (modelId: string) => this.getPageLocator('ModelItem', modelId);
	private getModelItemButton = (modelId: string) => this.getPageLocator('ModelItemButton', modelId);
	private getModelItemImage = (modelId: string) => this.getPageLocator('ModelItemImage', modelId);
	private getModelItemName = (modelId: string) => this.getPageLocator('ModelItemName', modelId);
	private getModelItemDescription = (modelId: string) =>
		this.getPageLocator('ModelItemDescription', modelId);
	private getModelItemHideButton = (modelId: string) =>
		this.getPageLocator('ModelItemHideButton', modelId);
	private getModelItemEditButton = (modelId: string) =>
		this.getPageLocator('ModelItemEditButton', modelId);
	private getModelItemMenuButton = (modelId: string) =>
		this.getPageLocator('ModelItemMenuButton', modelId);
	private getModelItemToggleSwitch = (modelId: string) =>
		this.getPageLocator('ModelItemToggleSwitch', modelId);

	constructor(page: Page) {
		super(page);
	}

	async assertModelCount(count: number): Promise<void> {
		await expect(this.modelCount).toHaveText(count.toString());
	}

	/**
	 * Opens the settings modal.
	 *
	 * Page Object: ConfigureModelsModal
	 * TODO implement that modal! and write tests for reordering models, and setting defaults, and maybe also the reset button?
	 */
	async clickSettingsButton(): Promise<void> {
		await this.settingsButton.click();
	}

	/**
	 * Searches for a model by name. This input currently does not filter by ID, so we need to search by name.
	 *
	 * @param modelName The name of the model to search for.
	 */
	async searchForModel(modelName: string): Promise<void> {
		await this.searchInput.clear();
		await this.searchInput.fill(modelName);
	}

	/**
	 * Opens the model editor for the given model.
	 *
	 * Opens Page Object: {@link ModelEditorPage}
	 * (URL does not change for this page!)
	 *
	 * @param modelId The ID of the model to edit, including the prefix!
	 */
	async clickModelItemEditButton(modelId: string): Promise<void> {
		// clicking getModelItemButton would also work here, but this is clicking the edit button specifically
		await this.getModelItemEditButton(modelId).click();
	}

	async assertModelItemWithNameExists(modelId: string, modelName: string): Promise<void> {
		await expect(this.getModelItemName(modelId)).toHaveText(modelName);
	}

	// TODO: add more methods - hide model, toggle model, maybe preset import/export?
}

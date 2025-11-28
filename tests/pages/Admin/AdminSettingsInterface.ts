import { expect, type Locator, type Page } from '@playwright/test';
import { testId } from '$lib/utils/testId';
import { AdminSettingsPage } from './AdminSettingsPage';
import type { MiniMediatorModel } from '../../data/miniMediatorModels';

/**
 * Represents the Admin Settings - Settings - Interface page.
 *
 * This is the page when navigating to /admin/settings#interface.
 *
 * URL: /admin/settings#interface
 */
export class AdminSettingsInterfaceTab extends AdminSettingsPage {
	// helper functions to get test id and locator for the current page
	private getPageTestId = (...args: string[]): string => {
		return testId('AdminSettings', 'Interface', ...args);
	};
	private getPageLocator = (...args: string[]): Locator => {
		return this.page.getByTestId(this.getPageTestId(...args));
	};

	//---------------//
	// Page Elements //
	//---------------//

	private localTaskModelSelect = this.getPageLocator('LocalTaskModelSelect');
	private externalTaskModelSelect = this.getPageLocator('ExternalTaskModelSelect');
	private titleGenSwitch = this.getPageLocator('TitleGenSwitch');
	private titleGenPromptInput = this.getPageLocator('TitleGenPromptInput');
	private tagsGenSwitch = this.getPageLocator('TagsGenSwitch');
	private tagsGenPromptInput = this.getPageLocator('TagsGenPromptInput');
	private searchQueryGenSwitch = this.getPageLocator('SearchQueryGenSwitch');
	private ragQueryGenSwitch = this.getPageLocator('RagQueryGenSwitch');
	/** Used for both RAG and web search query generation */
	private queryGenPromptInput = this.getPageLocator('QueryGenPromptInput');
	private autocompleteGenSwitch = this.getPageLocator('AutocompleteGenSwitch');
	private autocompleteGenInputMaxLengthInput = this.getPageLocator(
		'AutocompleteGenInputMaxLengthInput'
	);
	private imagePromptGenPromptInput = this.getPageLocator('ImagePromptGenPromptInput');
	private toolsFunctionCallingPromptInput = this.getPageLocator('ToolsFunctionCallingPromptInput');

	private bannerDismissibleSwitch = this.getPageLocator('BannerDismissibleSwitch');

	//---------------//
	// Page Elements //
	//---------------//

	constructor(page: Page) {
		super(page);
	}

	async setLocalTaskModel(model: MiniMediatorModel): Promise<void> {
		await this.localTaskModelSelect.selectOption({ value: model.getFullIdWithEndpointPrefix() });
	}

	async setExternalTaskModel(model: MiniMediatorModel): Promise<void> {
		await this.externalTaskModelSelect.selectOption({ value: model.getFullIdWithEndpointPrefix() });
	}

	//--------------------------------//
	// Title Generation Settings     //
	//--------------------------------//

	async setTitleGenSwitch(enabled: boolean): Promise<void> {
		await this.titleGenSwitch.setChecked(enabled);
	}

	async setTitleGenPromptTemplate(template: string): Promise<void> {
		await this.titleGenPromptInput.fill(template);
	}

	async getTitleGenPromptTemplate(): Promise<string> {
		return await this.titleGenPromptInput.inputValue();
	}

	async assertTitleGenPromptTemplate(template: string): Promise<void> {
		await expect(this.titleGenPromptInput).toHaveText(template);
	}

	//--------------------------------//
	// Tags Generation Settings     //
	//--------------------------------//

	async setTagsGenSwitch(enabled: boolean): Promise<void> {
		await this.tagsGenSwitch.setChecked(enabled);
	}

	async setTagsGenPromptTemplate(template: string): Promise<void> {
		await this.tagsGenPromptInput.fill(template);
	}

	async getTagsGenPromptTemplate(): Promise<string> {
		return await this.tagsGenPromptInput.inputValue();
	}

	async assertTagsGenPromptTemplate(template: string): Promise<void> {
		await expect(this.tagsGenPromptInput).toHaveText(template);
	}

	//---------------------------------------//
	//      Retrieval Query Generation       //
	//---------------------------------------//

	/**
	 * Sets whether to enable retrieval query generation.
	 *
	 * @param enabled - Whether to enable retrieval query generation.
	 */
	async setRetrievalQueryGenSwitch(enabled: boolean): Promise<void> {
		await this.ragQueryGenSwitch.setChecked(enabled);
	}

	/**
	 * Sets whether to enable web search query generation.
	 *
	 * @param enabled - Whether to enable web search query generation.
	 */
	async setSearchQueryGenSwitch(enabled: boolean): Promise<void> {
		await this.searchQueryGenSwitch.setChecked(enabled);
	}

	/**
	 * Sets the prompt template for retrieval & web search query generation.
	 *
	 * @param template - The prompt template for retrieval & web search query generation.
	 */
	async setRetrievalQueryGenPromptTemplate(template: string): Promise<void> {
		await this.queryGenPromptInput.fill(template);
	}

	/**
	 * Gets the prompt template for retrieval & web search query generation.
	 *
	 * @returns The prompt template for retrieval & web search query generation.
	 */
	async getRetrievalQueryGenPromptTemplate(): Promise<string> {
		return await this.queryGenPromptInput.inputValue();
	}

	/**
	 * Asserts that the prompt template for retrieval & web search query generation is correct.
	 *
	 * @param template - The prompt template for retrieval & web search query generation.
	 */
	async assertRetrievalQueryGenPromptTemplate(template: string): Promise<void> {
		await expect(this.queryGenPromptInput).toHaveText(template);
	}

	//---------------------------------------//
	//      Autocomplete Generation       //
	//---------------------------------------//

	async setAutocompleteGenSwitch(enabled: boolean): Promise<void> {
		await this.autocompleteGenSwitch.setChecked(enabled);
	}

	async setAutocompleteGenInputMaxLength(length: number): Promise<void> {
		await this.autocompleteGenInputMaxLengthInput.fill(length.toString());
	}

	async getAutocompleteGenInputMaxLength(): Promise<number> {
		const value = await this.autocompleteGenInputMaxLengthInput.inputValue();
		return Number(value);
	}

	async assertAutocompleteGenInputMaxLength(length: number): Promise<void> {
		const value = await this.getAutocompleteGenInputMaxLength();
		expect(value).toBe(length);
	}

	//---------------------------------------//
	//      Image Prompt Generation       //
	//---------------------------------------//

	// there is no switch for this, it's always enabled

	async setImagePromptGenPromptTemplate(template: string): Promise<void> {
		await this.imagePromptGenPromptInput.fill(template);
	}

	async getImagePromptGenPromptTemplate(): Promise<string> {
		return await this.imagePromptGenPromptInput.inputValue();
	}

	async assertImagePromptGenPromptTemplate(template: string): Promise<void> {
		await expect(this.imagePromptGenPromptInput).toHaveText(template);
	}

	//---------------------------------------//
	//      Tools Function Calling       //
	//---------------------------------------//

	// there is no switch for this, it's always enabled

	async setToolsFunctionCallingPromptTemplate(template: string): Promise<void> {
		await this.toolsFunctionCallingPromptInput.fill(template);
	}

	async getToolsFunctionCallingPromptTemplate(): Promise<string> {
		return await this.toolsFunctionCallingPromptInput.inputValue();
	}

	async assertToolsFunctionCallingPromptTemplate(template: string): Promise<void> {
		await expect(this.toolsFunctionCallingPromptInput).toHaveText(template);
	}

	/**
	 * Asserts that the model option exists in the local or external task model select.
	 *
	 * @param provider - The provider of the model.
	 * @param modelName - The user-facing name of the model. (NOT the model ID!)
	 */
	async assertModelOptionExists(provider: 'ollama' | 'openai', modelName: string): Promise<void> {
		const selectLocator =
			provider === 'openai' ? this.externalTaskModelSelect : this.localTaskModelSelect;
		const optionLocator = selectLocator.locator('option', { hasText: modelName });
		await expect(optionLocator).toHaveText(modelName); // toBeVisible doesn't work because the select dropdown is not open, so we have to do a redundant check with toHaveText
	}

	// TODO: add more methods?
	// TODO banners
}

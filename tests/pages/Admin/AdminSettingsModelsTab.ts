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

	async assertModelItemWithDescriptionExists(
		modelId: string,
		modelDescription: string
	): Promise<void> {
		await expect(this.getModelItemDescription(modelId)).toHaveText(modelDescription);
	}

	/**
	 * Asserts that the model's image src attribute matches the expected URL or pattern.
	 *
	 * @param modelId - The ID of the model, including the prefix!
	 * @param expectedImageUrl - The expected image URL. Can be:
	 *   - An exact URL string (e.g., '/static/favicon.png')
	 *   - A regex pattern (e.g., /\/api\/v1\/files\/.*\/content/)
	 *   - A function that returns a boolean (for custom validation)
	 */
	async assertModelItemWithImageExists(
		modelId: string,
		expectedImageUrl: string | RegExp | ((url: string) => boolean)
	): Promise<void> {
		const imageLocator = this.getModelItemImage(modelId);

		if (typeof expectedImageUrl === 'string') {
			// Exact URL match
			await expect(imageLocator).toHaveAttribute('src', expectedImageUrl);
		} else if (expectedImageUrl instanceof RegExp) {
			// Regex pattern match
			await expect(imageLocator).toHaveAttribute('src', expectedImageUrl);
		} else {
			// Custom function validation
			const actualSrc = await imageLocator.getAttribute('src');
			expect(actualSrc).not.toBeNull();
			expect(expectedImageUrl(actualSrc!)).toBe(true);
		}
	}

	/**
	 * Asserts that the model's image is NOT the default favicon.
	 *
	 * @param modelId - The ID of the model, including the prefix!
	 * @param defaultImageUrl - The default image URL to check against (defaults to '/static/favicon.png')
	 */
	async assertModelItemImageIsNotDefault(
		modelId: string,
		defaultImageUrl: string = '/static/favicon.png'
	): Promise<void> {
		const imageLocator = this.getModelItemImage(modelId);
		await expect(imageLocator).not.toHaveAttribute('src', defaultImageUrl);
	}

	/**
	 * Gets the image src URL for a model.
	 *
	 * @param modelId - The ID of the model, including the prefix!
	 * @returns The image src URL, or null if not found
	 */
	async getModelItemImageUrl(modelId: string): Promise<string | null> {
		const imageLocator = this.getModelItemImage(modelId);
		return await imageLocator.getAttribute('src');
	}

	/**
	 * Waits for the model's image to be saved (URL changes from data: or default to file URL).
	 * This should be called after saving a model with a new image to wait for the backend to process it.
	 *
	 * @param modelId - The ID of the model, including the prefix!
	 * @param defaultImageUrl - The default image URL to exclude (defaults to '/static/favicon.png')
	 * @param timeout - Maximum time to wait in milliseconds (default: 10000ms)
	 * @returns The saved image file URL
	 */
	async waitForModelImageToBeSaved(
		modelId: string,
		defaultImageUrl: string = '/static/favicon.png',
		timeout: number = 10000
	): Promise<string> {
		const startTime = Date.now();
		while (Date.now() - startTime < timeout) {
			const imageUrl = await this.getModelItemImageUrl(modelId);
			if (
				imageUrl &&
				!imageUrl.startsWith('data:') &&
				imageUrl !== defaultImageUrl &&
				imageUrl.includes('/api/v1/files/')
			) {
				// Image has been saved - it's now a file URL
				return imageUrl;
			}
			await this.page.waitForTimeout(200);
		}
		const currentUrl = await this.getModelItemImageUrl(modelId);
		throw new Error(`Model image was not saved within ${timeout}ms. Current URL: ${currentUrl}`);
	}

	/**
	 * Asserts that the model's image URL matches the uploaded file pattern.
	 * This checks that the image is a file URL (e.g., /api/v1/files/{id}/content) and not the default.
	 *
	 * @param modelId - The ID of the model, including the prefix!
	 * @param defaultImageUrl - The default image URL to exclude (defaults to '/static/favicon.png')
	 */
	async assertModelItemImageIsUploaded(
		modelId: string,
		defaultImageUrl: string = '/static/favicon.png'
	): Promise<void> {
		const imageLocator = this.getModelItemImage(modelId);
		const actualSrc = await imageLocator.getAttribute('src');

		expect(actualSrc).not.toBeNull();
		expect(actualSrc).not.toBe(defaultImageUrl);
		// Check that it's a file URL (either /api/v1/files/... or data:... or absolute URL)
		expect(actualSrc).toMatch(/\/api\/v1\/files\/.*\/content|data:image|https?:\/\//);
	}

	/**
	 * Asserts that the model's image content matches the expected image file.
	 * This fetches the actual image from the URL and compares it byte-by-byte to the expected image.
	 *
	 * @param modelId - The ID of the model, including the prefix!
	 * @param expectedImageBuffer - The expected image content as a Buffer
	 * @param defaultImageUrl - The default image URL (defaults to '/static/favicon.png'). If the image is the default, this will fail.
	 */
	async assertModelItemImageContentMatches(
		modelId: string,
		expectedImageBuffer: Buffer,
		defaultImageUrl: string = '/static/favicon.png'
	): Promise<void> {
		const imageLocator = this.getModelItemImage(modelId);
		const actualSrc = await imageLocator.getAttribute('src');

		expect(actualSrc).not.toBeNull();
		expect(actualSrc).not.toBe(defaultImageUrl);

		// Fetch the actual image content
		let actualImageBuffer: Buffer;

		if (actualSrc!.startsWith('data:')) {
			// Handle data URLs (base64 encoded)
			const base64Data = actualSrc!.split(',')[1];
			actualImageBuffer = Buffer.from(base64Data, 'base64');
		} else {
			// Handle file URLs (relative or absolute)
			// Convert relative URLs to absolute using URL constructor
			const baseUrl = this.page.url();
			const imageUrl = actualSrc!.startsWith('http')
				? actualSrc!
				: new URL(actualSrc!, baseUrl).toString();

			// Fetch the image
			const response = await this.page.request.get(imageUrl);
			expect(response.ok()).toBe(true);
			actualImageBuffer = await response.body();
		}

		// Compare the image buffers
		expect(
			actualImageBuffer.equals(expectedImageBuffer),
			`Image content mismatch for model ${modelId}`
		).toBe(true);
	}

	// TODO: add more methods - hide model, toggle model, maybe preset import/export?
}

import type { Locator, Page } from '@playwright/test';
import { WorkspacePage } from './WorkspacePage';
import { testId } from '$lib/utils/testId';
import { expect } from '@playwright/test';

/**
 * Represents the workspace models page. The default page when the user clicks the workspace button.
 *
 * URL: /workspace/models
 */
export class WorkspaceModelsPage extends WorkspacePage {
	// helper methods to get test id and locator for the current page
	protected getPageTestId = (...args: string[]): string => {
		return testId('Workspace', 'Models', ...args);
	};
	protected getPageLocator = (...args: string[]): Locator => {
		return this.page.getByTestId(this.getPageTestId(...args));
	};

	private createModelButton = this.getPageLocator('CreateModelButton');
	private getModelItem = (modelId: string) => this.getPageLocator('ModelItem', modelId);
	/** Clicking opens model editor page. */
	private getModelItemButton = (modelId: string) => this.getPageLocator('ModelItemButton', modelId);
	/** Clicking opens model editor page. */
	private getModelItemEditButton = (modelId: string) =>
		this.getPageLocator('ModelItemEditButton', modelId);
	/** Opens a dropdown that currently lacks a dedicated component with options: share, clone, export, or delete. */
	private getModelItemMenuButton = (modelId: string) =>
		this.getPageLocator('ModelItemMenuButton', modelId);
	/** Toggles whether the model is included in model list endpoint. */
	private getModelItemToggleSwitch = (modelId: string) =>
		this.getPageLocator('ModelItemToggleSwitch', modelId);
	/** The name of the model. */
	private getModelItemName = (modelId: string) => this.getPageLocator('ModelItemName', modelId);
	/** The image of the model. */
	private getModelItemImage = (modelId: string) => this.getPageLocator('ModelItemImage', modelId);
	/** The description of the model, or the model ID if no description is set. */
	private getModelItemDescription = (modelId: string) =>
		this.getPageLocator('ModelItemDescription', modelId);

	// model item menu button options
	private getModelItemShareButton = (modelId: string) =>
		this.getPageLocator('ModelItemShareButton', modelId);
	private getModelItemCloneButton = (modelId: string) =>
		this.getPageLocator('ModelItemCloneButton', modelId);
	private getModelItemExportButton = (modelId: string) =>
		this.getPageLocator('ModelItemExportButton', modelId);
	private getModelItemDeleteButton = (modelId: string) =>
		this.getPageLocator('ModelItemDeleteButton', modelId);

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

	/**
	 * Clicks the model item edit button.
	 *
	 * Page Object: ModelEditorPage
	 */
	async clickModelItemEditButton(modelId: string): Promise<void> {
		await this.getModelItemEditButton(modelId).click();
	}

	/**
	 * Asserts that a model with the given ID and name exists in the model list.
	 * @param modelId - The ID of the model to assert.
	 * @param modelName - The name of the model to assert.
	 * @param modelDescription - The description of the model to assert, or null if no description is set (meaning the model ID is shown instead).
	 */
	async assertModelExists(
		modelId: string,
		modelName: string,
		modelDescription: string | null
	): Promise<void> {
		await expect(this.getModelItem(modelId)).toBeVisible();
		await expect(this.getModelItemName(modelId)).toHaveText(modelName);
		if (modelDescription) {
			await expect(this.getModelItemDescription(modelId)).toHaveText(modelDescription);
		} else {
			await expect(this.getModelItemDescription(modelId)).toHaveText(modelId);
		}
	}

	async getModelName(modelId: string): Promise<string> {
		return (await this.getModelItemName(modelId).textContent()) ?? '';
	}
	async getModelDescription(modelId: string): Promise<string | null> {
		return (await this.getModelItemDescription(modelId).textContent()) ?? null;
	}

	async getModelsOnPage(): Promise<{ id: string; name: string; description: string | null }[]> {
		const models = await this.page.locator('[id^="model-item"]').all();
		const results = await Promise.all(
			models.map(async (model) => {
				const id = (await model.getAttribute('data-testid'))?.split('-').pop() ?? '';
				return {
					id: id,
					name: await this.getModelName(id),
					description: await this.getModelDescription(id)
				};
			})
		);
		return results;
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
	 * @param previousImageUrl - The previous image URL to exclude (optional)
	 * @param timeout - Maximum time to wait in milliseconds (default: 10000ms)
	 * @returns The saved image file URL
	 */
	async waitForModelImageToBeSaved(
		modelId: string,
		previousImageUrl?: string,
		timeout: number = 10000
	): Promise<string> {
		const startTime = Date.now();
		while (Date.now() - startTime < timeout) {
			const imageUrl = await this.getModelItemImageUrl(modelId);
			if (
				imageUrl &&
				!imageUrl.startsWith('data:') &&
				imageUrl !== previousImageUrl &&
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
	 * Asserts that the model's image content matches the expected image file.
	 * This fetches the actual image from the URL and compares it byte-by-byte to the expected image.
	 *
	 * @param modelId - The ID of the model, including the prefix!
	 * @param expectedImageBuffer - The expected image content as a Buffer
	 */
	async assertModelItemImageContentMatches(
		modelId: string,
		expectedImageBuffer: Buffer
	): Promise<void> {
		const imageLocator = this.getModelItemImage(modelId);
		const actualSrc = await imageLocator.getAttribute('src');

		expect(actualSrc).not.toBeNull();

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

	/**
	 * Gets the disabled state for the given model.
	 *
	 * @param modelId - The ID of the model, including the prefix!
	 * @returns True if the model is **disabled**, false if it is enabled.
	 */
	async getModelItemDisabledState(modelId: string): Promise<boolean> {
		const element = this.getModelItemToggleSwitch(modelId);
		return await element.evaluate((el) => {
			return el.getAttribute('data-state') === 'unchecked'; // unchecked = disabled -> return true because isDisabled
		});
	}

	/**
	 * Asserts that the model's disabled state matches the expected value.
	 *
	 * @param modelId - The ID of the model, including the prefix!
	 * @param disabledState - The expected disabled state.
	 */
	async assertModelItemDisabledState(modelId: string, disabledState: boolean): Promise<void> {
		expect(await this.getModelItemDisabledState(modelId)).toBe(disabledState);
	}

	/**
	 * Sets the disabled state for the given model.
	 *
	 * @param modelId - The ID of the model, including the prefix!
	 * @param disabledState - The disabled state to set.
	 */
	async setModelItemDisabledState(modelId: string, disabledState: boolean): Promise<void> {
		const currentDisabledState = await this.getModelItemDisabledState(modelId);

		if (disabledState !== currentDisabledState) {
			const element = this.getModelItemToggleSwitch(modelId);
			await element.click();
		}
	}

	/**
	 * Clicks the model item menu button (the three-dot menu) and waits for the menu to open.
	 *
	 * @param modelId - The ID of the model, including the prefix!
	 */
	async clickModelItemMenuButton(modelId: string): Promise<void> {
		await this.getModelItemMenuButton(modelId).click();
		// Wait for the menu to be visible by waiting for one of the menu items
		await this.getModelItemCloneButton(modelId).waitFor({ state: 'visible', timeout: 5000 });
	}

	/**
	 * Clicks the clone menu item from the model menu dropdown.
	 *
	 * @param modelId - The ID of the model, including the prefix!
	 */
	async clickCloneMenuItem(modelId: string): Promise<void> {
		await this.getModelItemCloneButton(modelId).click();
	}

	/**
	 * Clicks the delete menu item from the model menu dropdown.
	 *
	 * @param modelId - The ID of the model, including the prefix!
	 */
	async clickDeleteMenuItem(modelId: string): Promise<void> {
		await this.getModelItemDeleteButton(modelId).click();
	}

	/**
	 * Confirms the delete action (e.g., clicks confirm button in a confirmation dialog).
	 */
	async confirmDelete(): Promise<void> {
		await this.clickConfirmDialogConfirmButton();
	}

	/**
	 * Asserts that a model with the given ID does not exist in the model list.
	 *
	 * @param modelId - The ID of the model to assert does not exist.
	 */
	async assertModelDoesNotExist(modelId: string): Promise<void> {
		await expect(this.getModelItem(modelId)).not.toBeVisible();
	}
}

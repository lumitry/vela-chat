import { expect, type Page } from '@playwright/test';
import { testId } from '$lib/utils/testId';
import { Dropdown } from './Dropdown';

/**
 * Represents the Model Selector dropdown component.
 *
 * This selector appears in the chat page navbar and allows users to select models.
 *
 * The model selector does not technically need to be opened to use some of these methods. Methods that do not require the model selector to be open are marked as such in their docstring.
 *
 * Methods that DO require the model selector to be open are NOT marked as such! That much should be assumed by default, and the others are exceptions, not the rule.
 *
 * Extends Dropdown to provide both convenience methods (selectModel(), assertCurrentModelName(), etc.)
 * and generic dropdown functionality (clickOptionByText(), assertOptionExists(), etc.).
 *
 * @example
 * ```typescript
 * // Convenience methods (better DX)
 * await modelSelector.open();
 * await modelSelector.selectModel('openai:gpt-4');
 * await modelSelector.assertCurrentModelName('GPT-4');
 *
 * // Generic dropdown methods (more flexible)
 * await modelSelector.clickOptionByText('GPT-4');
 * await modelSelector.assertOptionExists('GPT-4');
 * ```
 */
export class ModelSelector extends Dropdown {
	private modelSelectorTrigger: ReturnType<Page['getByTestId']>;
	private modelSelectorTriggerCurrentModelName: ReturnType<Page['getByTestId']>;
	private getModelSelectorModelItem: (modelId: string) => ReturnType<Page['getByTestId']>;
	private getModelSelectorModelImage: (modelId: string) => ReturnType<Page['getByTestId']>;
	private getModelSelectorModelName: (modelId: string) => ReturnType<Page['getByTestId']>;
	private getModelSelectorModelDescription: (modelId: string) => ReturnType<Page['getByTestId']>;
	/** Only for Ollama models. Currently mini-mediator doesn't support this anyway. */
	private getModelSelectorModelParameterSize: (modelId: string) => ReturnType<Page['getByTestId']>;

	constructor(page: Page, containerTestIdPrefix: string[] = ['Chat', 'ModelSelector']) {
		// The dropdown content appears when the selector is opened
		// We need to find the dropdown content - it's typically in a DropdownMenu.Content
		// For now, we'll use a more generic locator that should work
		const dropdownContainer = page.locator('[role="menu"]').first();
		super(dropdownContainer);

		// Initialize locators using test IDs
		this.modelSelectorTrigger = page.getByTestId(
			testId(...containerTestIdPrefix, 'Selector', 'Trigger')
		);
		this.modelSelectorTriggerCurrentModelName = page.getByTestId(
			testId(...containerTestIdPrefix, 'Selector', 'Trigger', 'CurrentModelName')
		);
		this.getModelSelectorModelItem = (modelId: string) =>
			page.getByTestId(testId(...containerTestIdPrefix, 'ModelItem', modelId));
		this.getModelSelectorModelImage = (modelId: string) =>
			page.getByTestId(testId(...containerTestIdPrefix, 'ModelImage', modelId));
		this.getModelSelectorModelName = (modelId: string) =>
			page.getByTestId(testId(...containerTestIdPrefix, 'ModelName', modelId));
		this.getModelSelectorModelDescription = (modelId: string) =>
			page.getByTestId(testId(...containerTestIdPrefix, 'ModelDescription', modelId));
		this.getModelSelectorModelParameterSize = (modelId: string) =>
			page.getByTestId(testId(...containerTestIdPrefix, 'ModelParameterSize', modelId));
	}

	/**
	 * Clicks the model selector trigger (the model name & chevron) to open the model selector.
	 *
	 * The model selector should be closed before calling this method.
	 */
	async open(): Promise<void> {
		await this.modelSelectorTrigger.click();
		// Wait for dropdown to be visible
		await this.container.waitFor({ state: 'visible', timeout: 2000 }).catch(() => {
			// Dropdown might already be visible or might not use standard visibility
		});
	}

	/**
	 * Asserts that the current model name on the model selector trigger matches the expected model name.
	 *
	 * The model selector does not need to be open to call this method.
	 *
	 * TODO: support for multiple models!
	 *
	 * @param modelName - The expected model name.
	 */
	async assertCurrentModelName(modelName: string): Promise<void> {
		await expect(this.modelSelectorTriggerCurrentModelName).toHaveText(modelName);
	}

	/**
	 * Asserts that the model name exists in the model selector.
	 *
	 * @param modelId - The ID of the model.
	 * @param modelName - The name of the model.
	 */
	async assertModelNameExists(modelId: string, modelName: string): Promise<void> {
		await expect(this.getModelSelectorModelName(modelId)).toHaveText(modelName);
	}

	/**
	 * Selects a model from the model selector.
	 *
	 * Closes the model selector if it is open.
	 *
	 * @param modelId - The ID of the model.
	 */
	async selectModel(modelId: string): Promise<void> {
		await this.getModelSelectorModelItem(modelId).click();
		// Wait for dropdown to close after selection
		await this.container.waitFor({ state: 'hidden', timeout: 2000 }).catch(() => {
			// Dropdown might close immediately or might not use standard visibility
		});
	}

	/**
	 * Asserts that the model description exists in the model selector.
	 *
	 * @param modelId - The ID of the model.
	 * @param modelDescription - The description of the model. If null, asserts that the description element does not exist.
	 */
	async assertModelDescription(modelId: string, modelDescription: string | null): Promise<void> {
		if (modelDescription === null) {
			await expect(this.getModelSelectorModelDescription(modelId)).not.toBeVisible();
		} else {
			await expect(this.getModelSelectorModelDescription(modelId)).toHaveAttribute(
				'aria-label',
				`<p>${modelDescription}</p>\n`
			);
		}
	}

	/**
	 * Asserts that the model's image src attribute matches the expected URL or pattern.
	 *
	 * @param modelId - The ID of the model.
	 * @param expectedImageUrl - The expected image URL. Can be:
	 *   - An exact URL string (e.g., '/static/favicon.png')
	 *   - A regex pattern (e.g., /\/api\/v1\/files\/.*\/content/)
	 *   - A function that returns a boolean (for custom validation)
	 */
	async assertModelImage(
		modelId: string,
		expectedImageUrl: string | RegExp | ((url: string) => boolean)
	): Promise<void> {
		const imageLocator = this.getModelSelectorModelImage(modelId);

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
	 * @param modelId - The ID of the model.
	 * @param defaultImageUrl - The default image URL to check against (defaults to '/static/favicon.png')
	 */
	async assertModelImageIsNotDefault(
		modelId: string,
		defaultImageUrl: string = '/static/favicon.png'
	): Promise<void> {
		const imageLocator = this.getModelSelectorModelImage(modelId);
		await expect(imageLocator).not.toHaveAttribute('src', defaultImageUrl);
	}

	/**
	 * Asserts that the model's image URL matches the uploaded file pattern.
	 * This checks that the image is a file URL (e.g., /api/v1/files/{id}/content) and not the default.
	 *
	 * @param modelId - The ID of the model.
	 * @param defaultImageUrl - The default image URL to exclude (defaults to '/static/favicon.png')
	 */
	async assertModelImageIsUploaded(
		modelId: string,
		defaultImageUrl: string = '/static/favicon.png'
	): Promise<void> {
		const imageLocator = this.getModelSelectorModelImage(modelId);
		const actualSrc = await imageLocator.getAttribute('src');

		expect(actualSrc).not.toBeNull();
		expect(actualSrc).not.toBe(defaultImageUrl);
		// Check that it's a file URL (either /api/v1/files/... or data:... or absolute URL)
		expect(actualSrc).toMatch(/\/api\/v1\/files\/.*\/content|data:image|https?:\/\//);
	}
}

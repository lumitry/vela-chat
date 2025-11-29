import { expect, type Locator, type Page } from '@playwright/test';
import { testId } from '$lib/utils/testId';
import { Dropdown } from './Dropdown';

/**
 * Represents the Model Selector dropdown component.
 *
 * This selector appears in the chat page navbar and allows users to select models.
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
		this.getModelSelectorModelParameterSize = (modelId: string) =>
			page.getByTestId(testId(...containerTestIdPrefix, 'ModelParameterSize', modelId));
	}

	/**
	 * Clicks the model selector trigger (the model name & chevron) to open the model selector.
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
	 * The model selector must be open before calling this method.
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
	 * The model selector must be open before calling this method.
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
}

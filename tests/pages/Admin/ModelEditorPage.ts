import type { Locator, Page } from '@playwright/test';
import { BasePage } from '../BasePage';
import { expect } from '@playwright/test';
import { testId } from '$lib/utils/testId';

/**
 * Represents the model editor page.
 * No specific URL. Accessed from the admin settings models tab and the workspace models tab.
 */
export class ModelEditorPage extends BasePage {
	private getPageTestId = (...args: string[]): string => {
		// not using Admin or Workspace here since this page is accessed from both!
		return testId('ModelEditor', ...args);
	};
	private getPageLocator = (...args: string[]): Locator => {
		return this.page.getByTestId(this.getPageTestId(...args));
	};

	//-----------------------//
	// General Page Elements //
	//-----------------------//

	private profileImageInput = this.getPageLocator('ProfileImageInput');
	private resetImageButton = this.getPageLocator('ResetImageButton');
	private nameInput = this.getPageLocator('NameInput');
	private descriptionToggleButton = this.getPageLocator('DescriptionToggleButton');
	private descriptionTextarea = this.getPageLocator('DescriptionTextarea');
	private systemPromptTextarea = this.getPageLocator('SystemPromptTextarea');
	private advancedParamsToggleButton = this.getPageLocator('AdvancedParamsToggleButton');

	/** The Advanced Parameters section, not a specific input/element.
	 * TODO: create a AdvancedParams common component object and add it as a property/field to this class! similar to how UserMenu is attached to BasePage!
	 * we already have testIds for advanced params!
	 */
	private advancedParams = this.getPageLocator('AdvancedParams');

	// this stuff isn't supported by testIds yet, but we should add it!
	private suggestionPromptsToggleButton = this.getPageLocator('SuggestionPromptsToggleButton');
	private suggestionPrompts = this.getPageLocator('SuggestionPrompts');
	private knowledge = this.getPageLocator('Knowledge');
	private toolsSelector = this.getPageLocator('ToolsSelector');
	private filtersSelector = this.getPageLocator('FiltersSelector');
	private actionsSelector = this.getPageLocator('ActionsSelector');

	// back to supported stuff...
	// Capabilities section
	private visionCapabilityCheckbox = this.getPageLocator('Capabilities', 'Vision', 'Checkbox');
	private usageCapabilityCheckbox = this.getPageLocator('Capabilities', 'Usage', 'Checkbox');
	private citationsCapabilityCheckbox = this.getPageLocator(
		'Capabilities',
		'Citations',
		'Checkbox'
	);
	private verbosityCapabilityCheckbox = this.getPageLocator(
		'Capabilities',
		'Verbosity',
		'Checkbox'
	);

	// Model Details section (pricing & reasoning behavior)
	private modelDetailsToggleButton = this.getPageLocator('ModelDetailsToggleButton');
	/// pricing section
	private fetchFromOpenRouterButton = this.getPageLocator('FetchFromOpenRouterButton');
	private pricePer1MInputTokensInput = this.getPageLocator('PricePer1MInputTokensInput');
	private pricePer1MOutputTokensInput = this.getPageLocator('PricePer1MOutputTokensInput');
	private maxContextLengthInput = this.getPageLocator('MaxContextLengthInput');
	private pricePer1KImagesInput = this.getPageLocator('PricePer1KImagesInput');
	/// reasoning behavior section (many of these are conditional based on the reasoning behavior selected)
	private reasoningBehaviorSelect = this.getPageLocator('ReasoningBehaviorSelect');
	private reasoningTargetModelSelect = this.getPageLocator('ReasoningTargetModelSelect');
	private reasoningMaxTokensInput = this.getPageLocator('ReasoningMaxTokensInput');

	// other stuff at end of page
	private jsonPreviewToggleButton = this.getPageLocator('JSONPreviewToggleButton');
	private jsonPreviewTextarea = this.getPageLocator('JSONPreviewTextarea');
	private submitButton = this.getPageLocator('SubmitButton');

	//-------------------------//
	// Workspace-Only Elements //
	//-------------------------//

	/**
	 * This input is only visible in the workspace model editor, specifically when creating a NEW workspace model.
	 *
	 * It does not appear when editing an existing workspace model.
	 */
	private idInput = this.getPageLocator('IdInput');

	/** Selects the base model for the workspace model. */
	private baseModelSelect = this.getPageLocator('BaseModelSelect');

	constructor(page: Page) {
		super(page);
		// TODO: create a Tags component object and add it as a property here
		//  we already have testIds for tags!
		// TODO also make sure we do testing for model tags!

		// TODO: create a AccessControl component object and add it as a property here
		//  we already have testIds for access control!
		// TODO also make sure we do testing for access control!

		// TODO: create a Knowledge component object?? and add it as a property here
		// TODO also make sure we do testing for knowledge!

		// TODO: create a ToolsSelector component object?? and add it as a property here
		// TODO also make sure we do testing for tools!

		// TODO: create a FiltersSelector component object?? and add it as a property here
		// TODO also make sure we do testing for filters!

		// TODO: create a ActionsSelector component object?? and add it as a property here
		// TODO also make sure we do testing for actions!
	}

	// ---------------- //
	//   CRUD Methods   //
	// ---------------- //

	/**
	 * Uploads a profile image for the model.
	 * @param file - A file object with the image content as a Buffer.
	 * @example
	 *
	 * import { readFileSync } from 'fs';
	 * import { join } from 'path';
	 *
	 * const imageBuffer = readFileSync(join(__dirname, '../fixtures/test-image.png'));
	 * await modelEditor.setModelImage({
	 *     name: 'test-image.png',
	 *     mimeType: 'image/png',
	 *     buffer: imageBuffer
	 * });
	 *  */
	async setModelImage(file: { name: string; mimeType: string; buffer: Buffer }): Promise<void> {
		// TODO this is untested atm. no clue if it works
		await this.profileImageInput.setInputFiles([
			{
				name: file.name,
				buffer: file.buffer,
				mimeType: file.mimeType
			}
		]);
	}

	/**
	 * Resets the image to the default favicon.png.
	 */
	async clickResetImageButton(): Promise<void> {
		await this.resetImageButton.click();
	}

	/**
	 * Sets the model's name.
	 * @param name - The name to set.
	 */
	async setName(name: string): Promise<void> {
		await this.nameInput.fill(name);
	}

	/**
	 * Gets the text of the description toggle button. Either 'Default' or 'Custom'.
	 * @returns The text of the description toggle button.
	 */
	async getDescriptionToggleButtonText(): Promise<string> {
		return (await this.descriptionToggleButton.textContent()) ?? '';
	}

	/**
	 * Sets the model's description. If the description is set to 'default', it will be set to 'custom' before trying to set the description.
	 *
	 * @param description - The description to set.
	 */
	async setDescription(description: string): Promise<void> {
		if ((await this.getDescriptionToggleButtonText()) === 'Default') {
			await this.descriptionToggleButton.click();
		}
		await this.descriptionTextarea.fill(description);
	}

	async setSystemPrompt(systemPrompt: string): Promise<void> {
		await this.systemPromptTextarea.fill(systemPrompt);
	}

	/**
	 * Sets the model's 'capabilities' - e.g. whether it supports vision (multimodal), usage tracking, citations, and verbosity.
	 *
	 * Default values in UI are false, true, true, false.
	 *
	 * Default values for new models that haven't been touched by UI yet are false, false, true, false.
	 *
	 * (The difference being usage tracking is only enabled by default if you open the model editor and save the model because of a hack I put into the frontend code.)
	 *
	 * @param capabilities - The capabilities to set.
	 */
	async setCapabilities(capabilities: {
		vision?: boolean;
		usage?: boolean;
		citations?: boolean;
		verbosity?: boolean;
	}): Promise<void> {
		await this.visionCapabilityCheckbox.setChecked(capabilities.vision ?? false);
		await this.usageCapabilityCheckbox.setChecked(capabilities.usage ?? false);
		await this.citationsCapabilityCheckbox.setChecked(capabilities.citations ?? false);
		await this.verbosityCapabilityCheckbox.setChecked(capabilities.verbosity ?? false);
	}

	/** Saves the model and navigates back to the previous page.
	 *
	 * Clicks the Save & Update button (or Save & Create button if creating a new workspace model).
	 * After saving, the page automatically navigates back to where you came from.
	 */
	async saveAndReturn(): Promise<void> {
		await this.submitButton.click();
	}

	/**
	 * Checks if the model editor is for a workspace model by checking if the base model select is visible.
	 *
	 * @returns True if the model editor is for a workspace model, false otherwise.
	 */
	async getIsWorkspaceModel(): Promise<boolean> {
		return await this.baseModelSelect.isVisible();
	}

	async assertIsWorkspaceModel(): Promise<void> {
		expect(await this.getIsWorkspaceModel()).toBe(true);
	}

	/**
	 * Checks if the model editor is for a new workspace model by checking if the id input is editable.
	 *
	 * @returns True if the model editor is for a new workspace model, false otherwise.
	 */
	async getIsCreateWorkspaceModel(): Promise<boolean> {
		return await this.idInput.isEditable();
	}

	async assertIsCreateWorkspaceModel(): Promise<void> {
		expect(await this.getIsCreateWorkspaceModel()).toBe(true);
	}
}

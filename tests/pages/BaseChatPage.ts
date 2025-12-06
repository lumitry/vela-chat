import type { Locator, Page } from '@playwright/test';
import { BasePage } from './BasePage';
import { ModelSelector } from '../components/ModelSelector';
import { testId } from '$lib/utils/testId';
import { expect } from '@playwright/test';

/**
 * Represents a user message and its associated response message IDs.
 *
 * Note: In multi-response scenarios (split view), there can be multiple response messages
 * for a single user message. The `responseMessageIds` array will contain all of them.
 * For single-response scenarios, the array will contain just one ID.
 */
export interface SentMessage {
	/** The ID of the user message that was sent */
	userMessageId: string;
	/**
	 * Array of response message IDs. In single-response mode, this contains one ID.
	 * In multi-response mode (split view), this contains multiple IDs (one per selected model).
	 */
	responseMessageIds: string[];
}

/**
 * Common parent page object for all chat pages.
 *
 * This includes the home page and the chat page.
 */
export abstract class BaseChatPage extends BasePage {
	public modelSelector: ModelSelector;

	// helper functions to get test id and locator for the current page
	protected getPageTestId = (...args: string[]): string => {
		return testId('Chat', ...args);
	};
	protected getPageLocator = (...args: string[]): Locator => {
		return this.page.getByTestId(this.getPageTestId(...args));
	};

	// Navbar element
	/** Opens controls sidebar */
	private controlsButton = this.getPageLocator('Navbar', 'ControlsButton');

	// MessageInput elements
	private richTextInput = this.getPageLocator('MessageInput', 'RichTextInput').locator(
		'#chat-input'
	);
	private plainTextInput = this.getPageLocator('MessageInput', 'PlainTextInput').locator(
		'#chat-input'
	);
	private autocompleteSuggestion = this.richTextInput.locator('.ai-autocompletion');
	private sendMessageButton = this.getPageLocator('MessageInput', 'SendMessageButton');
	private stopResponseButton = this.getPageLocator('MessageInput', 'StopResponseButton');
	private callButton = this.getPageLocator('MessageInput', 'CallButton');

	// Commands (Models, Knowledge, Prompts)
	private commandsContainer = this.getPageLocator('MessageInput', 'Commands', 'Container');
	/// Models commands - show up when you type the @ symbol
	private getCommandsModelsModelImage = (modelId: string) =>
		this.getPageLocator('MessageInput', 'Commands', 'Models', 'ModelImage', modelId);
	private getCommandsModelsModelName = (modelId: string) =>
		this.getPageLocator('MessageInput', 'Commands', 'Models', 'ModelName', modelId);

	constructor(page: Page) {
		super(page);
		this.modelSelector = new ModelSelector(page, ['Chat', 'ModelSelector']);
	}

	// --------------- //
	//  Message Input  //
	// --------------- //

	async getMessageInputType(): Promise<'rich' | 'plain'> {
		if (await this.richTextInput.isVisible()) {
			return 'rich';
		}
		return 'plain';
	}

	async assertMessageInputType(type: 'rich' | 'plain'): Promise<void> {
		if (type === 'rich') {
			await expect(this.richTextInput).toBeVisible();
		} else {
			await expect(this.plainTextInput).toBeVisible();
		}
	}

	/**
	 * Helper method to get the message input locator regardless of type.
	 */
	private async getMessageInput(): Promise<Locator> {
		const type = await this.getMessageInputType();
		if (type === 'rich') {
			return this.richTextInput;
		} else {
			return this.plainTextInput;
		}
	}

	/**
	 * Types a message into the message input.
	 *
	 * @param message - The message to type.
	 */
	async typeMessage(message: string): Promise<void> {
		const input = await this.getMessageInput();
		await input.fill(message);
	}

	async clickSendMessageButton(): Promise<void> {
		await this.sendMessageButton.click();
	}

	/**
	 * Submits a message by typing it and clicking the send message button.
	 *
	 * Does NOT wait for the message to be completed, or anything of the sort.
	 *
	 * You probably want to use submitMessageAndCaptureIds() instead.
	 *
	 * @param message - The message to submit.
	 */
	async submitMessage(message: string): Promise<void> {
		await this.typeMessage(message);
		await this.clickSendMessageButton();
	}

	/**
	 * Checks whether the LLM is currently responding to a message by checking if the stop response button is visible.
	 *
	 * @returns True if a response is in progress, false otherwise.
	 */
	async isResponseInProgress(): Promise<boolean> {
		return await this.stopResponseButton.isVisible();
	}

	async assertResponseInProgress(): Promise<void> {
		await expect(this.stopResponseButton).toBeVisible();
	}

	/**
	 * Checks whether the LLM is not currently responding to a message by checking if the call button is visible.
	 *
	 * @returns True if a response is not in progress, false otherwise.
	 */
	async isResponseNotInProgress(): Promise<boolean> {
		return await this.callButton.isVisible();
	}

	/**
	 * Asserts that the response is not in progress by checking if the call button is visible.
	 */
	async assertResponseNotInProgress(): Promise<void> {
		await expect(this.callButton).toBeVisible();
	}

	/**
	 * Asserts that the message cannot be submitted by checking if the send message button is not visible.
	 *
	 * Also asserts that the call button is still visible (as it will be when input is determined to be empty).
	 *
	 * This should be used either when a response is in progress, or when the input should be detected as effectively empty.
	 */
	async assertCannotSubmitMessage(): Promise<void> {
		await expect(this.sendMessageButton).not.toBeVisible();
		await expect(this.callButton).toBeVisible();
	}

	/**
	 * Clicks the stop response button to stop the current response.
	 */
	async clickStopResponseButton(): Promise<void> {
		await this.stopResponseButton.click();
	}

	/**
	 * Gets the autocomplete suggestion for the current message input.
	 *
	 * MUST be in rich text input mode to use this method without errors.
	 *
	 * @returns The autocomplete suggestion, or null if no suggestion is available.
	 */
	async getAutocompleteSuggestion(): Promise<string | null> {
		return await this.autocompleteSuggestion.getAttribute('data-suggestion');
	}

	async assertAutocompleteSuggestionExists(suggestion: string): Promise<void> {
		await expect(this.autocompleteSuggestion).toHaveText(suggestion);
	}

	async assertAutocompleteSuggestionDoesNotExist(): Promise<void> {
		await expect(this.autocompleteSuggestion).not.toBeVisible();
	}

	/**
	 * Submits a message and captures the message IDs from the API request(s).
	 *
	 * This method intercepts POST requests to `/api/chat/completions` to extract
	 * the user message ID and response message ID(s) before responses complete.
	 * This allows for assertions during streaming responses and early access to IDs.
	 *
	 * For single-response scenarios, `responseMessageIds` will contain one ID.
	 * For multi-response scenarios (split view with multiple models), it will contain
	 * multiple IDs (one per model/API request).
	 *
	 * @param message - The message text to submit.
	 * @returns A promise that resolves to an object containing the user message ID and array of response message IDs.
	 */
	async submitMessageAndCaptureIds(message: string): Promise<SentMessage> {
		// TODO does this work? Cursor chat name 'Adding identifiers for E2E testing in chat app'
		// TODO i'm specifically worried about multi-response/side-by-side view!
		// Set up route interception to capture message IDs
		let userMessageId: string | null = null;
		const responseMessageIds: string[] = [];
		let captureComplete = false;

		const routePromise = new Promise<SentMessage>((resolve) => {
			this.page.route('**/api/chat/completions', async (route) => {
				const request = route.request();
				const postData = request.postDataJSON();

				// Extract user message ID from the messages array.
				// There can be multiple user messages in the history; we always want the *latest* one.
				type ChatMessage = { role?: string; id?: string };
				const messages: ChatMessage[] = Array.isArray(postData?.messages)
					? (postData.messages as ChatMessage[])
					: [];
				const userMessages = messages.filter((msg) => msg.role === 'user');
				const latestUserMessage = userMessages[userMessages.length - 1];
				const msgId = latestUserMessage?.id ?? null;

				// Extract response message ID from the top-level 'id' field
				const responseId = postData?.id || null;

				if (msgId) {
					userMessageId = msgId;
				}

				if (responseId) {
					responseMessageIds.push(responseId);
				}

				// Continue with the request
				await route.continue();

				// Wait a bit to see if more requests come in (for multi-response scenarios)
				// TODO we could probably skip this if there is only one model selected
				// Then resolve with what we have
				if (!captureComplete) {
					captureComplete = true;
					// Give a small delay to capture multiple requests in multi-response scenarios
					setTimeout(() => {
						if (userMessageId && responseMessageIds.length > 0) {
							resolve({
								userMessageId,
								responseMessageIds: [...responseMessageIds]
							});
						}
					}, 100);
				}
			});
		});

		// Submit the message
		await this.submitMessage(message);

		// Wait for the route interception to capture the IDs
		const result = await routePromise;

		if (!result.userMessageId || result.responseMessageIds.length === 0) {
			throw new Error('Failed to capture message IDs from API request');
		}

		return result;
	}

	async assertModelExistsInCommands(modelId: string): Promise<void> {
		await expect(this.getCommandsModelsModelName(modelId)).toBeVisible();
	}

	/**
	 * Asserts that the model name exists in the commands container.
	 *
	 * The model commands container must be visible before calling this method.
	 * (It is accessed by entering the @ key then typing the model name)
	 *
	 * @param modelId - The ID of the model, including the endpoint prefix.
	 * @param modelName - The name of the model.
	 */
	async assertModelNameInCommands(modelId: string, modelName: string): Promise<void> {
		await expect(this.getCommandsModelsModelName(modelId)).toHaveText(modelName);
	}

	/**
	 * Asserts that the model's image in the commands container matches the expected URL or pattern.
	 *
	 * The model commands container must be visible before calling this method.
	 * (It is accessed by entering the @ key then typing the model name)
	 *
	 * @param modelId - The ID of the model, including the endpoint prefix.
	 * @param expectedImageUrl - The expected image URL. Can be:
	 *   - An exact URL string (e.g., '/static/favicon.png')
	 *   - A regex pattern (e.g., /\/api\/v1\/files\/.*\/content/)
	 *   - A function that returns a boolean (for custom validation)
	 */
	async assertModelImageInCommands(
		modelId: string,
		expectedImageUrl: string | RegExp | ((url: string) => boolean)
	): Promise<void> {
		const imageLocator = this.getCommandsModelsModelImage(modelId);

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
	 * Asserts that the model's hide state matches the expected value.
	 *
	 * We expect the model to **NOT** be visible in the commands container if it is hidden.
	 *
	 * @param modelId - The ID of the model.
	 * @param expectedHideState - The expected hide state.
	 */
	async assertModelHideState(modelId: string, expectedHideState: boolean): Promise<void> {
		if (expectedHideState) {
			await expect(this.getCommandsModelsModelName(modelId)).not.toBeVisible();
			await expect(this.getCommandsModelsModelImage(modelId)).not.toBeVisible();
		} else {
			await expect(this.getCommandsModelsModelName(modelId)).toBeVisible();
			await expect(this.getCommandsModelsModelImage(modelId)).toBeVisible();
		}
	}
}

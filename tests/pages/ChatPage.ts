import { expect, type Locator, type Page } from '@playwright/test';
import { BaseChatPage } from './BaseChatPage';

/**
 * The home page, AKA the new chat page.
 */
export class ChatPage extends BaseChatPage {
	// navbar elements
	/** Opens chat context menu dropdown */
	private chatContextMenuButton = this.getPageLocator('Navbar', 'ChatContextMenuButton');
	/** Opens chat info modal */
	private chatInfoButton = this.getPageLocator('Navbar', 'ChatInfoButton');

	/// chat title (the thing in the middle of navbar that shows the chat title and folder name)
	/** Clickiing this scrolls the sidebar to the chat location */
	private chatTitleButton = this.getPageLocator('Navbar', 'ChatTitle', 'Button');
	private chatTitleTitle = this.getPageLocator('Navbar', 'ChatTitle', 'Title');
	private chatTitleFolderName = this.getPageLocator('Navbar', 'ChatTitle', 'FolderName');

	// Response message elements
	private getResponseMessageModelName = (messageId: string) =>
		this.getPageLocator('Message', 'Response', 'ModelName', messageId);

	constructor(page: Page) {
		super(page);
	}

	/**
	 * Asserts that the chat title element includes the expected title and folder name.
	 *
	 * If no folder name is provided, this will assert that there is NO folder name visible!
	 *
	 * @param title - The expected title of the chat.
	 * @param folderName - The expected folder name of the chat. If not provided, the folder name will not be visible.
	 */
	async assertChatTitle(title: string, folderName?: string): Promise<void> {
		await expect(this.chatTitleTitle).toHaveText(title);
		if (folderName) {
			await expect(this.chatTitleFolderName).toHaveText(folderName);
		} else {
			await expect(this.chatTitleFolderName).not.toBeVisible();
		}
	}

	/**
	 * Gets all response message IDs for a given user message ID by waiting for them to appear in the DOM.
	 *
	 * This is useful when you need to get all response messages, including in multi-response scenarios
	 * where not all response IDs may have been captured from the API request interception.
	 *
	 * TODO: this is probably unnecessary, multi-response scenarios SHOULD be handled by the api request interception! but this may still be useful in other edge case scenarios!
	 *
	 * Note: This method finds assistant messages that appear after the user message in the DOM.
	 * In normal conversation flow, response messages appear immediately after their parent user message.
	 * However, in complex scenarios (edits, branches, etc.), this may not be reliable.
	 *
	 * @param userMessageId - The ID of the user message.
	 * @param timeout - Maximum time to wait for response messages to appear (default: 5000ms).
	 * @returns A promise that resolves to an array of response message IDs.
	 */
	async getResponseMessageIdsForUserMessage(
		userMessageId: string,
		timeout: number = 5000
	): Promise<string[]> {
		// Wait for the user message to appear first
		const userMessageLocator = this.getUserMessageLocator(userMessageId);
		await userMessageLocator.waitFor({ timeout, state: 'visible' });

		const responseIds: string[] = [];
		const startTime = Date.now();

		// Poll for assistant messages that appear after the user message
		while (Date.now() - startTime < timeout) {
			// Get all assistant message elements
			const allAssistantMessages = this.page.locator('[data-testid^="Chat_Message_Assistant_"]');

			const count = await allAssistantMessages.count();

			for (let i = 0; i < count; i++) {
				const msg = allAssistantMessages.nth(i);
				const testId = await msg.getAttribute('data-testid');
				if (testId) {
					// Extract message ID from test ID: "Chat_Message_Assistant_{messageId}"
					const messageId = testId.replace('Chat_Message_Assistant_', '');
					if (messageId && !responseIds.includes(messageId)) {
						// Check if this message appears after the user message in the DOM
						const userMessageBox = await userMessageLocator.boundingBox();
						const assistantMessageBox = await msg.boundingBox();

						if (userMessageBox && assistantMessageBox && assistantMessageBox.y > userMessageBox.y) {
							responseIds.push(messageId);
						}
					}
				}
			}

			// If we found some messages and enough time has passed, break
			if (responseIds.length > 0 && Date.now() - startTime > 1000) {
				break;
			}

			await this.page.waitForTimeout(200);
		}

		return responseIds;
	}

	/**
	 * Gets a locator for a user message by its ID.
	 *
	 * @param messageId - The ID of the user message.
	 * @returns A locator for the user message element.
	 */
	getUserMessageLocator(messageId: string): Locator {
		return this.page.getByTestId(this.getPageTestId('Message', 'User', messageId));
	}

	/**
	 * Gets a locator for an assistant message by its ID.
	 *
	 * @param messageId - The ID of the assistant message.
	 * @returns A locator for the assistant message element.
	 */
	getAssistantMessageLocator(messageId: string): Locator {
		return this.page.getByTestId(this.getPageTestId('Message', 'Assistant', messageId));
	}

	/**
	 * Gets a locator for any message (user or assistant) by its ID.
	 *
	 * @param messageId - The ID of the message.
	 * @returns A locator for the message element.
	 */
	getMessageLocator(messageId: string): Locator {
		return this.page.getByTestId(this.getPageTestId('Message', messageId));
	}

	/**
	 * Asserts that a user message exists and is visible.
	 *
	 * @param messageId - The ID of the user message.
	 */
	async assertUserMessageExists(messageId: string): Promise<void> {
		await expect(this.getUserMessageLocator(messageId)).toBeVisible();
	}

	/**
	 * Asserts that an assistant message exists and is visible.
	 *
	 * @param messageId - The ID of the assistant message.
	 */
	async assertAssistantMessageExists(messageId: string): Promise<void> {
		await expect(this.getAssistantMessageLocator(messageId)).toBeVisible();
	}

	/**
	 * Asserts that a user message contains the expected text.
	 *
	 * @param messageId - The ID of the user message.
	 * @param expectedText - The expected text content.
	 */
	async assertUserMessageText(messageId: string, expectedText: string): Promise<void> {
		await expect(this.getUserMessageLocator(messageId)).toContainText(expectedText);
	}

	/**
	 * Asserts that an assistant message contains the expected text.
	 *
	 * @param messageId - The ID of the assistant message.
	 * @param expectedText - The expected text content.
	 */
	async assertAssistantMessageText(messageId: string, expectedText: string): Promise<void> {
		await expect(this.getAssistantMessageLocator(messageId)).toContainText(expectedText);
	}

	/**
	 * Asserts that all response messages for a user message exist and are visible.
	 *
	 * Useful for multi-response scenarios where you want to verify all responses appeared.
	 *
	 * @param userMessageId - The ID of the user message.
	 * @param expectedCount - Optional. If provided, asserts that exactly this many responses exist.
	 */
	async assertAllResponseMessagesExist(
		userMessageId: string,
		expectedCount?: number
	): Promise<void> {
		const responseIds = await this.getResponseMessageIdsForUserMessage(userMessageId);

		if (expectedCount !== undefined) {
			expect(responseIds.length).toBe(expectedCount);
		}

		for (const responseId of responseIds) {
			await this.assertAssistantMessageExists(responseId);
		}
	}

	/**
	 * Asserts that a response message has the expected model name.
	 *
	 * @param responseMessageId - The ID of the response message.
	 * @param modelName - The expected model name.
	 */
	async assertResponseMessageHasModelName(
		responseMessageId: string,
		modelName: string
	): Promise<void> {
		await expect(this.getResponseMessageModelName(responseMessageId)).toHaveText(modelName);
	}

	/**
	 * Asserts that a response message has the expected model image URL.
	 *
	 * @param responseMessageId - The ID of the response message.
	 * @param expectedImageUrl - The expected image URL. Can be:
	 *   - An exact URL string (e.g., '/static/favicon.png')
	 *   - A regex pattern (e.g., /\/api\/v1\/files\/.*\/content/)
	 *   - A function that returns a boolean (for custom validation)
	 */
	async assertResponseMessageHasModelImage(
		responseMessageId: string,
		expectedImageUrl: string | RegExp | ((url: string) => boolean)
	): Promise<void> {
		const imageLocator = this.getAssistantMessageLocator(responseMessageId).locator('img').first();

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
	 * Clicks the chat info button to open the {@link ChatInfoModal}.
	 *
	 * The button only appears when both $chatId and currentChatDetails are loaded.
	 * This method waits for the button to exist before clicking.
	 */
	async clickChatInfoButton(): Promise<void> {
		// Wait for the button to exist - it only appears when $chatId && currentChatDetails
		// This ensures currentChatDetails has been loaded asynchronously
		await this.chatInfoButton.waitFor({ state: 'visible' });
		await this.chatInfoButton.click();
	}
}

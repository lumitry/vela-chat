import { expect, type Locator, type Page } from '@playwright/test';
import { testId } from '$lib/utils/testId';

export class SharedChatPage {
	// Helper functions to get test id and locator for the current page
	private getPageTestId = (...args: string[]): string => {
		return testId('Chat', ...args);
	};
	private getPageLocator = (...args: string[]): Locator => {
		return this.page.getByTestId(this.getPageTestId(...args));
	};

	private chatTitle = this.getPageLocator('SharedChatPage', 'Title');
	private chatTimestamp = this.getPageLocator('SharedChatPage', 'Timestamp');
	private cloneChatButton = this.getPageLocator('SharedChatPage', 'CloneChatButton');

	constructor(private page: Page) {}

	async assertChatTitle(title: string): Promise<void> {
		await expect(this.chatTitle).toHaveText(title);
	}

	/**
	 * Asserts that the chat timestamp matches the expected timestamp.
	 *
	 * @param timestamp - The expected timestamp in **ISO string format** (e.g. `2025-01-01T00:00:00.000Z`).
	 */
	async assertChatTimestamp(timestamp: string): Promise<void> {
		await expect(this.chatTimestamp).toHaveAttribute('data-value', timestamp);
	}

	/** Takes you to a ChatPage containing the cloned chat. */
	async clickCloneChatButton(): Promise<void> {
		await this.cloneChatButton.click();
	}

	// ---------------------------------------- //
	//  Message Methods (copied from ChatPage)  //
	// ---------------------------------------- //

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
	 * Gets the text content of an assistant message.
	 *
	 * @param messageId - The ID of the assistant message.
	 * @returns The text content of the assistant message.
	 */
	async getAssistantMessageText(messageId: string): Promise<string> {
		const text = await this.getAssistantMessageLocator(messageId).textContent();
		if (!text) {
			throw new Error('Assistant message text not found');
		}
		return text;
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
	 * Asserts that an assistant message does not contain the expected text (also ignoring case).
	 *
	 * @param messageId - The ID of the assistant message.
	 * @param unexpectedText - The text content that should not be present.
	 */
	async assertAssistantMessageNotContainsText(
		messageId: string,
		unexpectedText: string
	): Promise<void> {
		await expect(this.getAssistantMessageLocator(messageId)).not.toContainText(unexpectedText, {
			ignoreCase: true
		});
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
		const modelNameLocator = this.getPageLocator(
			'Message',
			'Response',
			'ModelName',
			responseMessageId
		);
		await expect(modelNameLocator).toHaveText(modelName);
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
}

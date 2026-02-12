import { testId } from '$lib/utils/testId';
import { expect, type Locator, type Page } from '@playwright/test';
import { BaseModal } from '../../components/BaseModal';

/**
 * Represents the Chat Info modal.
 *
 * Modal is opened by clicking the chat info button on the {@link ChatPage}.
 */
export class ChatInfoModal extends BaseModal {
	// Modal elements
	/** The title of the chat */
	private chatTitle = this.page.getByTestId(testId('Chat', 'InfoModal', 'Title'));
	private closeButton = this.page.getByTestId(testId('Chat', 'InfoModal', 'CloseButton'));

	// Chat info elements
	private totalMessages = this.page.getByTestId(testId('Chat', 'InfoModal', 'TotalMessages'));
	/** The number of messages in the current 'branch' */
	private currentBranchMessages = this.page.getByTestId(
		testId('Chat', 'InfoModal', 'CurrentBranchMessages')
	);
	/** The number of branches in the chat as calculated by the number of leaf messages (ends of each path) */
	private branchCount = this.page.getByTestId(testId('Chat', 'InfoModal', 'BranchCount'));
	private attachmentCount = this.page.getByTestId(testId('Chat', 'InfoModal', 'AttachmentCount'));

	// Usage elements
	/** Total cost of response messages, not including tasks, embeddings, external image gen, web searches, etc. */
	private totalCost = this.page.getByTestId(testId('Chat', 'InfoModal', 'TotalCost'));
	private totalInputTokens = this.page.getByTestId(testId('Chat', 'InfoModal', 'TotalInputTokens'));
	private totalOutputTokens = this.page.getByTestId(
		testId('Chat', 'InfoModal', 'TotalOutputTokens')
	);
	private totalReasoningTokens = this.page.getByTestId(
		testId('Chat', 'InfoModal', 'TotalReasoningTokens')
	);

	// Unique models elements
	private uniqueModelsCount = this.page.getByTestId(
		testId('Chat', 'InfoModal', 'UniqueModelsCount')
	);
	private getUniqueModelImage = (modelId: string): Locator =>
		this.page.getByTestId(testId('Chat', 'InfoModal', 'UniqueModelImage', modelId));
	/** The placeholder for a unique model image. Only used if the model is disabled or doesn't exist. This will be the first letter of the model ID in uppercase. */
	private getUniqueModelImagePlaceholder = (modelId: string): Locator =>
		this.page.getByTestId(testId('Chat', 'InfoModal', 'UniqueModelImagePlaceholder', modelId));
	/** The label of the model (i.e. the model name if it has one, otherwise the model ID) */
	private getUniqueModelLabel = (modelId: string): Locator =>
		this.page.getByTestId(testId('Chat', 'InfoModal', 'UniqueModelLabel', modelId));
	/** The ID of the model. Only shows if model name != ID. */
	private getUniqueModelId = (modelId: string): Locator =>
		this.page.getByTestId(testId('Chat', 'InfoModal', 'UniqueModelId', modelId));
	private getUniqueModelMessageCount = (modelId: string): Locator =>
		this.page.getByTestId(testId('Chat', 'InfoModal', 'UniqueModelMessageCount', modelId));

	constructor(page: Page) {
		super(page, testId('Chat', 'InfoModal'));
	}

	async assertChatTitle(expectedTitle: string): Promise<void> {
		await expect(this.chatTitle).toHaveText(expectedTitle);
	}

	async assertCurrentBranchMessages(expectedMessages: number): Promise<void> {
		await expect(this.currentBranchMessages).toHaveText(expectedMessages.toString());
	}

	async assertBranchCount(expectedCount: number): Promise<void> {
		await expect(this.branchCount).toHaveText(expectedCount.toString());
	}

	async assertAttachmentCount(expectedCount: number): Promise<void> {
		await expect(this.attachmentCount).toHaveText(expectedCount.toString());
	}

	async assertTotalCost(expectedCost: number): Promise<void> {
		await expect(this.totalCost).toHaveText(expectedCost.toString());
	}

	async assertTotalInputTokens(expectedTokens: number): Promise<void> {
		await expect(this.totalInputTokens).toHaveText(expectedTokens.toString());
	}

	async assertTotalOutputTokens(expectedTokens: number): Promise<void> {
		await expect(this.totalOutputTokens).toHaveText(expectedTokens.toString());
	}

	async assertTotalReasoningTokens(expectedTokens: number): Promise<void> {
		await expect(this.totalReasoningTokens).toHaveText(expectedTokens.toString());
	}

	async assertUniqueModelsCount(expectedCount: number): Promise<void> {
		await expect(this.uniqueModelsCount).toHaveText(expectedCount.toString());
	}

	async assertUniqueModelImage(modelId: string, expectedImage: string): Promise<void> {
		await expect(this.getUniqueModelImage(modelId)).toHaveAttribute('src', expectedImage);
	}

	/**
	 * Asserts that the unique model image placeholder text matches the first letter of the model ID in uppercase.
	 *
	 * This should never be used alongside {@link assertUniqueModelImage}, since the placeholder is only used if the model is disabled or doesn't exist.
	 *
	 * @param modelId - The ID of the model.
	 */
	async assertUniqueModelImagePlaceholder(modelId: string): Promise<void> {
		// model ID should never be empty string, but just in case
		const expectedText = (modelId || '?').slice(0, 1).toUpperCase();
		await expect(this.getUniqueModelImagePlaceholder(modelId)).toHaveText(expectedText);
	}

	/**
	 * Gets the image src URL for a unique model in the chat info modal.
	 *
	 * @param modelId - The ID of the model.
	 * @returns The image src URL, or null if not found
	 */
	async getUniqueModelImageUrl(modelId: string): Promise<string | null> {
		return await this.getUniqueModelImage(modelId).getAttribute('src');
	}

	async assertUniqueModelLabel(modelId: string, expectedLabel: string): Promise<void> {
		await expect(this.getUniqueModelLabel(modelId)).toHaveText(expectedLabel);
	}

	async assertUniqueModelId(modelId: string, expectedId: string): Promise<void> {
		await expect(this.getUniqueModelId(modelId)).toHaveText(expectedId);
	}

	async assertUniqueModelMessageCount(modelId: string, expectedCount: number): Promise<void> {
		await expect(this.getUniqueModelMessageCount(modelId)).toHaveText(expectedCount.toString());
	}

	/**
	 * Asserts that the unique model label exists in the modal.
	 *
	 * Make sure that this string is something that would not appear in other parts of the modal regardless, since this will match any span with the given text.
	 *
	 * @param label - The label to assert exists.
	 */
	async assertUniqueModelLabelExists(label: string): Promise<void> {
		await expect(
			this.page.getByTestId(testId('Chat', 'InfoModal')).locator('span', { hasText: label })
		).toBeVisible();
	}
}

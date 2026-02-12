import type { Locator, Page } from '@playwright/test';
import { testId } from '$lib/utils/testId';
import { AdminSettingsPage } from './AdminSettingsPage';

/**
 * Configuration for the embedding model.
 *
 * @param engine The embedding model engine.
 * @param model The embedding model.
 * @param url The endpoint URL. Not valid for sentence-transformers.
 * @param apiKey The API key. Not valid for sentence-transformers.
 * @param batchSize The batch size. Not valid for sentence-transformers.
 */
export type EmbeddingConfig = {
	engine: 'openai' | 'ollama' | 'sentence-transformers';
	model: string;
	url?: string;
	apiKey?: string;
	batchSize?: number;
};

/**
 * Represents the Admin Settings - Settings - General page.
 *
 * This is the default page when navigating to /admin/settings.
 *
 * URL: /admin/settings#general
 */
export class AdminSettingsDocumentsTab extends AdminSettingsPage {
	// Helper function to get the test ID for the current page.
	private getPageTestId = (...args: string[]): string => {
		return testId('AdminSettings', 'Documents', ...args);
	};
	private getPageLocator = (...args: string[]): Locator => {
		return this.page.getByTestId(this.getPageTestId(...args));
	};

	// Page elements
	/*
	 * General elements
	 */
	private contentExtractionEngineSelect = this.getPageLocator('ContentExtractionEngineSelect');
	private pdfExtractImagesSwitch = this.getPageLocator('PdfExtractImagesSwitch');
	private bypassEmbeddingAndRetrievalSwitch = this.getPageLocator(
		'BypassEmbeddingAndRetrievalSwitch'
	);
	private textSplitterSelect = this.getPageLocator('TextSplitterSelect');
	private chunkSizeInput = this.getPageLocator('ChunkSizeInput');
	private chunkOverlapInput = this.getPageLocator('ChunkOverlapInput');

	/*
	 * Embedding elements
	 */
	private embeddingEngineSelect = this.getPageLocator('EmbeddingEngineSelect');
	private embeddingModelInput = this.getPageLocator('EmbeddingModelInput');
	private openAIURLInput = this.getPageLocator('OpenAIURLInput');
	private openAIAPIKeyInput = this.getPageLocator('OpenAIAPIKeyInput');
	private ollamaURLInput = this.getPageLocator('OllamaURLInput');
	private ollamaAPIKeyInput = this.getPageLocator('OllamaAPIKeyInput');
	private embeddingBatchSizeInput = this.getPageLocator('EmbeddingBatchSizeInput');

	/*
	 * Retrieval elements
	 */
	private ragFullContextSwitch = this.getPageLocator('RagFullContextSwitch');
	private enableHybridSearchSwitch = this.getPageLocator('EnableHybridSearchSwitch');
	private ragTopKInput = this.getPageLocator('RagTopKInput');

	// hybrid search only
	private rerankingModelInput = this.getPageLocator('RerankingModelInput');
	private rerankingTopKInput = this.getPageLocator('RerankingTopKInput');
	private rerankingRelevanceThresholdInput = this.getPageLocator(
		'RerankingRelevanceThresholdInput'
	);

	private ragTemplateInput = this.getPageLocator('RagTemplateInput');

	/*
	 * File management & integration elements
	 */
	private fileMaxSizeInput = this.getPageLocator('FileMaxSizeInput');
	private fileMaxCountInput = this.getPageLocator('FileMaxCountInput');
	private enableGoogleDriveIntegrationSwitch = this.getPageLocator(
		'EnableGoogleDriveIntegrationSwitch'
	);
	private enableOneDriveIntegrationSwitch = this.getPageLocator('EnableOneDriveIntegrationSwitch');

	/*
	 * Danger zone elements
	 */
	private resetUploadDirButton = this.getPageLocator('ResetUploadDirButton');
	private resetVectorDBButton = this.getPageLocator('ResetVectorDBButton');
	private reindexKnowledgeFilesButton = this.getPageLocator('ReindexKnowledgeFilesButton');

	constructor(page: Page) {
		super(page);
	}

	/**
	 * Sets the embedding model engine, endpoint, and model.
	 *
	 * @param config The embedding configuration to set.
	 */
	async setEmbeddingModel(config: EmbeddingConfig): Promise<void> {
		if (config.engine === 'sentence-transformers') {
			// this one has no value for the value prop, so we pass an empty value... not sure if this works but we will never use sentencetransformers for embedding in these tests so it's fine
			await this.embeddingEngineSelect.selectOption({ value: '' });
		}
		await this.embeddingEngineSelect.selectOption({ value: config.engine });
		await this.embeddingModelInput.fill(config.model);
		if (config.engine === 'openai') {
			await this.openAIURLInput.fill(config.url ?? '');
			await this.openAIAPIKeyInput.fill(config.apiKey ?? '');
			await this.embeddingBatchSizeInput.fill(String(config.batchSize ?? 1));
		}
		if (config.engine === 'ollama') {
			await this.ollamaURLInput.fill(config.url ?? '');
			await this.ollamaAPIKeyInput.fill(config.apiKey ?? '');
			await this.embeddingBatchSizeInput.fill(String(config.batchSize ?? 1));
		}
	}
}

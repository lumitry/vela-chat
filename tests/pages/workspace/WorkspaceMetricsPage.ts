import { expect, type Page } from '@playwright/test';
import { WorkspacePage } from './WorkspacePage';

/**
 * Represents the workspace metrics page.
 * URL: /workspace/metrics
 */
export class WorkspaceMetricsPage extends WorkspacePage {
	private getModelUsageTableRow = (modelId: string) =>
		this.getPageLocator('Metrics', 'ModelUsageTable', 'Row', modelId);
	private getModelUsageTableRowSpend = (modelId: string) =>
		this.getPageLocator('Metrics', 'ModelUsageTable', 'Spend', modelId);
	private getModelUsageTableRowInputTokens = (modelId: string) =>
		this.getPageLocator('Metrics', 'ModelUsageTable', 'InputTokens', modelId);
	private getModelUsageTableRowOutputTokens = (modelId: string) =>
		this.getPageLocator('Metrics', 'ModelUsageTable', 'OutputTokens', modelId);
	private getModelUsageTableRowTotalTokens = (modelId: string) =>
		this.getPageLocator('Metrics', 'ModelUsageTable', 'TotalTokens', modelId);
	private getModelUsageTableRowMessageCount = (modelId: string) =>
		this.getPageLocator('Metrics', 'ModelUsageTable', 'MessageCount', modelId);
	private getModelUsageTableRowModelImage = (modelId: string) =>
		this.getPageLocator('Metrics', 'ModelUsageTable', 'ModelImage', modelId);
	private getModelUsageTableRowModelName = (modelId: string) =>
		this.getPageLocator('Metrics', 'ModelUsageTable', 'ModelName', modelId);

	constructor(page: Page) {
		super(page);
	}

	/**
	 * Asserts that the model usage table row exists for the given model ID.
	 *
	 * @param modelId - The ID of the model to assert the existence of.
	 */
	async assertModelUsageTableRowExists(modelId: string): Promise<void> {
		await this.getModelUsageTableRow(modelId).isVisible();
	}

	/**
	 * Asserts that the model usage table row name matches the given name.
	 *
	 * WARNING: THIS PROBABLY WILL NOT WORK AS YOU EXPECT IT TO! See metrics.py#get_model_metrics() for more details.
	 *
	 * Basically, the model name mapping is done once and cached for the lifetime of the server! Without server restart in between name changes, the name will not be updated!
	 *
	 * @param modelId
	 * @param name
	 */
	async assertModelUsageTableRowName(modelId: string, name: string): Promise<void> {
		await expect(this.getModelUsageTableRowModelName(modelId)).toHaveText(name);
	}

	async assertModelUsageTableRowImage(modelId: string, image: string): Promise<void> {
		await expect(this.getModelUsageTableRowModelImage(modelId)).toHaveAttribute('src', image);
	}

	async assertModelUsageTableRowSpend(modelId: string, spend: number): Promise<void> {
		await expect(this.getModelUsageTableRowSpend(modelId)).toHaveText(spend.toString());
	}

	async assertModelUsageTableRowInputTokens(modelId: string, inputTokens: number): Promise<void> {
		await expect(this.getModelUsageTableRowInputTokens(modelId)).toHaveText(inputTokens.toString());
	}

	async assertModelUsageTableRowOutputTokens(modelId: string, outputTokens: number): Promise<void> {
		await expect(this.getModelUsageTableRowOutputTokens(modelId)).toHaveText(
			outputTokens.toString()
		);
	}

	async assertModelUsageTableRowTotalTokens(modelId: string, totalTokens: number): Promise<void> {
		await expect(this.getModelUsageTableRowTotalTokens(modelId)).toHaveText(totalTokens.toString());
	}

	async assertModelUsageTableRowMessageCount(modelId: string, messageCount: number): Promise<void> {
		await expect(this.getModelUsageTableRowMessageCount(modelId)).toHaveText(
			messageCount.toString()
		);
	}
}

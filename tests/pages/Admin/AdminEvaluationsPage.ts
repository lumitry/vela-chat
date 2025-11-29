import { expect, type Locator, type Page } from '@playwright/test';
import { testId } from '$lib/utils/testId';
import { AdminPage } from './AdminPage';

/**
 * Represents the Admin Panel - Evaluations page.
 *
 * AKA: Leaderboard page, feedbacks page, etc.
 *
 * URL base: /admin/evaluations
 */
export class AdminEvaluationsPage extends AdminPage {
	// helper functions to get test id and locator for the current page
	private getPageTestId = (...args: string[]): string => {
		return testId('AdminSettings', 'Evaluations', ...args);
	};
	private getPageLocator = (...args: string[]): Locator => {
		return this.page.getByTestId(this.getPageTestId(...args));
	};

	// leaderboard elements
	private leaderboardModelCount = this.getPageLocator('Leaderboard', 'ModelCount');
	private leaderboardSearchInput = this.getPageLocator('Leaderboard', 'SearchInput');
	private getLeaderboardModelImage = (modelId: string) =>
		this.getPageLocator('Leaderboard', 'ModelImage', modelId);
	private getLeaderboardModelName = (modelId: string) =>
		this.getPageLocator('Leaderboard', 'ModelName', modelId);
	private getLeaderboardModelRating = (modelId: string) =>
		this.getPageLocator('Leaderboard', 'ModelRating', modelId);
	private getLeaderboardModelWonPercentage = (modelId: string) =>
		this.getPageLocator('Leaderboard', 'ModelWonPercentage', modelId);
	private getLeaderboardModelWonCount = (modelId: string) =>
		this.getPageLocator('Leaderboard', 'ModelWonCount', modelId);
	private getLeaderboardModelLostPercentage = (modelId: string) =>
		this.getPageLocator('Leaderboard', 'ModelLostPercentage', modelId);
	private getLeaderboardModelLostCount = (modelId: string) =>
		this.getPageLocator('Leaderboard', 'ModelLostCount', modelId);

	constructor(page: Page) {
		super(page);
	}

	/**
	 * Asserts that the model name exists in the leaderboard.
	 *
	 * @param modelId - The ID of the model.
	 * @param modelName - The name of the model.
	 */
	async assertLeaderboardModelNameExists(modelId: string, modelName: string): Promise<void> {
		await expect(this.getLeaderboardModelName(modelId)).toHaveText(modelName);
	}

	/**
	 * Asserts that the model's image src attribute in the leaderboard matches the expected URL or pattern.
	 *
	 * @param modelId - The ID of the model.
	 * @param expectedImageUrl - The expected image URL. Can be:
	 *   - An exact URL string (e.g., '/static/favicon.png')
	 *   - A regex pattern (e.g., /\/api\/v1\/files\/.*\/content/)
	 *   - A function that returns a boolean (for custom validation)
	 */
	async assertLeaderboardModelImageExists(
		modelId: string,
		expectedImageUrl: string | RegExp | ((url: string) => boolean)
	): Promise<void> {
		const imageLocator = this.getLeaderboardModelImage(modelId);

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

	// TODO: add more methods, probably refactor this into a leaderboard page object and a feedbacks page object
}

import { expect, type Page } from '@playwright/test';
import { BaseChatPage } from './BaseChatPage';

/**
 * The home page, AKA the new chat page.
 */
export class HomePage extends BaseChatPage {
	private placeholderCurrentModelName = this.getPageLocator('Placeholder', 'CurrentModelName');
	private placeholderDescription = this.getPageLocator('Placeholder', 'Description');
	private placeholderCurrentModelImage = this.getPageLocator('Placeholder', 'CurrentModelImage');
	private getPlaceholderTagsTooltip = (modelIdx: number) =>
		this.getPageLocator('Placeholder', 'CurrentModelTagsTooltip', modelIdx.toString());

	constructor(page: Page) {
		super(page);
	}

	async assertPlaceholderCurrentModelName(modelName: string): Promise<void> {
		await expect(this.placeholderCurrentModelName).toHaveText(modelName);
	}

	async assertPlaceholderDescription(description: string | null): Promise<void> {
		if (description === null) {
			// When description is null, the element should not exist
			await expect(this.placeholderDescription).not.toBeVisible();
		} else {
			await expect(this.placeholderDescription).toHaveText(description);
		}
	}

	/**
	 * Asserts that the placeholder current model image src attribute matches the expected URL or pattern.
	 *
	 * @param expectedImageUrl - The expected image URL. Can be:
	 *   - An exact URL string (e.g., '/static/favicon.png')
	 *   - A regex pattern (e.g., /\/api\/v1\/files\/.*\/content/)
	 *   - A function that returns a boolean (for custom validation)
	 */
	async assertPlaceholderCurrentModelImage(
		expectedImageUrl: string | RegExp | ((url: string) => boolean)
	): Promise<void> {
		if (typeof expectedImageUrl === 'string') {
			// Exact URL match
			await expect(this.placeholderCurrentModelImage).toHaveAttribute('src', expectedImageUrl);
		} else if (expectedImageUrl instanceof RegExp) {
			// Regex pattern match
			await expect(this.placeholderCurrentModelImage).toHaveAttribute('src', expectedImageUrl);
		} else {
			// Custom function validation
			const actualSrc = await this.placeholderCurrentModelImage.getAttribute('src');
			expect(actualSrc).not.toBeNull();
			expect(expectedImageUrl(actualSrc!)).toBe(true);
		}
	}

	/**
	 * Asserts that the placeholder current model is present or absent depending on the expected disable state.
	 *
	 * @param expectedPresence - Whether we expect the model to be present or absent.
	 * @param modelName - The name of the model.
	 * @param expectedImageUrl - The expected image URL.
	 * @param description - The expected description.
	 */
	async assertPlaceholderCurrentModelPresence(
		expectedPresence: boolean,
		modelName: string,
		expectedImageUrl: string,
		description: string
	): Promise<void> {
		// if the model is disabled, the placeholder will show some other model's name and image and description
		if (expectedPresence) {
			await this.assertPlaceholderCurrentModelName(modelName);
			await this.assertPlaceholderCurrentModelImage(expectedImageUrl);
			await this.assertPlaceholderDescription(description);
		} else {
			await expect(this.placeholderCurrentModelName).not.toHaveText(modelName);
			await expect(this.placeholderCurrentModelImage).not.toHaveAttribute('src', expectedImageUrl);
			// The description should either NOT match the string (if visible), OR it can simply not be visible at all.
			if (await this.placeholderDescription.isVisible({ timeout: 50 })) {
				// super low timeout because the other assertions on the page will already make sure the placeholder is loaded/stable
				const text = await this.placeholderDescription.textContent();
				expect(text).not.toBe(description);
			}
		}
	}

	/**
	 * Asserts that the placeholder shows the expected tags in the hover tooltip.
	 *
	 * @param expectedTags - The expected tags array. Tags are displayed as uppercase, comma-separated in the tooltip.
	 * @param modelIdx - The index of the model to assert tags for. Defaults to 0.
	 */
	async assertPlaceholderTags(expectedTags: string[], modelIdx: number = 0): Promise<void> {
		const modelImage = this.placeholderCurrentModelImage;

		// make sure the tooltip is visible
		await modelImage.hover();
		await this.page.waitForTimeout(300);

		if (expectedTags.length === 0) {
			// If no tags expected, verify the image is visible
			// The tooltip might not show tags if empty, so we just verify the image exists
			await expect(modelImage).toBeVisible();
		} else {
			// Tags are displayed as uppercase, comma-separated in the tooltip
			const expectedTooltipText = expectedTags.map((t) => t.toUpperCase()).join(', ');

			// Check the tooltip's aria-label (which contains the tooltip content)
			await expect(this.getPlaceholderTagsTooltip(modelIdx)).toHaveAttribute(
				'aria-label',
				expectedTooltipText
			);
		}
	}
}

import { expect, type Locator } from '@playwright/test';

/**
 * Represents a generic dropdown menu component.
 * Automatically parses dropdown options from the provided container locator.
 *
 * Supports dropdowns with:
 * - Buttons (e.g., UserMenu)
 * - DropdownMenu.Item elements (role="menuitem")
 * - Any clickable elements within the dropdown
 *
 * @example
 * ```typescript
 * // In a page object:
 * const menuContainer = page.locator('[role="menu"]');
 * const dropdown = new Dropdown(menuContainer);
 *
 * // Click by text
 * await dropdown.clickOptionByText('Settings');
 *
 * // Click by index
 * await dropdown.clickOptionByIndex(0);
 *
 * // Click by test ID
 * await dropdown.clickOptionByTestId('UserMenu_Settings');
 *
 * // Get all options
 * const options = await dropdown.getAllOptionTexts();
 *
 * // Assertions
 * await dropdown.assertOptionCount(5);
 * await dropdown.assertOptionExists('Settings');
 * ```
 */
export class Dropdown {
	protected container: Locator;
	private options: Locator;

	constructor(container: Locator) {
		this.container = container;
		// Find all clickable items in the dropdown:
		// 1. Buttons (for button-based dropdowns like UserMenu)
		// 2. Elements with role="menuitem" (for DropdownMenu.Item components)
		// 3. Elements with data-testid (for testable elements)
		// Exclude nested buttons (buttons that contain other interactive elements)
		this.options = container.locator(
			'button:not(:has(button)), [role="menuitem"], [data-testid]:not(button)'
		);
	}

	/**
	 * Get all option locators
	 */
	getOptions(): Locator {
		return this.options;
	}

	/**
	 * Get the number of options in the dropdown
	 */
	async getOptionCount(): Promise<number> {
		return await this.options.count();
	}

	/**
	 * Get an option by its index (0-based)
	 */
	getOptionByIndex(index: number): Locator {
		return this.options.nth(index);
	}

	/**
	 * Get an option by its text content (exact match)
	 */
	getOptionByText(text: string): Locator {
		return this.options.filter({ hasText: new RegExp(`^${text}$`) });
	}

	/**
	 * Get an option by its test ID
	 */
	getOptionByTestId(testId: string): Locator {
		return this.container.getByTestId(testId);
	}

	/**
	 * Get an option by partial text match
	 */
	getOptionByPartialText(text: string): Locator {
		return this.options.filter({ hasText: text });
	}

	/**
	 * Click an option by index
	 */
	async clickOptionByIndex(index: number): Promise<void> {
		await this.getOptionByIndex(index).click();
	}

	/**
	 * Click an option by text (exact match)
	 */
	async clickOptionByText(text: string): Promise<void> {
		await this.getOptionByText(text).click();
	}

	/**
	 * Click an option by test ID
	 */
	async clickOptionByTestId(testId: string): Promise<void> {
		await this.getOptionByTestId(testId).click();
	}

	/**
	 * Click an option by partial text match
	 */
	async clickOptionByPartialText(text: string): Promise<void> {
		await this.getOptionByPartialText(text).click();
	}

	/**
	 * Get the text content of all options
	 */
	async getAllOptionTexts(): Promise<string[]> {
		const count = await this.getOptionCount();
		const texts: string[] = [];
		for (let i = 0; i < count; i++) {
			const text = await this.getOptionByIndex(i).textContent();
			if (text) {
				texts.push(text.trim());
			}
		}
		return texts;
	}

	/**
	 * Assert the dropdown is visible
	 */
	async assertIsVisible(): Promise<void> {
		await expect(this.container).toBeVisible();
	}

	/**
	 * Assert the dropdown is not visible
	 */
	async assertIsNotVisible(): Promise<void> {
		await expect(this.container).not.toBeVisible();
	}

	/**
	 * Assert the dropdown has a specific number of options
	 */
	async assertOptionCount(expectedCount: number): Promise<void> {
		const count = await this.getOptionCount();
		expect(count).toBe(expectedCount);
	}

	/**
	 * Assert an option with specific text exists
	 */
	async assertOptionExists(text: string): Promise<void> {
		const option = this.getOptionByText(text);
		await expect(option).toBeVisible();
	}

	/**
	 * Assert an option with specific text does not exist
	 */
	async assertOptionDoesNotExist(text: string): Promise<void> {
		const option = this.getOptionByText(text);
		await expect(option).not.toBeVisible();
	}
}

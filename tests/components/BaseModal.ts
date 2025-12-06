import { expect, type Locator, type Page } from '@playwright/test';

/**
 * Base class for modal components.
 * Provides common functionality for interacting with modals.
 *
 * @example
 * ```typescript
 * export class AddUserModal extends BaseModal {
 *   constructor(page: Page) {
 *     super(page, 'AdminSettings_Users_AddUserModal');
 *   }
 * }
 *
 * // Usage:
 * const modal = new AddUserModal(page);
 * await modal.assertIsVisible();
 * await modal.close(); // Click backdrop or press Escape
 * await modal.closeByBackdrop(); // Explicitly click backdrop
 * await modal.pressEscape(); // Press Escape key
 * ```
 */
export class BaseModal {
	protected page: Page;
	protected backdrop: Locator;
	protected content: Locator;
	private modalTestId: string;

	constructor(page: Page, modalTestId?: string) {
		this.page = page;
		this.modalTestId = modalTestId || '';

		// If test ID is provided, use it; otherwise fall back to class selector
		if (this.modalTestId) {
			this.backdrop = page.getByTestId(this.modalTestId);
			this.content = page.getByTestId(`${this.modalTestId}_Content`);
		} else {
			// Fallback to class selector for modals without test IDs
			this.backdrop = page.locator('.modal').last();
			this.content = this.backdrop.locator('> div').last();
		}
	}

	/**
	 * Get the modal backdrop locator
	 */
	getBackdrop(): Locator {
		return this.backdrop;
	}

	/**
	 * Get the modal content locator
	 */
	getContent(): Locator {
		return this.content;
	}

	/**
	 * Close the modal by clicking the backdrop
	 */
	async closeByBackdrop(): Promise<void> {
		// Click at the edge of the backdrop (not on content)
		await this.backdrop.click({ position: { x: 10, y: 10 } });
	}

	/**
	 * Close the modal by pressing Escape key
	 */
	async pressEscape(): Promise<void> {
		await this.page.keyboard.press('Escape');
	}

	/**
	 * Close the modal (tries backdrop click first, then Escape)
	 */
	async close(): Promise<void> {
		// Try clicking backdrop first (most common way)
		await this.closeByBackdrop();
		// Wait a bit to see if it closed
		await this.page.waitForTimeout(100);
		// If still visible, try Escape
		if (await this.backdrop.isVisible().catch(() => false)) {
			await this.pressEscape();
		}
	}

	/**
	 * Assert the modal is visible
	 */
	async assertIsVisible(): Promise<void> {
		await expect(this.backdrop).toBeVisible();
	}

	/**
	 * Assert the modal is not visible
	 */
	async assertIsNotVisible(): Promise<void> {
		await expect(this.backdrop).not.toBeVisible();
	}

	/**
	 * Wait for the modal to be visible
	 */
	async waitForVisible(): Promise<void> {
		await this.backdrop.waitFor({ state: 'visible' });
	}

	/**
	 * Wait for the modal to be hidden
	 */
	async waitForHidden(): Promise<void> {
		await this.backdrop.waitFor({ state: 'hidden' });
	}

	/**
	 * Get the text content of the modal
	 */
	async getTextContent(): Promise<string> {
		return (await this.content.textContent()) || '';
	}
}


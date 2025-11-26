import { expect, type Locator } from '@playwright/test';

/**
 * Represents a toast component from the svelte-sonner library.
 */
export class Toast {
	constructor(private toastContainer: Locator) {}

	/**
	 * Get the text of the toast.
	 * Note: Gets the text of the first toast of the given type.
	 *
	 * @param type - The type of toast to get the text of.
	 * @returns The text of the toast.
	 */
	async getToastText(type: 'error' | 'success' | 'info' | 'warning'): Promise<string> {
		const toast = this.toastContainer.locator(`li[data-type="${type}"]`).first();
		return (await toast.textContent()) ?? '';
	}

	/**
	 * Assert the toast is visible.
	 * @param type - The type of toast to assert is visible.
	 */
	async assertToastIsVisible(type: 'error' | 'success' | 'info' | 'warning'): Promise<void> {
		const toast = this.toastContainer.locator(`li[data-type="${type}"]`).first();
		await expect(toast).toBeVisible();
	}

	/**
	 * Assert the toast is not visible.
	 * @param type - The type of toast to assert is not visible.
	 */
	async assertToastIsNotVisible(type: 'error' | 'success' | 'info' | 'warning'): Promise<void> {
		const toast = this.toastContainer.locator(`li[data-type="${type}"]`);
		await expect(toast).not.toBeVisible();
	}

	/**
	 * Assert the text of the toast is equal to the expected text.
	 * @param type - The type of toast to assert.
	 * @param text - The expected text of the toast.
	 */
	async assertToastText(
		type: 'error' | 'success' | 'info' | 'warning',
		text: string
	): Promise<void> {
		expect(this.getToastText(type)).toBe(text);
	}

	/**
	 * Wait for all toasts of the given type to disappear.
	 * @param type - The type of toast to wait for the disappearance of.
	 */
	async waitForToastToDisappear(type: 'error' | 'success' | 'info' | 'warning'): Promise<void> {
		const toasts = this.toastContainer.locator(`li[data-type="${type}"]`);
		await expect(toasts).toHaveCount(0, { timeout: 1000 });
	}

	// TODO add method to get the nth toast, etc.
}

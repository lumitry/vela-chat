import { expect, type Locator } from '@playwright/test';

/**
 * Represents the bits-ui Pagination component.
 * Uses data-* attributes to target elements since we can't add custom test IDs to bits-ui.
 *
 * @example
 * ```typescript
 * // In a page object:
 * const paginationRoot = page.locator('[data-pagination-root]');
 * const pagination = new Pagination(paginationRoot);
 *
 * // Navigate to a specific page
 * await pagination.goToPage(6);
 *
 * // Navigate with next/previous
 * await pagination.nextPage();
 * await pagination.prevPage();
 *
 * // Get current state
 * const currentPage = await pagination.getCurrentPage();
 * const visiblePages = await pagination.getVisiblePageNumbers();
 *
 * // Random navigation
 * await pagination.randomPage();
 * ```
 */
export class Pagination {
	private container: Locator;
	private prevButton: Locator;
	private nextButton: Locator;
	private pageButtons: Locator;

	constructor(container: Locator) {
		this.container = container;
		this.prevButton = container.locator('[data-pagination-prev-button]');
		this.nextButton = container.locator('[data-pagination-next-button]');
		this.pageButtons = container.locator('[data-pagination-page]');
	}

	/**
	 * Navigate to a specific page, handling cases where the page is hidden behind ellipsis.
	 * If the target page button is visible, clicks it directly. Otherwise, uses next/prev
	 * buttons to navigate until the target page becomes visible or is reached.
	 *
	 * @param pageNumber - The page number to navigate to
	 * @throws Error if pageNumber is less than 1 or greater than the total page count
	 */
	async goToPage(pageNumber: number): Promise<void> {
		const totalPages = await this.getPageCount();

		if (pageNumber < 1 || pageNumber > totalPages) {
			throw new Error(`Page ${pageNumber} is out of range. Valid pages are 1-${totalPages}.`);
		}

		const currentPage = await this.getCurrentPage();
		if (currentPage === pageNumber) {
			return; // Already on the target page
		}

		// Try clicking the page button directly if it's visible
		const pageButton = this.container.locator(`[data-pagination-page][data-value="${pageNumber}"]`);
		if (await pageButton.isVisible()) {
			await pageButton.click();
			return;
		}

		// Navigate using next/prev until we reach the target or it becomes visible
		const direction = pageNumber > currentPage ? 'next' : 'prev';
		const maxIterations = totalPages; // Safety limit to prevent infinite loops

		for (let i = 0; i < maxIterations; i++) {
			// Check if target page button is now visible
			if (await pageButton.isVisible()) {
				await pageButton.click();
				return;
			}

			// Check if we've somehow reached the target page
			const nowOnPage = await this.getCurrentPage();
			if (nowOnPage === pageNumber) {
				return;
			}

			// Navigate one step in the appropriate direction
			if (direction === 'next') {
				await this.nextButton.click();
			} else {
				await this.prevButton.click();
			}
		}

		throw new Error(`Failed to navigate to page ${pageNumber} after ${maxIterations} attempts.`);
	}

	/**
	 * Navigate directly to a visible page button without using next/prev navigation.
	 * Use this when you know the page is visible and want faster navigation.
	 *
	 * @param pageNumber - The page number to navigate to (must be visible)
	 */
	async clickVisiblePage(pageNumber: number): Promise<void> {
		const pageButton = this.container.locator(`[data-pagination-page][data-value="${pageNumber}"]`);
		await pageButton.click();
	}

	/**
	 * Click the next page button.
	 */
	async nextPage(): Promise<void> {
		await this.nextButton.click();
	}

	/**
	 * Click the previous page button.
	 */
	async prevPage(): Promise<void> {
		await this.prevButton.click();
	}

	/**
	 * Get the currently selected page number.
	 * @returns The current page number
	 */
	async getCurrentPage(): Promise<number> {
		const selectedButton = this.container.locator('[data-pagination-page][data-selected]');
		const value = await selectedButton.getAttribute('data-value');
		return parseInt(value ?? '1', 10);
	}

	/**
	 * Get all page numbers that are currently visible (not hidden behind ellipsis).
	 * @returns Array of visible page numbers
	 */
	async getVisiblePageNumbers(): Promise<number[]> {
		const buttons = await this.pageButtons.all();
		const pageNumbers: number[] = [];

		for (const button of buttons) {
			const value = await button.getAttribute('data-value');
			if (value) {
				pageNumbers.push(parseInt(value, 10));
			}
		}

		return pageNumbers;
	}

	/**
	 * Get the highest visible page number.
	 * Note: This is typically the last page if it's visible in the pagination,
	 * which it usually is in most pagination implementations (bits-ui shows first, nearby, and last pages).
	 *
	 * @returns The highest visible page number
	 */
	async getMaxVisiblePage(): Promise<number> {
		const visiblePages = await this.getVisiblePageNumbers();
		return Math.max(...visiblePages);
	}

	/**
	 * Get the total number of pages.
	 * In bits-ui pagination, the last page is always visible, so this returns the
	 * highest visible page number.
	 *
	 * @returns The total page count
	 */
	async getPageCount(): Promise<number> {
		return await this.getMaxVisiblePage();
	}

	/**
	 * Get the lowest visible page number (typically 1).
	 * @returns The lowest visible page number
	 */
	async getMinVisiblePage(): Promise<number> {
		const visiblePages = await this.getVisiblePageNumbers();
		return Math.min(...visiblePages);
	}

	/**
	 * Navigate to a random page (excluding the current page).
	 * Picks from ALL pages (1 to pageCount), not just visible ones.
	 * Useful for testing pagination behavior without targeting a specific page.
	 *
	 * @returns The page number that was navigated to
	 */
	async randomPage(): Promise<number> {
		const currentPage = await this.getCurrentPage();
		const pageCount = await this.getPageCount();

		if (pageCount <= 1) {
			throw new Error('No other pages available to navigate to');
		}

		// Pick a random page from 1 to pageCount, excluding current
		let targetPage: number;
		do {
			targetPage = Math.floor(Math.random() * pageCount) + 1;
		} while (targetPage === currentPage);

		await this.goToPage(targetPage);
		return targetPage;
	}

	/**
	 * Navigate to the first page (page 1).
	 */
	async firstPage(): Promise<void> {
		await this.goToPage(1);
	}

	/**
	 * Navigate to the last page.
	 */
	async lastPage(): Promise<void> {
		const pageCount = await this.getPageCount();
		await this.goToPage(pageCount);
	}

	/**
	 * Check if the previous button is disabled.
	 * @returns true if the previous button is disabled
	 */
	async isPrevDisabled(): Promise<boolean> {
		return await this.prevButton.isDisabled();
	}

	/**
	 * Check if the next button is disabled.
	 * @returns true if the next button is disabled
	 */
	async isNextDisabled(): Promise<boolean> {
		return await this.nextButton.isDisabled();
	}

	/**
	 * Check if the pagination component is visible.
	 * @returns true if the pagination is visible
	 */
	async isVisible(): Promise<boolean> {
		return await this.container.isVisible();
	}

	/**
	 * Get the count of visible page buttons (not including ellipsis).
	 * @returns The number of visible page buttons
	 */
	async getVisiblePageButtonCount(): Promise<number> {
		return await this.pageButtons.count();
	}

	// ---- Assertions ----

	/**
	 * Assert the pagination is visible.
	 */
	async assertIsVisible(): Promise<void> {
		await expect(this.container).toBeVisible();
	}

	/**
	 * Assert the pagination is not visible.
	 */
	async assertIsNotVisible(): Promise<void> {
		await expect(this.container).not.toBeVisible();
	}

	/**
	 * Assert the current page is the expected page number.
	 * @param expectedPage - The expected page number
	 */
	async assertCurrentPage(expectedPage: number): Promise<void> {
		const currentPage = await this.getCurrentPage();
		expect(currentPage).toBe(expectedPage);
	}

	/**
	 * Assert the previous button is disabled.
	 */
	async assertPrevIsDisabled(): Promise<void> {
		await expect(this.prevButton).toBeDisabled();
	}

	/**
	 * Assert the previous button is enabled.
	 */
	async assertPrevIsEnabled(): Promise<void> {
		await expect(this.prevButton).toBeEnabled();
	}

	/**
	 * Assert the next button is disabled.
	 */
	async assertNextIsDisabled(): Promise<void> {
		await expect(this.nextButton).toBeDisabled();
	}

	/**
	 * Assert the next button is enabled.
	 */
	async assertNextIsEnabled(): Promise<void> {
		await expect(this.nextButton).toBeEnabled();
	}

	/**
	 * Assert a specific page number is visible in the pagination.
	 * @param pageNumber - The page number that should be visible
	 */
	async assertPageIsVisible(pageNumber: number): Promise<void> {
		const pageButton = this.container.locator(`[data-pagination-page][data-value="${pageNumber}"]`);
		await expect(pageButton).toBeVisible();
	}

	/**
	 * Assert a specific page number is NOT visible in the pagination (hidden behind ellipsis).
	 * @param pageNumber - The page number that should not be visible
	 */
	async assertPageIsNotVisible(pageNumber: number): Promise<void> {
		const pageButton = this.container.locator(`[data-pagination-page][data-value="${pageNumber}"]`);
		await expect(pageButton).not.toBeVisible();
	}
}

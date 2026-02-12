import { expect, type Page } from '@playwright/test';
import { testId } from '$lib/utils/testId';
import { Dropdown } from './Dropdown';

/**
 * Represents the UserMenu dropdown component.
 * This menu appears in the Navbar and Sidebar components throughout the app.
 *
 * Extends Dropdown to provide both convenience methods (clickSettings(), etc.)
 * and generic dropdown functionality (clickOptionByText(), assertOptionExists(), etc.).
 *
 * @example
 * ```typescript
 * // Convenience methods (better DX)
 * await userMenu.clickAdminPanel();
 *
 * // Generic dropdown methods (more flexible)
 * await userMenu.clickOptionByText('Admin Panel');
 * await userMenu.assertOptionExists('Admin Panel'); // Check if user is admin
 * await userMenu.assertOptionDoesNotExist('Admin Panel'); // Check if user is not admin
 * ```
 */
export class UserMenuDropdown extends Dropdown {
	private settingsButton: ReturnType<Page['getByTestId']>;
	private archivedChatsButton: ReturnType<Page['getByTestId']>;
	private playgroundButton: ReturnType<Page['getByTestId']>;
	private adminPanelButton: ReturnType<Page['getByTestId']>;
	private signOutButton: ReturnType<Page['getByTestId']>;

	constructor(page: Page) {
		// The dropdown content appears when the menu is opened
		const dropdownContainer = page.locator('[role="menu"]');
		super(dropdownContainer);

		// Initialize button locators using test IDs
		this.settingsButton = page.getByTestId(testId('UserMenu', 'Settings'));
		this.archivedChatsButton = page.getByTestId(testId('UserMenu', 'ArchivedChats'));
		this.playgroundButton = page.getByTestId(testId('UserMenu', 'Playground'));
		this.adminPanelButton = page.getByTestId(testId('UserMenu', 'AdminPanel'));
		this.signOutButton = page.getByTestId(testId('UserMenu', 'SignOut'));
	}

	/**
	 * Convenience method to click the Settings option
	 */
	async clickSettings(): Promise<void> {
		await this.settingsButton.click();
	}

	/**
	 * Convenience method to click the Archived Chats option
	 */
	async clickArchivedChats(): Promise<void> {
		await this.archivedChatsButton.click();
	}

	/**
	 * Convenience method to click the Playground option (admin only)
	 */
	async clickPlayground(): Promise<void> {
		await this.playgroundButton.click();
	}

	/**
	 * Convenience method to click the Admin Panel option (admin only)
	 */
	async clickAdminPanel(): Promise<void> {
		await this.adminPanelButton.click();
	}

	/**
	 * Convenience method to click the Sign Out option
	 */
	async clickSignOut(): Promise<void> {
		await this.signOutButton.click();
	}

	/**
	 * Get whether the user is an admin or not
	 */
	async isAdmin(): Promise<boolean> {
		return await this.adminPanelButton.isVisible();
	}

	/**
	 * Assert that the user is an admin
	 */
	async assertIsAdmin(): Promise<void> {
		await expect(this.adminPanelButton).toBeVisible();
	}

	/**
	 * Get the number of active users
	 * @returns The number of active users
	 */
	async getActiveUsersCount(): Promise<number> {
		// getOptionByTestId actually works here since it doesn't validate that the element is a button!
		const activeUsersCount = await this.getOptionByTestId(
			testId('UserMenu', 'ActiveUsers')
		).textContent();
		if (!activeUsersCount) {
			throw new Error('Active users count not found');
		}
		return parseInt(activeUsersCount);
	}
}

import { expect, type Page } from '@playwright/test';
import { Toast } from '../components/Toast';
import { UserMenuDropdown } from '../components/UserMenu';
import { testId } from '$lib/utils/testId';

/**
 * Common page object for all pages. Contains functionality common to all (or most) pages.
 *
 * Exceptions being the onboarding and auth pages.
 *
 * Note that the account pending overlay has methods in here at the moment, but it obviously only exists if the user is pending.
 */
export abstract class BasePage {
	public toast: Toast;
	public userMenu: UserMenuDropdown;

	private userMenuButton: ReturnType<Page['getByTestId']>;
	private accountPendingOverlay: ReturnType<Page['getByTestId']>;
	private accountPendingOverlayAdminDetailsText: ReturnType<Page['getByTestId']>;
	private newChatButton: ReturnType<Page['getByTestId']>;
	private sidebarToggleButtonWhenClosed: ReturnType<Page['getByTestId']>;
	private sidebarToggleButtonWhenOpen: ReturnType<Page['getByTestId']>;
	private sidebar: ReturnType<Page['getByTestId']>;

	// command palette elements
	protected getCommandPaletteCommandButton = (commandId: string) =>
		this.page.getByTestId(testId('CommandPalette', 'CommandItem', commandId));
	protected getCommandPaletteSubmenuItemButton = (submenuItemId: string) =>
		this.page.getByTestId(testId('CommandPalette', 'SubmenuItem', submenuItemId));
	private getCommandPaletteCommandInput: ReturnType<Page['getByTestId']>;
	private commandPalette: ReturnType<Page['getByTestId']>;

	constructor(protected page: Page) {
		const toastContainer = this.page.locator('section[aria-label="Notifications alt+T"]');
		this.toast = new Toast(toastContainer);
		this.userMenu = new UserMenuDropdown(page);
		this.userMenuButton = this.page.getByTestId(testId('Navbar', 'UserMenu', 'Button'));
		this.accountPendingOverlay = this.page.getByTestId(
			testId('AccountPending', 'CheckAgainButton')
		);
		this.accountPendingOverlayAdminDetailsText = this.page.getByTestId(
			testId('AccountPending', 'AdminDetailsText')
		);
		this.newChatButton = this.page.getByTestId(testId('Sidebar', 'NewChatButton'));
		this.sidebarToggleButtonWhenClosed = this.page.getByTestId(testId('SidebarToggleButton'));
		this.sidebarToggleButtonWhenOpen = this.page.getByTestId(testId('Sidebar', 'ToggleButton'));
		this.sidebar = this.page.getByTestId(testId('Sidebar'));
		this.getCommandPaletteCommandInput = this.page.getByTestId(
			testId('CommandPalette', 'CommandInput')
		);
		this.commandPalette = this.page.getByTestId(testId('CommandPalette'));
	}

	async verifyPageLoaded(): Promise<void> {
		// Common verification logic
		await this.page.waitForLoadState('networkidle');
	}

	/**
	 * Click the user menu button to open the user menu dropdown.
	 *
	 * @example
	 * ```typescript
	 * const homePage = new HomePage(page);
	 * const userMenu = homePage.userMenu;
	 * await homePage.clickUserMenuButton();
	 * await userMenu.clickAdminPanel(); // normally you would just do homePage.userMenu.clickAdminPanel() instead, but if you want to do multiple methods on the user menu, you can also do this!
	 * await expect(page).toHaveURL('/admin'); // success
	 * ```
	 */
	async clickUserMenuButton(): Promise<void> {
		await this.userMenuButton.click();
	}

	/**
	 * Get the user role by checking for the account pending overlay and the user menu's admin panel button.
	 * @returns The user role.
	 */
	async getUserRole(): Promise<'admin' | 'user' | 'pending'> {
		if (await this.accountPendingOverlay.isVisible()) {
			return 'pending';
		}
		await this.clickUserMenuButton();
		if (await this.userMenu.isAdmin()) {
			return 'admin';
		} else {
			return 'user';
		}
	}

	/**
	 * Assert that the user is logged in and has the given role.
	 * @param role The role to assert.
	 */
	async assertUserRole(role: 'admin' | 'user' | 'pending'): Promise<void> {
		const userRole = await this.getUserRole();
		expect(userRole).toBe(role);
	}

	/**
	 * Get the admin details text from the account pending overlay.
	 * @returns The admin details text.
	 */
	async getAccountPendingOverlayAdminDetailsText(): Promise<string> {
		return (await this.accountPendingOverlayAdminDetailsText.textContent()) ?? '';
	}

	/**
	 * Assert that the admin details text from the account pending overlay is equal to the expected text.
	 * @param text The expected admin details text.
	 */
	async assertAccountPendingOverlayAdminDetailsText(text: string): Promise<void> {
		expect(await this.getAccountPendingOverlayAdminDetailsText()).toBe(text);
	}

	/**
	 * Assert that the account pending overlay is not visible.
	 */
	async assertAccountPendingOverlayIsNotVisible(): Promise<void> {
		await expect(this.accountPendingOverlay).not.toBeVisible();
	}

	/**
	 * Click the sidebar toggle button.
	 */
	async toggleOpenSidebar(): Promise<void> {
		if (await this.sidebar.isVisible()) {
			await this.sidebarToggleButtonWhenOpen.click();
		} else {
			await this.sidebarToggleButtonWhenClosed.click();
		}
	}

	/**
	 * Open the sidebar if it is closed.
	 */
	async openSidebarIfClosed(): Promise<void> {
		if (await this.sidebar.isVisible()) {
			return;
		}
		await this.toggleOpenSidebar();
	}

	/**
	 * Click the new chat button, opening the sidebar if it is closed.
	 *
	 * Takes you to the home page where you can start a new chat.
	 */
	async clickNewChatButton(): Promise<void> {
		await this.openSidebarIfClosed(); // you can't click the new chat button if the sidebar is closed, and i heavily doubt anyone would try calling this method intentionally knowing that the sidebar is closed and hoping for it to fail, so we might as well not require them to call openSidebarIfClosed() every time they want to call this method.
		await this.newChatButton.click();
	}

	/**
	 * Open the command palette.
	 * @param shortcut - The shortcut to use to open the command palette. Defaults to 'cmd+p'.
	 */
	async openCommandPalette(
		shortcut: 'cmd+p' | 'cmd+k' | 'cmd+e' | 'double-shift' = 'cmd+p'
	): Promise<void> {
		const shortcutReplaced = shortcut.replace('cmd', 'ControlOrMeta');
		await this.page.keyboard.press(`${shortcutReplaced}`);
	}

	// TODO refactor command palette to its own component class

	/**
	 * Types a text into the command palette input. Does NOT submit the command.
	 *
	 * Can also be used in submenus.
	 *
	 * @param searchText - The text to type into the command palette input.
	 */
	async typeCommandPaletteCommand(searchText: string): Promise<void> {
		await this.getCommandPaletteCommandInput.fill(searchText);
	}

	/**
	 * Submits the command palette input.
	 */
	async submitCommandPaletteCommand(): Promise<void> {
		await this.getCommandPaletteCommandInput.press('Enter');
	}

	/**
	 * Clicks a command in the command palette.
	 *
	 * @param commandId - The ID of the command to click.
	 */
	async clickCommandPaletteCommand(commandId: string): Promise<void> {
		await this.getCommandPaletteCommandButton(commandId).click();
	}

	/**
	 * Clicks a submenu item in the command palette.
	 *
	 * @param submenuItemId - The ID of the submenu item to click.
	 */
	async clickCommandPaletteSubmenuItem(submenuItemId: string): Promise<void> {
		await this.getCommandPaletteSubmenuItemButton(submenuItemId).click();
	}

	async assertCommandPaletteSubmenuItemExists(submenuItemId: string): Promise<void> {
		await expect(this.getCommandPaletteSubmenuItemButton(submenuItemId)).toBeVisible();
	}

	async assertCommandPaletteSubmenuItemContainsText(
		submenuItemId: string,
		text: string
	): Promise<void> {
		await expect(this.getCommandPaletteSubmenuItemButton(submenuItemId)).toContainText(text);
	}

	/**
	 * Closes the command palette by clicking the backdrop or pressing Escape, and waits for it to actually close.
	 *
	 * Similar to BaseModal.close(), this tries clicking the backdrop first (which is more reliable),
	 * then falls back to Escape if needed. Handles cases where a submenu is open.
	 * Waits for the command palette to be hidden before returning.
	 *
	 * Note: The command palette is always in the DOM (rendered off-screen for instant opening),
	 * so we check `aria-hidden` attribute instead of `isVisible()` to determine if it's closed.
	 */
	async closeCommandPalette(): Promise<void> {
		// Check if command palette is open by checking aria-hidden attribute
		// When closed, aria-hidden="true"; when open, aria-hidden="false"
		const ariaHidden = await this.commandPalette.getAttribute('aria-hidden');
		if (ariaHidden === 'true') {
			// Already closed, nothing to do
			return;
		}

		// Check if there's a submenu open - if so, close it first with Escape
		const submenuLocator = this.page
			.locator('[data-testid^="CommandPalette_SubmenuItem_"]')
			.first();
		const hasSubmenu = await submenuLocator.isVisible().catch(() => false);

		if (hasSubmenu) {
			// Close submenu first
			await this.page.keyboard.press('Escape');
			// Wait for submenu to disappear
			await submenuLocator.waitFor({ state: 'hidden', timeout: 1000 }).catch(() => {
				// Submenu might already be closed or not exist, continue anyway
			});
		}

		// Now close the main palette - try clicking backdrop first (like BaseModal does)
		// Click at the edge of the backdrop, not on the content
		// The backdrop has on:mousedown handler that closes the palette
		try {
			await this.commandPalette.click({ position: { x: 10, y: 10 } });
			// Wait a bit to see if it closed (check aria-hidden)
			await this.page
				.waitForFunction(
					(testId) => {
						const element = document.querySelector(`[data-testid="${testId}"]`);
						return element?.getAttribute('aria-hidden') === 'true';
					},
					testId('CommandPalette'),
					{ timeout: 500 }
				)
				.catch(() => {
					// If clicking didn't work, continue to Escape fallback
				});
		} catch {
			// If clicking failed, continue to Escape fallback
		}

		// Check if still open - if so, try Escape
		const stillOpen = (await this.commandPalette.getAttribute('aria-hidden')) !== 'true';
		if (stillOpen) {
			// Press Escape to close the command palette
			await this.page.keyboard.press('Escape');
		}

		// Wait for the command palette to actually be closed
		// Check aria-hidden="true" instead of isVisible() since the element is always in DOM
		await expect(this.commandPalette).toHaveAttribute('aria-hidden', 'true', { timeout: 2000 });
	}
}

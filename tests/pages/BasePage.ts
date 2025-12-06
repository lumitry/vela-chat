import { expect, type Page } from '@playwright/test';
import { Toast } from '../components/Toast';
import { UserMenuDropdown } from '../components/UserMenu';
import { CommandPalette } from '../components/CommandPalette';
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
	public commandPalette: CommandPalette;

	private userMenuButton: ReturnType<Page['getByTestId']>;
	private accountPendingOverlay: ReturnType<Page['getByTestId']>;
	private accountPendingOverlayAdminDetailsText: ReturnType<Page['getByTestId']>;
	private newChatButton: ReturnType<Page['getByTestId']>;
	private sidebarToggleButtonWhenClosed: ReturnType<Page['getByTestId']>;
	private sidebarToggleButtonWhenOpen: ReturnType<Page['getByTestId']>;
	private sidebar: ReturnType<Page['getByTestId']>;
	private workspaceButton: ReturnType<Page['getByTestId']>;
	private getChatItem: (id: string) => ReturnType<Page['getByTestId']>;
	private getFolderItem: (id: string) => ReturnType<Page['getByTestId']>;

	constructor(protected page: Page) {
		const toastContainer = this.page.locator('section[aria-label="Notifications alt+T"]');
		this.toast = new Toast(toastContainer);
		this.userMenu = new UserMenuDropdown(page);
		this.commandPalette = new CommandPalette(page);
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
		this.workspaceButton = this.page.getByTestId(testId('Sidebar', 'WorkspaceButton'));
		this.getChatItem = (id: string) => this.page.getByTestId(testId('Sidebar', 'ChatItem', id));
		this.getFolderItem = (id: string) => this.page.getByTestId(testId('Sidebar', 'FolderItem', id));
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
	 * Click the workspace button, opening the first available workspace page.
	 *
	 * First opens the sidebar if it is closed.
	 *
	 * PageObject: WorkspaceModelsPage (or theoretically one of the other workspace pages if the user doesn't have access to the models page)
	 */
	async clickWorkspaceButton(): Promise<void> {
		await this.openSidebarIfClosed();
		await this.workspaceButton.click();
	}

	/**
	 * Clicks the *first* chat with the given title.
	 *
	 * @param title The title of the chat to click.
	 */
	async clickChatByTitle(title: string): Promise<void> {
		await this.page.locator('[data-chat-id] a div div').filter({ hasText: title }).first().click();
	}

	/**
	 * Click the chat with the given chatId.
	 *
	 * @param chatId The chatId of the chat to click.
	 */
	async clickChatById(chatId: string): Promise<void> {
		await this.getChatItem(chatId).click();
	}

	/**
	 * Click the chat at the given index.
	 *
	 * **IMPORTANT** - this will look for the chat at the given index in the sidebar *absolutely*!
	 * In other words, if you've got a folder with 3 chats in it and five chats in the root,
	 * and you call this method with an index of 2, it will click the 3rd chat in the folder,
	 * **NOT** the third chat in the root!
	 *
	 * HOWEVER, if the folder is not expanded, the chats in that folder will not be found.
	 *
	 * @param index The index of the chat to click.
	 */
	async clickChatByIndex(index: number): Promise<void> {
		await this.page.locator('[data-chat-id] a div div').nth(index).click();
	}

	/**
	 * Toggle the expansion state of the *first* folder with the given title.
	 *
	 * @param title The title of the folder to expand.
	 */
	async toggleFolderExpansionByTitle(title: string): Promise<void> {
		await this.page
			.locator(`[data-testid^="${testId('Sidebar', 'FolderItem')}"]`)
			.filter({ hasText: title })
			.first()
			.click();
	}

	async toggleFolderExpansionById(id: string): Promise<void> {
		await this.getFolderItem(id).click();
	}

	async toggleFolderExpansionByIndex(index: number): Promise<void> {
		await this.page
			.locator(`[data-testid^="${testId('Sidebar', 'FolderItem')}"]`)
			.nth(index)
			.click();
	}
}

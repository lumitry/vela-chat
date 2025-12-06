import { expect, type Locator, type Page } from '@playwright/test';
import { testId } from '$lib/utils/testId';
import { AdminPage } from './AdminPage';
import { Pagination } from '../../components/Pagination';

export type UserInfo = {
	idx: number;
	role: 'admin' | 'user' | 'pending';
	name: string;
	email: string;
	lastActiveAt: number;
	createdAt: number;
};

/**
 * Represents the Admin Settings - Users page.
 * URL base: /admin/users
 *
 * Note: All indices are based on location on the page, not absolute in the total user list.
 */
export class AdminUsersPage extends AdminPage {
	// helper functions to get test id and locator for the current page
	private getPageTestId = (...args: string[]): string => {
		return testId('AdminSettings', 'Users', ...args);
	};
	private getPageLocator = (...args: string[]): Locator => {
		return this.page.getByTestId(this.getPageTestId(...args));
	};

	/**
	 * The pagination component for navigating through the user list.
	 */
	public pagination: Pagination;

	/**
	 * The button to add a new user to the list.
	 */
	private addUserButton = this.page.getByTestId(testId('AdminSettings', 'Users', 'AddUserButton'));
	private userCount = this.getPageLocator('UserCount');
	private searchInput = this.getPageLocator('SearchInput');

	// user rows
	private userRows = this.page.getByTestId(testId('AdminSettings', 'Users', 'UserRow'));
	private getUserRow = (index: number) => this.userRows.nth(index);
	private getUserRowRoleButton = (index: number) =>
		this.getPageLocator('UserRow', 'RoleButton', `${index}`);
	private getUserRowUserImage = (index: number) =>
		this.getPageLocator('UserRow', 'UserImage', `${index}`);
	private getUserRowName = (index: number) =>
		this.getPageLocator('UserRow', 'UserName', `${index}`);
	private getUserRowEmail = (index: number) => this.getPageLocator('UserRow', 'Email', `${index}`);
	private getUserRowLastActiveAt = (index: number) =>
		this.getPageLocator('UserRow', 'LastActiveAt', `${index}`);
	private getUserRowCreatedAt = (index: number) =>
		this.getPageLocator('UserRow', 'CreatedAt', `${index}`);
	private getUserRowChatsButton = (index: number) =>
		this.getPageLocator('UserRow', 'ChatsButton', `${index}`);
	private getUserRowEditButton = (index: number) =>
		this.getPageLocator('UserRow', 'EditButton', `${index}`);
	private getUserRowDeleteButton = (index: number) =>
		this.getPageLocator('UserRow', 'DeleteButton', `${index}`);

	constructor(page: Page) {
		super(page);
		this.pagination = new Pagination(this.page.locator('[data-pagination-root]'));
	}

	/** Waits for the users to load in. */
	async waitForUsersToLoad(): Promise<void> {
		await this.userRows.first().waitFor({ state: 'visible' });
	}

	/**
	 * Clicks the add user button to open the {@link AddUserModal}.
	 */
	async clickAddUserButton(): Promise<void> {
		await this.addUserButton.click();
	}

	/**
	 * Searches for a user by name or email.
	 * @param query the query to search for
	 */
	async searchForUser(query: string): Promise<void> {
		await this.searchInput.fill(query);
	}

	/**
	 * Gets the number of users created in this instance.
	 */
	async getUserCount(): Promise<number> {
		const text = await this.userCount.textContent();
		return text ? parseInt(text) : 0;
	}

	/**
	 * Gets a user on the page by index.
	 * @param index the index of the user to get
	 * @returns the user on the page
	 */
	async getUserOnPage(index: number): Promise<UserInfo> {
		const role = await this.getUserRowRole(index);
		const name = await this.getUsername(index);
		const email = await this.getUserEmail(index);

		const lastActiveAtValue = await this.getUserRowLastActiveAt(index).getAttribute('data-value');
		const createdAtValue = await this.getUserRowCreatedAt(index).getAttribute('data-value');
		const lastActiveAt = lastActiveAtValue ? parseInt(lastActiveAtValue) : 0;
		const createdAt = createdAtValue ? parseInt(createdAtValue) : 0;

		return { idx: index, role, name, email, lastActiveAt, createdAt };
	}

	/**
	 * Gets a list of the users in the user list on this page.
	 * @returns the users on the page
	 */
	async getUsersOnPage(): Promise<UserInfo[]> {
		const users = await this.userRows.all();
		return Promise.all(
			users.map(async (_, idx) => {
				return this.getUserOnPage(idx);
			})
		);
	}

	/**
	 * Gets a random user on the page.
	 * @returns the random user on the page
	 */
	async getRandomUserOnPage(): Promise<UserInfo> {
		const users = await this.getUsersOnPage();
		return users[Math.floor(Math.random() * users.length)];
	}

	/**
	 * Gets a random non-admin user on the page.
	 * Useful for tests that modify user properties, since admin users have restrictions.
	 * @returns the random non-admin user on the page
	 * @throws if no non-admin users are found on the page
	 */
	async getRandomNonAdminUserOnPage(): Promise<UserInfo> {
		const users = await this.getUsersOnPage();
		const nonAdminUsers = users.filter((u) => u.role !== 'admin');
		if (nonAdminUsers.length === 0) {
			throw new Error('No non-admin users found on the page');
		}
		return nonAdminUsers[Math.floor(Math.random() * nonAdminUsers.length)];
	}

	/** Gets the role of a user in the user list. */
	async getUserRowRole(index: number): Promise<'admin' | 'user' | 'pending'> {
		const role = await this.getUserRowRoleButton(index).textContent();
		return role as 'admin' | 'user' | 'pending';
	}

	/** Clicks the user role button for a user to change their role. */
	async clickUserRowRoleButton(index: number): Promise<void> {
		await this.getUserRowRoleButton(index).click();
	}

	/** Sets the role of a user in the user list by clicking the role button until it reaches the target role.
	 *
	 * Role cycle: user → admin → pending → user → ...
	 */
	async setUserRowRole(index: number, targetRole: 'admin' | 'user' | 'pending'): Promise<void> {
		let currentRole = await this.getUserRowRole(index);

		while (currentRole !== targetRole) {
			await this.clickUserRowRoleButton(index);
			// Wait for the role to change (API call completes and UI updates)
			await this.getUserRowRoleButton(index).waitFor({ state: 'visible' });
			// Wait until the text content changes from what it was
			await expect(this.getUserRowRoleButton(index)).not.toHaveText(currentRole, { timeout: 5000 });
			currentRole = await this.getUserRowRole(index);
		}
	}

	/** Clicks the user image for a user to view their profile. */
	async getUserImageUrl(index: number): Promise<string> {
		return (await this.getUserRowUserImage(index).getAttribute('src')) ?? '';
	}

	/** Asserts that the user image URL for a user matches the expected URL. */
	async assertUserImageUrl(index: number, url: string): Promise<void> {
		expect(await this.getUserImageUrl(index)).toBe(url);
	}

	/** Gets the username of a user in the user list. */
	async getUsername(index: number): Promise<string> {
		return (await this.getUserRowName(index).textContent()) ?? '';
	}

	/** Gets the email of a user in the user list. */
	async getUserEmail(index: number): Promise<string> {
		return (await this.getUserRowEmail(index).textContent()) ?? '';
	}

	/** Gets the last active at timestamp of a user in the user list. */
	async getUserLastActiveAt(index: number): Promise<number> {
		const value = await this.getUserRowLastActiveAt(index).getAttribute('data-value');
		return value ? parseInt(value) : 0;
	}

	/** Gets the created at timestamp of a user in the user list. */
	async getUserCreatedAt(index: number): Promise<number> {
		const value = await this.getUserRowCreatedAt(index).getAttribute('data-value');
		return value ? parseInt(value) : 0;
	}

	/** Clicks the chats button for a user to view their chats.
	 *
	 * Only exists if the target user is not an admin.
	 *
	 * Opens the {@link UserChatsModal} modal.
	 */
	async clickUserRowChatsButton(index: number): Promise<void> {
		await this.getUserRowChatsButton(index).click();
	}

	/** Clicks the edit button for a user to edit their user.
	 *
	 * Opens the {@link EditUserModal} modal.
	 */
	async clickUserRowEditButton(index: number): Promise<void> {
		await this.getUserRowEditButton(index).click();
	}

	/** Clicks the delete button for a user to delete their user.
	 *
	 * Only exists if the target user is not an admin.
	 */
	async clickUserRowDeleteButton(index: number): Promise<void> {
		await this.getUserRowDeleteButton(index).click();
		await this.clickConfirmDialogConfirmButton();
	}
}

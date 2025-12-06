import type { Page } from '@playwright/test';
import { testId } from '$lib/utils/testId';
import { AdminPage } from './AdminPage';

/**
 * Represents the Admin Settings - Users page.
 * URL base: /admin/users
 */
export class AdminUsersPage extends AdminPage {
	/**
	 * The button to add a new user to the list.
	 */
	private addUserButton = this.page.getByTestId(testId('AdminSettings', 'Users', 'AddUserButton'));

	constructor(page: Page) {
		super(page);
	}

	/**
	 * Clicks the add user button to open the {@link AddUserModal}.
	 */
	async clickAddUserButton(): Promise<void> {
		await this.addUserButton.click();
	}

	/**
	 * Gets a list of the users in the user list on this page.
	 * @returns the users on the page
	 */
	async getUsersOnPage(): Promise<any[]> {
		// TODO: better type for the users. can't be TestUser because we don't have password.
		const users = await this.page.getByTestId(testId('AdminSettings', 'Users', 'UserRow')).all();
		// TODO also that testid doesn't exist yet!
		return users.map((user) => {
			return {
				role: user.locator('td').nth(1).textContent(),
				name: user.locator('td').nth(2).textContent(),
				email: user.locator('td').nth(3).textContent(),
				lastActiveAt: user.locator('td').nth(4).textContent(),
				createdAt: user.locator('td').nth(5).textContent()
			};
		});
	}

	// TODO: add methods for other stuff on the page! Edit user, delete user, etc.
}

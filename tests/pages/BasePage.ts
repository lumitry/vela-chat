import type { Page } from '@playwright/test';
import { Toast } from '../components/Toast';
import { UserMenuDropdown } from '../components/UserMenu';
import { testId } from '$lib/utils/testId';

/**
 * Common page object for all pages. Contains functionality common to all (or most) pages.
 */
export abstract class BasePage {
	public toast: Toast;
	public userMenu: UserMenuDropdown;

	private userMenuButton: ReturnType<Page['getByTestId']>;

	constructor(protected page: Page) {
		const toastContainer = this.page.locator('section[aria-label="Notifications alt+T"]');
		this.toast = new Toast(toastContainer);
		this.userMenu = new UserMenuDropdown(page);
		this.userMenuButton = this.page.getByTestId(testId('Navbar', 'UserMenu', 'Button'));
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
}

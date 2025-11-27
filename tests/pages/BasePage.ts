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
}

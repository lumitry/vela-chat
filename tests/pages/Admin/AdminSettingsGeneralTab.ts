import type { Page } from '@playwright/test';
import { testId } from '$lib/utils/testId';
import { AdminSettingsPage } from './AdminSettingsPage';

/**
 * Represents the Admin Settings - Settings - General page.
 *
 * This is the default page when navigating to /admin/settings.
 *
 * URL: /admin/settings#general
 */
export class AdminSettingsGeneralTab extends AdminSettingsPage {
	// Helper function to get the test ID for the current page.
	private getPageTestId = (...args: string[]): string => {
		return testId('AdminSettings', 'General', ...args);
	};

	// Page elements
	private defaultUserRoleSelect = this.page.getByTestId(
		this.getPageTestId('DefaultUserRoleSelect')
	);
	private enableNewSignUpsSwitch = this.page.getByTestId(
		this.getPageTestId('EnableNewSignUpsSwitch')
	);

	// below are unused for now

	// private showAdminDetailsInAccountPendingOverlaySwitch = this.page.getByTestId(
	// 	this.getPageTestId('ShowAdminDetailsInAccountPendingOverlaySwitch')
	// );
	// private enableApiKeySwitch = this.page.getByTestId(this.getPageTestId('EnableApiKeySwitch'));
	// private apiKeyAllowedEndpointsInput = this.page.getByTestId(
	// 	this.getPageTestId('ApiKeyAllowedEndpointsInput')
	// );

	constructor(page: Page) {
		super(page);
	}

	/**
	 * Sets the default user role.
	 *
	 * @param role The role to set as the default user role.
	 */
	async setDefaultUserRole(role: 'pending' | 'user' | 'admin'): Promise<void> {
		await this.defaultUserRoleSelect.selectOption({ value: role });
	}

	/**
	 * Sets whether to enable new sign ups.
	 *
	 * @param enabled Whether to enable new sign ups.
	 */
	async setEnableNewSignUps(enabled: boolean): Promise<void> {
		// todo: does this work? it's a switch, not a checkbox...
		await this.enableNewSignUpsSwitch.setChecked(enabled);
	}

	// TODO: add more methods?
}

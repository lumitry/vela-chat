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
	constructor(page: Page) {
		super(page);
	}

	// TODO: add methods!
}

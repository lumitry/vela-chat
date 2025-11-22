import { test, expect } from '@playwright/test';
import { LoginPage } from '../pages/LoginPage';
import { SHARED_USERS, generateUsersCSV } from '../data/users';
import { HomePage } from '../pages/HomePage';
import { AddUserModal } from '../pages/Admin/modals/AddUserModal';
import { AdminUsersPage } from '../pages/Admin/AdminUsersPage';
import { AdminSettingsGeneralTab } from '../pages/Admin/AdminSettingsGeneralTab';

test('Create a new user', async ({ page }) => {
	await page.goto('/', { waitUntil: 'networkidle' });
	const loginPage = new LoginPage(page);

	// Expect a title "to contain" a substring.
	await loginPage.login(SHARED_USERS.preExistingAdmin);

	const homePage = new HomePage(page);
	await homePage.clickUserMenuButton();
	await homePage.userMenu.clickAdminPanel();
	const adminSettingsGeneralPage = new AdminSettingsGeneralTab(page);
	await adminSettingsGeneralPage.clickUsersPageButton();
	const adminUsersPage = new AdminUsersPage(page);
	await adminUsersPage.clickAddUserButton();
	const addUserModal = new AddUserModal(page);
	await addUserModal.clickCSVImportTabButton();
	await addUserModal.uploadCSVFile({
		name: 'users.csv',
		mimeType: 'text/csv',
		buffer: Buffer.from(generateUsersCSV())
	});
	await addUserModal.clickSaveButton();
	await addUserModal.close();
	// TODO add assertions that the new users were created successfully!
	await expect(page).toHaveURL('/FAIL-FOR-SCREENSHOT');
});

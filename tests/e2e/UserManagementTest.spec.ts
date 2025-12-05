import { DEFAULT_PASSWORD } from '../data/users';
import { expect, test } from '../fixtures/testUser';
import { AdminSettingsGeneralTab } from '../pages/Admin/AdminSettingsGeneralTab';
import { AdminUsersPage, type UserInfo } from '../pages/Admin/AdminUsersPage';
import { EditUserModal, type EditUserModaEditableField } from '../pages/Admin/modals/EditUserModal';
import { AuthMode, AuthPage } from '../pages/AuthPage';
import { HomePage } from '../pages/HomePage';

type UserRole = 'admin' | 'user' | 'pending';

type UserFieldTestCase =
	| {
			field: EditUserModaEditableField;
			newValue: string;
			isModalField: true;
	  }
	| {
			field: 'role';
			newValue: UserRole;
			isModalField: false;
	  };

const testCases: UserFieldTestCase[] = [
	{ field: 'name', newValue: 'RenamedTestUser', isModalField: true },
	{ field: 'email', newValue: 'renamed_user@test.local', isModalField: true },
	{ field: 'password', newValue: `${DEFAULT_PASSWORD}_REPLACEMENT`, isModalField: true },
	{ field: 'role', newValue: 'user', isModalField: false }
];

/** Expected user state for verification */
type ExpectedUserState = {
	name: string;
	email: string;
	password: string;
	role: UserRole;
};

test.describe('User Management Test', { tag: '@smoke' }, () => {
	for (const testCase of testCases) {
		test(`Verify admin can edit another user's ${testCase.field}`, async ({ page }) => {
			let targetUser: UserInfo;
			let originalState: ExpectedUserState;
			let expectedState: ExpectedUserState;

			const homePage = new HomePage(page);
			await homePage.clickUserMenuButton();
			await homePage.userMenu.clickAdminPanel();
			const adminSettings = new AdminSettingsGeneralTab(page);
			await adminSettings.clickUsersPageButton();

			const adminUsersPage = new AdminUsersPage(page);
			await adminUsersPage.waitForUsersToLoad();

			// TODO we should make users for this test (i.e. via csv import) to avoid concurrency issues with modifying a user while another test is using it.
			// TODO also would be nice to do that for the delete user test
			// TODO and we'll need to make a few chats for the view user chats test...

			await test.step(`Change user ${testCase.field}`, async () => {
				await adminUsersPage.pagination.randomPage();
				targetUser = await adminUsersPage.getRandomUserOnPage();
				expect(targetUser).toBeDefined();

				// Store original state (password is assumed to be DEFAULT_PASSWORD)
				originalState = {
					name: targetUser.name,
					email: targetUser.email,
					password: DEFAULT_PASSWORD,
					role: targetUser.role
				};

				// Calculate expected state after change
				expectedState = { ...originalState };
				if (testCase.field === 'role') {
					expectedState.role = testCase.newValue;
				} else {
					expectedState[testCase.field] = testCase.newValue;
				}

				// Apply the change
				if (testCase.isModalField) {
					await adminUsersPage.clickUserRowEditButton(targetUser.idx);
					const editUserModal = new EditUserModal(page);
					await editUserModal.setField(testCase.field, testCase.newValue);
					await editUserModal.saveAndClose();
				} else {
					// Role change via clicking role button
					await adminUsersPage.setUserRowRole(targetUser.idx, testCase.newValue);
				}
			});

			/**
			 * Verifies user state by logging in as the user in a new browser context.
			 */
			const verifyUserState = async (expected: ExpectedUserState) => {
				const newContext = await page.context().browser()!.newContext();
				const newPage = await newContext.newPage();

				try {
					await newPage.goto('/auth');
					const loginPage = new AuthPage(newPage);
					await loginPage.switchPageModeIfNeeded(AuthMode.SignIn);
					await loginPage.signIn({
						email: expected.email,
						password: expected.password,
						name: expected.name,
						role: expected.role
					});
					await expect(newPage).toHaveURL('/');

					const verifyHomePage = new HomePage(newPage);
					await verifyHomePage.toast.assertToastIsVisible('success');
					await verifyHomePage.assertUserRole(expected.role);
					await verifyHomePage.openSidebarIfClosed();
					await verifyHomePage.assertUserName(expected.name);
				} finally {
					await newContext.close();
				}
			};

			await test.step(`Verify ${testCase.field} has been changed`, async () => {
				await verifyUserState(expectedState);
			});

			await test.step(`Revert ${testCase.field} to original`, async () => {
				// Need to find the user again (may have moved due to sorting/pagination)
				await adminUsersPage.searchForUser(expectedState.email);
				await adminUsersPage.pagination.firstPage(); // using search doesn't automatically change the current page
				// TODO that's a bug, we should fix it
				await adminUsersPage.waitForUsersToLoad();

				// Get the user (should be first result after search)
				const users = await adminUsersPage.getUsersOnPage();
				const updatedUser = users.find((u) => u.email === expectedState.email);
				expect(updatedUser).toBeDefined();

				if (testCase.isModalField) {
					await adminUsersPage.clickUserRowEditButton(updatedUser!.idx);
					const editUserModal = new EditUserModal(page);
					await editUserModal.setField(testCase.field, originalState[testCase.field]);
					await editUserModal.saveAndClose();
				} else {
					await adminUsersPage.setUserRowRole(updatedUser!.idx, originalState.role);
				}
			});

			await test.step(`Verify ${testCase.field} has been reverted`, async () => {
				await verifyUserState(originalState);
			});
		});
	}
});

import { randomUUID } from 'crypto';
import { DEFAULT_PASSWORD, SHARED_USERS, generateUsersCSV, type TestUser } from '../data/users';
import { expect, test, type Page } from '@playwright/test';
import { AdminSettingsGeneralTab } from '../pages/Admin/AdminSettingsGeneralTab';
import { AdminUsersPage, type UserInfo } from '../pages/Admin/AdminUsersPage';
import { AddUserModal } from '../pages/Admin/modals/AddUserModal';
import { EditUserModal, type EditUserModaEditableField } from '../pages/Admin/modals/EditUserModal';
import { AuthMode, AuthPage } from '../pages/AuthPage';
import { HomePage } from '../pages/HomePage';
import { MINI_MEDIATOR_SCENARIO_BASIC_CHAT } from '../data/miniMediatorScenarios';
import { ChatPage } from '../pages/ChatPage';
import { UserChatsModal } from '../pages/Admin/modals/UserChatsModal';
import { SharedChatPage } from '../pages/SharedChatPage';
import type { SentMessage } from '../pages/BaseChatPage';

type UserRole = 'admin' | 'user' | 'pending';

/**
 * Creates a unique test user for this specific test run.
 * Uses a random UUID to ensure no collisions with parallel tests.
 */
function createUniqueTestUser(testName: string, role: UserRole = 'admin'): TestUser {
	const uniqueId = randomUUID().slice(0, 8);
	return {
		name: `Test-${uniqueId}`,
		email: `test-${uniqueId}@usertest.local`,
		password: DEFAULT_PASSWORD,
		role
	};
}

/** Expected user state for verification */
type ExpectedUserState = {
	name: string;
	email: string;
	password: string;
	role: UserRole;
};

// Test case definitions
// newValue can be a string or a function that returns a string (for dynamic values like email)
type UserFieldTestCase =
	| {
			field: EditUserModaEditableField;
			newValue: string | (() => string);
			isModalField: true;
	  }
	| {
			field: 'role';
			newValue: UserRole;
			isModalField: false;
	  };

const testCases: UserFieldTestCase[] = [
	{ field: 'name', newValue: 'RenamedTestUser', isModalField: true },
	{
		field: 'email',
		newValue: () => `renamed-${randomUUID().slice(0, 8)}@usertest.local`,
		isModalField: true
	},
	{ field: 'password', newValue: `${DEFAULT_PASSWORD}_CHANGED`, isModalField: true },
	{ field: 'role', newValue: 'user', isModalField: false }
];

/** Resolves a newValue - if it's a function, call it; otherwise return as-is */
function resolveNewValue(value: string | (() => string)): string {
	return typeof value === 'function' ? value() : value;
}

test.describe('User Management Test', { tag: '@smoke' }, () => {
	/**
	 * Helper to sign in as admin and navigate to users page
	 */
	async function signInAsAdmin(page: import('@playwright/test').Page) {
		await page.goto('/', { waitUntil: 'load' });
		const authPage = new AuthPage(page);
		await authPage.switchPageModeIfNeeded(AuthMode.SignIn);
		await authPage.signIn(SHARED_USERS.preExistingAdmin);
		await authPage.toast.assertToastIsVisible('success');
		await expect(page).toHaveURL('/');
		return new HomePage(page);
	}

	/**
	 * Helper to navigate to admin users page
	 */
	async function goToAdminUsersPage(page: import('@playwright/test').Page, homePage: HomePage) {
		await homePage.clickUserMenuButton();
		await homePage.userMenu.clickAdminPanel();
		const adminSettings = new AdminSettingsGeneralTab(page);
		await adminSettings.clickUsersPageButton();
		const adminUsersPage = new AdminUsersPage(page);
		await adminUsersPage.waitForUsersToLoad();
		return adminUsersPage;
	}

	/**
	 * Helper to create a test user via CSV import
	 */
	async function createTestUser(
		page: import('@playwright/test').Page,
		adminUsersPage: AdminUsersPage,
		user: TestUser
	) {
		await adminUsersPage.clickAddUserButton();
		const addUserModal = new AddUserModal(page);
		await addUserModal.clickCSVImportTabButton();
		await addUserModal.uploadCSVFile({
			name: 'user.csv',
			mimeType: 'text/csv',
			buffer: Buffer.from(generateUsersCSV([user]))
		});
		await addUserModal.saveAndClose();
		await addUserModal.close();
	}

	/**
	 * Helper to find a user by email on the current page
	 */
	async function findUserByEmail(adminUsersPage: AdminUsersPage, email: string): Promise<UserInfo> {
		await adminUsersPage.searchForUser(email);
		await adminUsersPage.waitForUsersToLoad();
		const users = await adminUsersPage.getUsersOnPage();
		const foundUser = users.find((u) => u.email === email);
		expect(foundUser, `User with email ${email} not found`).toBeDefined();
		return foundUser!;
	}

	for (const testCase of testCases) {
		test(`Verify admin can edit another user's ${testCase.field}`, async ({ page }) => {
			// Create a unique user for THIS test
			const testUser = createUniqueTestUser(testCase.field);
			// Resolve newValue once per test run (important for dynamic values like email)
			const newValue =
				testCase.field === 'role' ? testCase.newValue : resolveNewValue(testCase.newValue);
			let targetUser: UserInfo;
			let originalState: ExpectedUserState;
			let expectedState: ExpectedUserState;

			const homePage = await signInAsAdmin(page);
			const adminUsersPage = await goToAdminUsersPage(page, homePage);

			await test.step('Create test user', async () => {
				await createTestUser(page, adminUsersPage, testUser);
			});

			await test.step(`Change user ${testCase.field}`, async () => {
				targetUser = await findUserByEmail(adminUsersPage, testUser.email);

				// Store original state
				originalState = {
					name: targetUser.name,
					email: targetUser.email,
					password: DEFAULT_PASSWORD,
					role: targetUser.role
				};

				// Calculate expected state after change
				expectedState = { ...originalState };
				if (testCase.field === 'role') {
					expectedState.role = newValue as UserRole;
				} else {
					expectedState[testCase.field] = newValue;
				}

				// Apply the change
				if (testCase.isModalField) {
					await adminUsersPage.clickUserRowEditButton(targetUser.idx);
					const editUserModal = new EditUserModal(page);
					await editUserModal.setField(testCase.field, newValue);
					await editUserModal.saveAndClose();
				} else {
					await adminUsersPage.setUserRowRole(targetUser.idx, newValue as UserRole);
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
				// Find the user by their (possibly changed) email
				const updatedUser = await findUserByEmail(adminUsersPage, expectedState.email);

				if (testCase.isModalField) {
					await adminUsersPage.clickUserRowEditButton(updatedUser.idx);
					const editUserModal = new EditUserModal(page);
					await editUserModal.setField(testCase.field, originalState[testCase.field]);
					await editUserModal.saveAndClose();
				} else {
					await adminUsersPage.setUserRowRole(updatedUser.idx, originalState.role);
				}
			});

			await test.step(`Verify ${testCase.field} has been reverted`, async () => {
				await verifyUserState(originalState);
			});
		});
	}

	test('Verify admin can delete a user', async ({ page }) => {
		const testUser = createUniqueTestUser('delete', 'user');

		const homePage = await signInAsAdmin(page);
		const adminUsersPage = await goToAdminUsersPage(page, homePage);

		await test.step('Create test user', async () => {
			await createTestUser(page, adminUsersPage, testUser);
		});

		await test.step('Delete user', async () => {
			const foundUser = await findUserByEmail(adminUsersPage, testUser.email);
			await adminUsersPage.clickUserRowDeleteButton(foundUser.idx);
		});

		await test.step('Verify user is deleted', async () => {
			await adminUsersPage.searchForUser(testUser.email);
			// Wait a moment for search to complete, but don't require rows to be visible
			// since the user should be deleted
			await page.waitForTimeout(500);
			const users = await adminUsersPage.getUsersOnPage();
			const deletedUser = users.find((u) => u.email === testUser.email);
			expect(deletedUser, 'Deleted user should not be found').toBeUndefined();
		});
	});

	test("Verify admin can view another user's chats", async ({ page }) => {
		const scenario = MINI_MEDIATOR_SCENARIO_BASIC_CHAT;
		const inputMessage = scenario.getInput();
		const model = scenario.model;
		const expectedResponse = scenario.getOutput();
		const numChats = 3;
		const messages: SentMessage[] = [];
		let sharedChatPage: Page | null = null; // Store the new page for use in later steps

		const testUser = createUniqueTestUser('view chats', 'user'); // MUST be user role to view their chats!
		const homePage = await signInAsAdmin(page);
		const adminUsersPage = await goToAdminUsersPage(page, homePage);
		await test.step('Create test user', async () => {
			await createTestUser(page, adminUsersPage, testUser);
		});

		const createChatsForUser = async (user: TestUser) => {
			const newContext = await page.context().browser()!.newContext();
			const newPage = await newContext.newPage();

			try {
				await newPage.goto('/auth');
				const loginPage = new AuthPage(newPage);
				await loginPage.switchPageModeIfNeeded(AuthMode.SignIn);
				await loginPage.signIn({
					email: user.email,
					password: user.password,
					name: user.name,
					role: user.role
				});
				await expect(newPage).toHaveURL('/');

				const homePage = new HomePage(newPage);
				await homePage.toast.assertToastIsVisible('success');

				for (let i = 0; i < numChats; i++) {
					await homePage.modelSelector.open();
					await homePage.modelSelector.selectModel(model);

					messages.push(await homePage.submitMessageAndCaptureIds(inputMessage));

					const chatPage = new ChatPage(newPage);
					await chatPage.assertAssistantMessageExists(
						messages[messages.length - 1].responseMessageIds[0]
					);
					await chatPage.assertAssistantMessageText(
						messages[messages.length - 1].responseMessageIds[0],
						expectedResponse
					);
					await chatPage.openSidebarIfClosed();
					await chatPage.clickNewChatButton();
				}
			} catch (error) {
				console.error('Error creating chats for user:', error);
			} finally {
				await newContext.close();
			}
		};

		await test.step('Create chats for user', async () => {
			await createChatsForUser(testUser);
		});

		await test.step('View user chats', async () => {
			const foundUser = await findUserByEmail(adminUsersPage, testUser.email);
			await adminUsersPage.clickUserRowChatsButton(foundUser.idx);
			const userChatsModal = new UserChatsModal(page);
			await userChatsModal.waitForVisible();
			const numberOfChats = await userChatsModal.getNumberOfChats();
			expect(numberOfChats, 'Number of chats should be 3').toBe(numChats);

			// Wait for the new page to open (chat title opens in new tab with target="_blank")
			const [newPage] = await Promise.all([
				page.context().waitForEvent('page'),
				userChatsModal.clickChatTitle(1) // click the second chat
			]);

			// Wait for the new page to load
			await newPage.waitForLoadState('networkidle');

			// Store the new page for use in later steps
			sharedChatPage = newPage;

			const sharedChatPageObj = new SharedChatPage(newPage);
			await sharedChatPageObj.assertUserMessageExists(messages[1].userMessageId);
			await sharedChatPageObj.assertUserMessageText(messages[1].userMessageId, inputMessage);
			await sharedChatPageObj.assertAssistantMessageExists(messages[1].responseMessageIds[0]);
			await sharedChatPageObj.assertAssistantMessageText(
				messages[1].responseMessageIds[0],
				expectedResponse
			);
		});

		// make sure cloning works just fine too
		await test.step('Clone chat', async () => {
			if (!sharedChatPage) {
				throw new Error('Shared chat page was not opened in previous step');
			}
			const sharedChatPageObj = new SharedChatPage(sharedChatPage);
			await sharedChatPageObj.clickCloneChatButton();
			// Clone button navigates in the same page, so use the same page
			const chatPage = new ChatPage(sharedChatPage);
			await chatPage.assertUserMessageExists(messages[1].userMessageId);
			await chatPage.assertUserMessageText(messages[1].userMessageId, inputMessage);
			await chatPage.assertAssistantMessageExists(messages[1].responseMessageIds[0]);
			await chatPage.assertAssistantMessageText(
				messages[1].responseMessageIds[0],
				expectedResponse
			);
		});
	});
});

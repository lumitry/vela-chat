import { test } from '../fixtures/testUser';
import { HomePage } from '../pages/HomePage';
import { AdminSettingsGeneralTab } from '../pages/Admin/AdminSettingsGeneralTab';
import { AdminSettingsModelsTab } from '../pages/Admin/AdminSettingsModelsTab';
import {
	MINI_MEDIATOR_MODELS_CRUD_DESCRIPTION_OLLAMA,
	MINI_MEDIATOR_MODELS_CRUD_DESCRIPTION_OPENAI,
	MINI_MEDIATOR_MODELS_CRUD_RENAME_OLLAMA,
	MINI_MEDIATOR_MODELS_CRUD_RENAME_OPENAI
} from '../data/miniMediatorModels';
import { ModelEditorPage } from '../pages/Admin/ModelEditorPage';
import { AdminSettingsInterfaceTab } from '../pages/Admin/AdminSettingsInterface';
import { AdminEvaluationsPage } from '../pages/Admin/AdminEvaluationsPage';
import { ChatPage } from '../pages/ChatPage';
import { ChatInfoModal } from '../pages/modals/ChatInfoModal';
import { generateRandomString } from '../data/random';
import { CHANGE_MODEL_COMMAND } from '../data/commandPalette';

['openai', 'ollama'].forEach((provider) => {
	test.describe(`Admin Models CRUD Test - ${provider}`, () => {
		test('Change model name', async ({ page }) => {
			const model =
				provider === 'openai'
					? MINI_MEDIATOR_MODELS_CRUD_RENAME_OPENAI
					: MINI_MEDIATOR_MODELS_CRUD_RENAME_OLLAMA;
			const modelId = model.getFullIdWithEndpointPrefix();
			const originalModelName = model.name;

			// Navigate to model editor
			await test.step('Navigate to model editor', async () => {
				const homePage = new HomePage(page);
				await homePage.clickUserMenuButton();
				await homePage.userMenu.clickAdminPanel();
				const adminSettings = new AdminSettingsGeneralTab(page);
				await adminSettings.clickModelsTabButton();
				const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
				await adminSettingsModelsTab.clickModelItemEditButton(modelId);
			});

			// Change model name
			const newModelName = `Test Model ${generateRandomString(5)}`;
			await test.step('Change model name', async () => {
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setName(newModelName);
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Helper function to assert model name appears correctly in all locations
			const assertModelNameInAllLocations = async (
				expectedModelName: string,
				expectedModelId: string
			) => {
				await test.step('Verify model name in Admin Settings Models tab', async () => {
					const adminSettings = new AdminSettingsGeneralTab(page);
					await adminSettings.clickModelsTabButton();
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.searchForModel(expectedModelName);
					// Note: We don't assert the count is exactly 1 because when reverting to the original
					// name "mini-mediator:anonymous", parallel tests might have models with the same name.
					// The important thing is that our specific model (by ID) exists with the correct name.
					await adminSettingsModelsTab.assertModelItemWithNameExists(
						expectedModelId,
						expectedModelName
					);
				});

				await test.step('Verify model name in Admin Settings Interface tab', async () => {
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.clickInterfaceTabButton();
					const adminSettingsInterfaceTab = new AdminSettingsInterfaceTab(page);
					await adminSettingsInterfaceTab.assertModelOptionExists(
						provider as 'ollama' | 'openai',
						expectedModelName,
						expectedModelId
					);
				});

				await test.step('Verify model name in Admin Evaluations page (leaderboard)', async () => {
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.clickEvaluationsPageButton();
					const adminEvaluationsPage = new AdminEvaluationsPage(page);
					await adminEvaluationsPage.assertLeaderboardModelNameExists(
						expectedModelId,
						expectedModelName
					);
				});

				await test.step('Verify model name in Home Page (new chat)', async () => {
					// Navigate to home page from wherever we are
					const homePage = new HomePage(page);
					await homePage.clickNewChatButton();
					await homePage.modelSelector.open();
					await homePage.modelSelector.assertModelNameExists(expectedModelId, expectedModelName);
					await homePage.modelSelector.selectModel(expectedModelId);
					await homePage.modelSelector.assertCurrentModelName(expectedModelName);
					await homePage.assertPlaceholderCurrentModelName(expectedModelName);
				});

				await test.step('Verify model name in chat response message', async () => {
					const homePage = new HomePage(page);
					const { responseMessageIds } =
						await homePage.submitMessageAndCaptureIds('Hello, how are you?');
					const responseMessageId = responseMessageIds[0];
					const chatPage = new ChatPage(page);
					// we are not verifying the content of the response message - just the model name!
					await chatPage.assertResponseMessageHasModelName(responseMessageId, expectedModelName);
				});

				await test.step('Verify model name in commands container (@model)', async () => {
					const chatPage = new ChatPage(page);
					// the commands container doesn't support spaces in the model name
					await chatPage.typeMessage('@' + expectedModelName.replaceAll(' ', ''));
					await chatPage.assertModelNameInCommands(expectedModelId, expectedModelName);
					// Clear the input for the next step
					await chatPage.typeMessage('');
				});

				await test.step('Verify model name in Chat Info modal', async () => {
					const chatPage = new ChatPage(page);
					const chatInfoModal = new ChatInfoModal(page);
					await chatPage.clickChatInfoButton();
					// Use assertUniqueModelLabel with model ID to avoid strict mode violations
					// when model name equals model ID (both label and ID would show same text)
					await chatInfoModal.assertUniqueModelLabel(expectedModelId, expectedModelName);
					await chatInfoModal.close();
				});

				await test.step('Verify model name in Command Palette', async () => {
					const chatPage = new ChatPage(page);
					await chatPage.commandPalette.open();
					await chatPage.commandPalette.typeCommand(CHANGE_MODEL_COMMAND.label);
					await chatPage.commandPalette.clickCommand(CHANGE_MODEL_COMMAND.id);
					await chatPage.commandPalette.submitCommand();
					await chatPage.commandPalette.assertSubmenuItemContainsText(
						'model:' + expectedModelId,
						expectedModelName
					);
					// Close command palette - waits for it to actually close
					await chatPage.commandPalette.close();
					// we don't verify that clicking the submenu item changes the model because that's to be tested in the command palette test!
				});
			};

			// Assert model name appears correctly with new name
			await assertModelNameInAllLocations(newModelName, modelId);

			// Revert model name back to original
			await test.step('Revert model name to original', async () => {
				// Navigate back to admin settings from wherever we are
				// We might be on chat page, home page, or admin settings
				const currentUrl = page.url();
				if (!currentUrl.includes('/admin')) {
					const homePage = new HomePage(page);
					await homePage.clickUserMenuButton();
					await homePage.userMenu.clickAdminPanel();
				}
				const adminSettings = new AdminSettingsGeneralTab(page);
				await adminSettings.clickModelsTabButton();
				const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
				await adminSettingsModelsTab.clickModelItemEditButton(modelId);
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setName(originalModelName);
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Assert model name appears correctly with original name (verifies stores are intact)
			await assertModelNameInAllLocations(originalModelName, modelId);
		});

		test('Change model description', async ({ page }) => {
			const model =
				provider === 'openai'
					? MINI_MEDIATOR_MODELS_CRUD_DESCRIPTION_OPENAI
					: MINI_MEDIATOR_MODELS_CRUD_DESCRIPTION_OLLAMA;
			const modelId = model.getFullIdWithEndpointPrefix();
			const modelName = model.name;
			const originalModelDescription = null; // models have no description by default

			// Navigate to model editor
			await test.step('Navigate to model editor', async () => {
				const homePage = new HomePage(page);
				await homePage.clickUserMenuButton();
				await homePage.userMenu.clickAdminPanel();
				const adminSettings = new AdminSettingsGeneralTab(page);
				await adminSettings.clickModelsTabButton();
				const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
				await adminSettingsModelsTab.clickModelItemEditButton(modelId);
			});

			// Change model name
			const newModelDescription = `Test Model Description ${generateRandomString(5)}`;
			await test.step('Change model description', async () => {
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setDescription(newModelDescription);
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Helper function to assert model description appears correctly in all locations
			const assertModelDescriptionInAllLocations = async (
				expectedModelDescription: string | null,
				modelId: string
			) => {
				// Calculate the actual description that will be shown in the UI
				// When description is null/empty, the UI shows:
				// - For Ollama: `${modelId} (mini-mediator)`
				// - For OpenAI: `${modelId}`
				const actualExpectedDescription =
					expectedModelDescription && expectedModelDescription.trim() !== ''
						? expectedModelDescription
						: provider === 'ollama'
							? `${modelId} (mini-mediator)`
							: modelId;

				await test.step('Verify model description in Admin Settings Models tab', async () => {
					const adminSettings = new AdminSettingsGeneralTab(page);
					await adminSettings.clickModelsTabButton();
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.searchForModel(modelName);
					await adminSettingsModelsTab.assertModelItemWithDescriptionExists(
						modelId,
						actualExpectedDescription
					);
				});

				await test.step('Verify model description in Home Page (new chat)', async () => {
					// Navigate to home page from wherever we are
					const homePage = new HomePage(page);
					await homePage.clickNewChatButton();
					await homePage.modelSelector.open();
					await homePage.modelSelector.assertModelDescription(modelId, expectedModelDescription);
					await homePage.modelSelector.selectModel(modelId);
					await homePage.assertPlaceholderDescription(expectedModelDescription);
				});
			};

			// Assert model description appears correctly with new description
			await assertModelDescriptionInAllLocations(newModelDescription, modelId);

			// Revert model description back to original
			await test.step('Revert model description to original', async () => {
				// Navigate back to admin settings from wherever we are
				// We might be on chat page, home page, or admin settings
				const currentUrl = page.url();
				if (!currentUrl.includes('/admin')) {
					const homePage = new HomePage(page);
					await homePage.clickUserMenuButton();
					await homePage.userMenu.clickAdminPanel();
				}
				const adminSettings = new AdminSettingsGeneralTab(page);
				await adminSettings.clickModelsTabButton();
				const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
				await adminSettingsModelsTab.clickModelItemEditButton(modelId);
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setDescription(originalModelDescription ?? '');
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Assert model description appears correctly with original description (verifies stores are intact)
			await assertModelDescriptionInAllLocations(originalModelDescription, modelId);
		});

		// TODO image change and assertions

		// TODO tags change and assertions. unless we want a separate tags test?

		// TODO visibility settings change and assertions (would require multiple accounts and groups i think... this might also need to be a separate test)

		// TODO hide model and assertions

		// TODO disable model and assertions
	});
});

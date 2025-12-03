import { test } from '../fixtures/testUser';
import { HomePage } from '../pages/HomePage';
import { AdminSettingsGeneralTab } from '../pages/Admin/AdminSettingsGeneralTab';
import { AdminSettingsModelsTab } from '../pages/Admin/AdminSettingsModelsTab';
import {
	MINI_MEDIATOR_MODELS_CRUD_DESCRIPTION_OLLAMA,
	MINI_MEDIATOR_MODELS_CRUD_DESCRIPTION_OPENAI,
	MINI_MEDIATOR_MODELS_CRUD_DISABLE_OLLAMA,
	MINI_MEDIATOR_MODELS_CRUD_DISABLE_OPENAI,
	MINI_MEDIATOR_MODELS_CRUD_HIDE_OLLAMA,
	MINI_MEDIATOR_MODELS_CRUD_HIDE_OPENAI,
	MINI_MEDIATOR_MODELS_CRUD_IMAGE_OLLAMA,
	MINI_MEDIATOR_MODELS_CRUD_IMAGE_OPENAI,
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
import { DEFAULT_MODEL_IMAGE, FRONTEND_BASE_URL } from '../data/constants';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { resizeImageTo250x250 } from '../utils/imageResize';
import { WorkspaceMetricsPage } from '../pages/workspace/WorkspaceMetricsPage';
import { WorkspaceModelsPage } from '../pages/workspace/WorkspaceModelsPage';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

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

				// TODO Not testing this for now because model names in metrics only update after a server restart!
				// (marking as a TODO because I'd like to change that at some point!)
				// await test.step('Verify model name in Workspace Metrics page', async () => {
				// 	const chatPage = new ChatPage(page);
				// 	await chatPage.clickWorkspaceButton();
				// 	const workspaceModelsPage = new WorkspaceModelsPage(page);
				// 	await workspaceModelsPage.clickMetricsPageButton();
				// 	const workspaceMetricsPage = new WorkspaceMetricsPage(page);

				// 	await workspaceMetricsPage.assertModelUsageTableRowName(
				// 		expectedModelId,
				// 		expectedModelName
				// 	);

				// 	// go back to home page for later steps
				// 	await workspaceMetricsPage.clickNewChatButton();
				// });
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

		// Change model image and verify in all locations
		// we do this by first uploading a new image, waiting for it to be saved, verifying the content, and then using the URL for all assertions.
		// this means we assume that one image URL always points to the same image, which is SUPPOSED to be the case!
		// in other words, we only verify the content of the image once, and then use the URL for all assertions after that.
		// but we DO try changing the image a second time and verifying the content (plus all the URL locations) again, so this should hopefully catch any major issues with image URLs.
		test('Change model image', async ({ page }) => {
			const model =
				provider === 'openai'
					? MINI_MEDIATOR_MODELS_CRUD_IMAGE_OPENAI
					: MINI_MEDIATOR_MODELS_CRUD_IMAGE_OLLAMA;
			const modelId = model.getFullIdWithEndpointPrefix();
			const modelName = model.name;
			const originalModelImage = `${FRONTEND_BASE_URL}${DEFAULT_MODEL_IMAGE}`;
			const newModelImageBuffer = readFileSync(join(__dirname, '../data/newModelImage.png'));
			const secondNewModelImageBuffer = readFileSync(
				join(__dirname, '../data/secondNewModelImage.png')
			);

			// Helper function to assert model image appears correctly in all locations
			const assertModelImageInAllLocations = async (expectedImageUrl: string, modelId: string) => {
				await test.step('Verify model image in Admin Settings Models tab', async () => {
					const adminSettings = new AdminSettingsGeneralTab(page);
					await adminSettings.clickModelsTabButton();
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.searchForModel(modelName);
					await adminSettingsModelsTab.assertModelItemWithImageExists(modelId, expectedImageUrl);
				});

				await test.step('Verify model image in Admin Evaluations page (leaderboard)', async () => {
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.clickEvaluationsPageButton();
					const adminEvaluationsPage = new AdminEvaluationsPage(page);
					await adminEvaluationsPage.assertLeaderboardModelImageExists(modelId, expectedImageUrl);
				});

				await test.step('Verify model image in Home Page (new chat)', async () => {
					const homePage = new HomePage(page);
					await homePage.clickNewChatButton();
					await homePage.modelSelector.open();
					await homePage.modelSelector.assertModelImage(modelId, expectedImageUrl);
					await homePage.modelSelector.selectModel(modelId);
					await homePage.assertPlaceholderCurrentModelImage(expectedImageUrl);
				});

				await test.step('Verify model image in chat response message', async () => {
					const homePage = new HomePage(page);
					const { responseMessageIds } =
						await homePage.submitMessageAndCaptureIds('Hello, how are you?');
					const responseMessageId = responseMessageIds[0];
					const chatPage = new ChatPage(page);
					await chatPage.assertResponseMessageHasModelImage(responseMessageId, expectedImageUrl);
				});

				await test.step('Verify model image in commands container (@model)', async () => {
					const chatPage = new ChatPage(page);
					// the commands container doesn't support spaces in the model name
					await chatPage.typeMessage('@' + modelName.replaceAll(' ', ''));
					await chatPage.assertModelImageInCommands(modelId, expectedImageUrl);
					// Clear the input for the next step
					await chatPage.typeMessage('');
				});

				await test.step('Verify model image in Chat Info modal', async () => {
					const chatPage = new ChatPage(page);
					const chatInfoModal = new ChatInfoModal(page);
					await chatPage.clickChatInfoButton();
					await chatInfoModal.assertUniqueModelImage(modelId, expectedImageUrl);
					await chatInfoModal.close();
				});

				await test.step('Verify model image in Workspace Metrics page', async () => {
					const chatPage = new ChatPage(page);
					await chatPage.clickWorkspaceButton();
					const workspaceModelsPage = new WorkspaceModelsPage(page);
					await workspaceModelsPage.clickMetricsPageButton();
					const workspaceMetricsPage = new WorkspaceMetricsPage(page);

					await workspaceMetricsPage.assertModelUsageTableRowImage(modelId, expectedImageUrl);

					// go back to home page for later steps
					await workspaceMetricsPage.clickNewChatButton();
				});
			};

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

			// First image upload
			await test.step('Upload first model image', async () => {
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setModelImage({
					name: 'newModelImage.png',
					mimeType: 'image/png',
					buffer: newModelImageBuffer
				});
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Wait for image to be saved, verify content once, then use URL for all assertions
			const firstImageUrl =
				await test.step('Wait for first image to be saved and verify content', async () => {
					const adminSettings = new AdminSettingsGeneralTab(page);
					await adminSettings.clickModelsTabButton();
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.searchForModel(modelName);
					// Wait for the image URL to be a file URL (not data: or favicon)
					const imageUrl = await adminSettingsModelsTab.waitForModelImageToBeSaved(modelId);

					// Verify once that the saved image matches the resized original
					const resizedExpectedBuffer = await resizeImageTo250x250(page, newModelImageBuffer);
					await adminSettingsModelsTab.assertModelItemImageContentMatches(
						modelId,
						resizedExpectedBuffer
					);

					return imageUrl;
				});

			// Assert model image URL appears correctly with first image in all locations
			await assertModelImageInAllLocations(firstImageUrl, modelId);

			// Second image upload
			await test.step('Upload second model image', async () => {
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
				await modelEditor.setModelImage({
					name: 'secondNewModelImage.png',
					mimeType: 'image/png',
					buffer: secondNewModelImageBuffer
				});
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Wait for image to be saved, verify content once, then use URL for all assertions
			const secondImageUrl =
				await test.step('Wait for second image to be saved and verify content', async () => {
					const adminSettings = new AdminSettingsGeneralTab(page);
					await adminSettings.clickModelsTabButton();
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.searchForModel(modelName);
					// Wait for the image URL to be a file URL (not data: or favicon or first image URL)
					const imageUrl = await adminSettingsModelsTab.waitForModelImageToBeSaved(
						modelId,
						firstImageUrl
					);

					// Verify once that the saved image matches the resized original
					const resizedExpectedBuffer = await resizeImageTo250x250(page, secondNewModelImageBuffer);
					await adminSettingsModelsTab.assertModelItemImageContentMatches(
						modelId,
						resizedExpectedBuffer
					);

					return imageUrl;
				});

			// Assert model image URL appears correctly with second image in all locations
			await assertModelImageInAllLocations(secondImageUrl, modelId);

			// Revert model image back to original (reset to default)
			await test.step('Revert model image to original', async () => {
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
				// Reset image to default by clicking the reset button
				await modelEditor.clickResetImageButton();
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Assert model image appears correctly with original image (verifies stores are intact)
			await assertModelImageInAllLocations(originalModelImage, modelId);
		});

		test('Hide model', async ({ page }) => {
			const model =
				provider === 'openai'
					? MINI_MEDIATOR_MODELS_CRUD_HIDE_OPENAI
					: MINI_MEDIATOR_MODELS_CRUD_HIDE_OLLAMA;
			const modelId = model.getFullIdWithEndpointPrefix();
			const modelName = `Hide Test Model ${generateRandomString(5)}`;
			// We will change the image for this model too.
			// This unfortunately couples it to the change model image test a little, but it's important to differentiate between this test and the disable model test!
			const newModelImageBuffer = readFileSync(join(__dirname, '../data/newModelImage.png'));
			// same thing for description!
			const modelDescription = `Hide Test Model Description ${generateRandomString(5)}`;

			await test.step('Set up model for hide test', async () => {
				const homePage = new HomePage(page);
				await homePage.clickUserMenuButton();
				await homePage.userMenu.clickAdminPanel();
				const adminSettings = new AdminSettingsGeneralTab(page);
				await adminSettings.clickModelsTabButton();
				const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
				await adminSettingsModelsTab.clickModelItemEditButton(modelId);
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setModelImage({
					name: 'newModelImage.png',
					mimeType: 'image/png',
					buffer: newModelImageBuffer
				});
				await modelEditor.setDescription(modelDescription);
				await modelEditor.setName(modelName);
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Wait for image to be saved, verify content once, then use URL for all assertions
			const expectedImageUrl =
				await test.step('Wait for first image to be saved and verify content', async () => {
					const adminSettings = new AdminSettingsGeneralTab(page);
					await adminSettings.clickModelsTabButton();
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.searchForModel(modelName);
					// Wait for the image URL to be a file URL (not data: or favicon)
					const imageUrl = await adminSettingsModelsTab.waitForModelImageToBeSaved(modelId);

					// Verify once that the saved image matches the resized original
					const resizedExpectedBuffer = await resizeImageTo250x250(page, newModelImageBuffer);
					await adminSettingsModelsTab.assertModelItemImageContentMatches(
						modelId,
						resizedExpectedBuffer
					);

					return imageUrl;
				});

			let chatId: string;
			let responseMessageId: string;

			// creates a new chat with the model & sets it as the default model. this is for future assertions.
			await test.step('Create new chat with not-yet-hidden model', async () => {
				const homePage = new HomePage(page);
				await homePage.clickNewChatButton();
				await homePage.modelSelector.open();
				await homePage.modelSelector.selectModel(modelId);
				await homePage.modelSelector.setCurrentModelAsDefault();

				// we do these assertions here to make the test fail early if these assertions are broken, since we will need to do them anyway later, and it would be better to fail in the setup when it's clear that something is wrong with these assertions rather than the model hide functionality itself.
				await homePage.assertPlaceholderCurrentModelName(modelName);
				await homePage.assertPlaceholderCurrentModelImage(expectedImageUrl);
				await homePage.assertPlaceholderDescription(modelDescription);

				const { responseMessageIds } =
					await homePage.submitMessageAndCaptureIds('Hello, how are you?');
				responseMessageId = responseMessageIds[0];
				const chatPage = new ChatPage(page);
				await chatPage.assertResponseMessageHasModelName(responseMessageId, modelName);
				await chatPage.assertResponseMessageHasModelImage(responseMessageId, expectedImageUrl);
				chatId = await chatPage.getChatId();
			});

			// Helper function to assert model hide state appears correctly in all locations
			const assertModelHideStateInAllLocations = async (expectedHideState: boolean) => {
				await test.step('Verify model hide state in Admin Settings Models tab', async () => {
					const adminSettings = new AdminSettingsGeneralTab(page);
					await adminSettings.clickModelsTabButton();
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.searchForModel(modelName);
					await adminSettingsModelsTab.assertModelItemHideState(modelId, expectedHideState);
				});

				await test.step('Verify model appears in Admin Settings Interface tab', async () => {
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.clickInterfaceTabButton();
					const adminSettingsInterfaceTab = new AdminSettingsInterfaceTab(page);
					// will always exist, regardless of hide state
					await adminSettingsInterfaceTab.assertModelOptionExists(
						provider as 'ollama' | 'openai',
						modelName,
						modelId
					);
				});

				await test.step('Verify model hide state in Admin Evaluations page (leaderboard)', async () => {
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.clickEvaluationsPageButton();
					const adminEvaluationsPage = new AdminEvaluationsPage(page);
					await adminEvaluationsPage.assertLeaderboardModelHideState(modelId, expectedHideState);
				});

				await test.step('Verify model hide state in Home Page (new chat)', async () => {
					const homePage = new HomePage(page);
					await homePage.clickNewChatButton();
					await homePage.modelSelector.open();
					// model will not apear in model selector if it is hidden, even if it is the default model!
					await homePage.modelSelector.assertModelHideState(modelId, expectedHideState);
					await homePage.modelSelector.close();
					// but the placeholder should still show the model name and image!
					await homePage.assertPlaceholderCurrentModelName(modelName);
					await homePage.assertPlaceholderCurrentModelImage(expectedImageUrl);
					await homePage.assertPlaceholderDescription(modelDescription);
				});

				// you can do this because it's your default model
				await test.step('Verify you can still make a new chat with the possibly-hidden model', async () => {
					const homePage = new HomePage(page);
					const { responseMessageIds } =
						await homePage.submitMessageAndCaptureIds('Hello, how are you?');
					const newResponseMessageId = responseMessageIds[0];
					const chatPage = new ChatPage(page);
					await chatPage.assertResponseMessageHasModelName(newResponseMessageId, modelName);
					await chatPage.assertResponseMessageHasModelImage(newResponseMessageId, expectedImageUrl);
					// go back to home page for later steps
					await chatPage.clickNewChatButton();
				});

				// this would not be true for disabled models
				await test.step('Verify the chat you made earlier still has the model name and image', async () => {
					const homePage = new HomePage(page);
					await homePage.clickChatById(chatId);
					const chatPage = new ChatPage(page);
					await chatPage.assertResponseMessageHasModelName(responseMessageId, modelName);
					await chatPage.assertResponseMessageHasModelImage(responseMessageId, expectedImageUrl);
				});

				await test.step('Verify model hide state in commands container (@model)', async () => {
					const chatPage = new ChatPage(page);
					// the commands container doesn't support spaces in the model name
					await chatPage.typeMessage('@' + modelName.replaceAll(' ', ''));
					await chatPage.assertModelHideState(modelId, expectedHideState);
					// Clear the input for the next step
					await chatPage.typeMessage('');
				});

				await test.step('Verify model name and image in Chat Info modal', async () => {
					const chatPage = new ChatPage(page);
					const chatInfoModal = new ChatInfoModal(page);
					await chatPage.clickChatInfoButton();
					// model metadata should still show here, even if it is hidden
					await chatInfoModal.assertUniqueModelLabel(modelId, modelName);
					await chatInfoModal.assertUniqueModelImage(modelId, expectedImageUrl);
					await chatInfoModal.close();
				});

				await test.step('Verify model hide state in Command Palette', async () => {
					const chatPage = new ChatPage(page);
					await chatPage.commandPalette.open();
					await chatPage.commandPalette.typeCommand(CHANGE_MODEL_COMMAND.label);
					await chatPage.commandPalette.clickCommand(CHANGE_MODEL_COMMAND.id);
					await chatPage.commandPalette.submitCommand();
					await chatPage.commandPalette.typeCommand(modelName);
					await chatPage.commandPalette.assertModelHideState(modelId, expectedHideState);
					await chatPage.commandPalette.close();
				});
			};

			// Hide model
			await test.step('Hide model', async () => {
				const currentUrl = page.url();
				if (!currentUrl.includes('/admin')) {
					const homePage = new HomePage(page);
					await homePage.clickUserMenuButton();
					await homePage.userMenu.clickAdminPanel();
				}
				const adminSettings = new AdminSettingsGeneralTab(page);
				await adminSettings.clickModelsTabButton();
				const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
				await adminSettingsModelsTab.searchForModel(modelName);
				await adminSettingsModelsTab.setModelItemHideState(modelId, true);
			});

			// Assert model hide state appears correctly with hidden state
			await assertModelHideStateInAllLocations(true);

			// Unhide model
			await test.step('Unhide model', async () => {
				const currentUrl = page.url();
				if (!currentUrl.includes('/admin')) {
					const homePage = new HomePage(page);
					await homePage.clickUserMenuButton();
					await homePage.userMenu.clickAdminPanel();
				}
				const adminSettings = new AdminSettingsGeneralTab(page);
				await adminSettings.clickModelsTabButton();
				const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
				await adminSettingsModelsTab.searchForModel(modelName);
				await adminSettingsModelsTab.setModelItemHideState(modelId, false);
			});

			// Assert model hide state appears correctly with unhidden state
			await assertModelHideStateInAllLocations(false);
		});

		test('Disable model', async ({ page }) => {
			const model =
				provider === 'openai'
					? MINI_MEDIATOR_MODELS_CRUD_DISABLE_OPENAI
					: MINI_MEDIATOR_MODELS_CRUD_DISABLE_OLLAMA;
			const modelId = model.getFullIdWithEndpointPrefix();
			const modelName = `Disable Test Model ${generateRandomString(5)}`;
			// We will change the image for this model too.
			// This unfortunately couples it to the change model image test a little, but it's important to differentiate between this test and the disable model test!
			const newModelImageBuffer = readFileSync(join(__dirname, '../data/newModelImage.png'));
			// same thing for description!
			const modelDescription = `Disable Test Model Description ${generateRandomString(5)}`;

			await test.step('Set up model for disable test', async () => {
				const homePage = new HomePage(page);
				await homePage.clickUserMenuButton();
				await homePage.userMenu.clickAdminPanel();
				const adminSettings = new AdminSettingsGeneralTab(page);
				await adminSettings.clickModelsTabButton();
				const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
				await adminSettingsModelsTab.clickModelItemEditButton(modelId);
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setModelImage({
					name: 'newModelImage.png',
					mimeType: 'image/png',
					buffer: newModelImageBuffer
				});
				await modelEditor.setDescription(modelDescription);
				await modelEditor.setName(modelName);
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Wait for image to be saved, verify content once, then use URL for all assertions
			const expectedImageUrl =
				await test.step('Wait for first image to be saved and verify content', async () => {
					const adminSettings = new AdminSettingsGeneralTab(page);
					await adminSettings.clickModelsTabButton();
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.searchForModel(modelName);
					// Wait for the image URL to be a file URL (not data: or favicon)
					const imageUrl = await adminSettingsModelsTab.waitForModelImageToBeSaved(modelId);

					// Verify once that the saved image matches the resized original
					const resizedExpectedBuffer = await resizeImageTo250x250(page, newModelImageBuffer);
					await adminSettingsModelsTab.assertModelItemImageContentMatches(
						modelId,
						resizedExpectedBuffer
					);

					return imageUrl;
				});

			let chatId: string;
			let responseMessageId: string;

			// creates a new chat with the model & sets it as the default model. this is for future assertions.
			await test.step('Create new chat with not-yet-disabled model', async () => {
				const homePage = new HomePage(page);
				await homePage.clickNewChatButton();
				await homePage.modelSelector.open();
				await homePage.modelSelector.selectModel(modelId);
				await homePage.modelSelector.setCurrentModelAsDefault();

				// we do these assertions here to make the test fail early if these assertions are broken, since we will need to do them anyway later, and it would be better to fail in the setup when it's clear that something is wrong with these assertions rather than the model hide functionality itself.
				await homePage.assertPlaceholderCurrentModelName(modelName);
				await homePage.assertPlaceholderCurrentModelImage(expectedImageUrl);
				await homePage.assertPlaceholderDescription(modelDescription);

				const { responseMessageIds } =
					await homePage.submitMessageAndCaptureIds('Hello, how are you?');
				responseMessageId = responseMessageIds[0];
				const chatPage = new ChatPage(page);
				await chatPage.assertResponseMessageHasModelName(responseMessageId, modelName);
				await chatPage.assertResponseMessageHasModelImage(responseMessageId, expectedImageUrl);
				chatId = await chatPage.getChatId();
			});

			// Helper function to assert model hide state appears correctly in all locations
			const assertModelDisableStateInAllLocations = async (expectedDisableState: boolean) => {
				await test.step('Verify model disable state in Admin Settings Models tab', async () => {
					const adminSettings = new AdminSettingsGeneralTab(page);
					await adminSettings.clickModelsTabButton();
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.searchForModel(modelName);
					await adminSettingsModelsTab.assertModelItemDisabledState(modelId, expectedDisableState);

					// TODO this is messy, but it stabilizes the test for now.
					await page.waitForTimeout(1000);
				});

				await test.step('Verify model appears in Admin Settings Interface tab', async () => {
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.clickInterfaceTabButton();
					const adminSettingsInterfaceTab = new AdminSettingsInterfaceTab(page);
					await adminSettingsInterfaceTab.assertPresenceOfModelOption(
						provider as 'ollama' | 'openai',
						modelName,
						modelId,
						!expectedDisableState // expectedPresence = !expectedDisableState
					);
				});

				await test.step('Verify model disable state in Admin Evaluations page (leaderboard)', async () => {
					const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
					await adminSettingsModelsTab.clickEvaluationsPageButton();
					const adminEvaluationsPage = new AdminEvaluationsPage(page);

					// reusing the assertLeaderboardModelHideState method here because it's the same logic
					await adminEvaluationsPage.assertLeaderboardModelHideState(modelId, expectedDisableState);
				});

				await test.step('Verify model disable state in Home Page (new chat)', async () => {
					const homePage = new HomePage(page);
					await homePage.clickNewChatButton();
					await homePage.modelSelector.open();
					// model will not apear in model selector if it is disabled, even if it is the default model!
					// reusing the assertModelHideState function here because it's the same logic
					await homePage.modelSelector.assertModelHideState(modelId, expectedDisableState);
					await homePage.modelSelector.close();
					await homePage.assertPlaceholderCurrentModelPresence(
						!expectedDisableState, // expectedPresence = !expectedDisableState
						modelName,
						expectedImageUrl,
						modelDescription
					);
				});

				await test.step('Verify the chat you made earlier still has the model name and image', async () => {
					const homePage = new HomePage(page);
					await homePage.clickChatById(chatId);
					const chatPage = new ChatPage(page);

					// disabled models show the model ID and default image instead of the set image and name
					const expectedModelName = expectedDisableState ? modelId : modelName;
					const expectedModelImageUrl = expectedDisableState
						? DEFAULT_MODEL_IMAGE
						: expectedImageUrl;

					await chatPage.assertResponseMessageHasModelName(responseMessageId, expectedModelName);
					await chatPage.assertResponseMessageHasModelImage(
						responseMessageId,
						expectedModelImageUrl
					);
				});

				await test.step('Verify model disable state in commands container (@model)', async () => {
					const chatPage = new ChatPage(page);
					// the commands container doesn't support spaces in the model name
					await chatPage.typeMessage('@' + modelName.replaceAll(' ', ''));
					// reusing the assertModelHideState method here because it's the same logic
					await chatPage.assertModelHideState(modelId, expectedDisableState);
					// Clear the input for the next step
					await chatPage.typeMessage('');
				});

				await test.step('Verify model name and image in Chat Info modal', async () => {
					const chatPage = new ChatPage(page);
					const chatInfoModal = new ChatInfoModal(page);
					await chatPage.clickChatInfoButton();

					// disabled models show the model ID and default image instead of the set image and name
					const expectedModelName = expectedDisableState ? modelId : modelName;

					await chatInfoModal.assertUniqueModelLabel(modelId, expectedModelName);
					if (expectedDisableState) {
						await chatInfoModal.assertUniqueModelImagePlaceholder(modelId);
					} else {
						await chatInfoModal.assertUniqueModelImage(modelId, expectedImageUrl);
					}
					await chatInfoModal.close();
				});

				await test.step('Verify model disable state in Command Palette', async () => {
					const chatPage = new ChatPage(page);
					await chatPage.commandPalette.open();
					await chatPage.commandPalette.typeCommand(CHANGE_MODEL_COMMAND.label);
					await chatPage.commandPalette.clickCommand(CHANGE_MODEL_COMMAND.id);
					await chatPage.commandPalette.submitCommand();
					await chatPage.commandPalette.typeCommand(modelName);

					// reusing the assertModelHideState method here because it's the same logic
					await chatPage.commandPalette.assertModelHideState(modelId, expectedDisableState);

					await chatPage.commandPalette.close();
				});
			};

			// Disable model
			await test.step('Disable model', async () => {
				const currentUrl = page.url();
				if (!currentUrl.includes('/admin')) {
					const homePage = new HomePage(page);
					await homePage.clickUserMenuButton();
					await homePage.userMenu.clickAdminPanel();
				}
				const adminSettings = new AdminSettingsGeneralTab(page);
				await adminSettings.clickModelsTabButton();
				const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
				await adminSettingsModelsTab.searchForModel(modelName);
				await adminSettingsModelsTab.setModelItemDisabledState(modelId, true);
			});

			// Assert model disable state appears correctly with disabled state
			await assertModelDisableStateInAllLocations(true);

			// Enable model
			await test.step('Enable model', async () => {
				const currentUrl = page.url();
				if (!currentUrl.includes('/admin')) {
					const homePage = new HomePage(page);
					await homePage.clickUserMenuButton();
					await homePage.userMenu.clickAdminPanel();
				}
				const adminSettings = new AdminSettingsGeneralTab(page);
				await adminSettings.clickModelsTabButton();
				const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
				await adminSettingsModelsTab.searchForModel(modelName);
				await adminSettingsModelsTab.setModelItemDisabledState(modelId, false);
			});

			// Assert model hide state appears correctly with unhidden state
			await assertModelDisableStateInAllLocations(false);
		});

		// TODO tags change and assertions.

		// TODO visibility settings change and assertions (would require multiple accounts and groups i think... this might also need to be a separate test, probably covering a lot of the other visibility settings, which would be a lot of work and i won't bother dealing with for a long time to come...)

		// TODO ((so refactor all the 'visibility settings' stuff in README.md to be in one big test rather than individual ones.))
	});
});

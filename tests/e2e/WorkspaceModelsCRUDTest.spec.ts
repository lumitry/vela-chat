import { test } from '../fixtures/testUser';
import { HomePage } from '../pages/HomePage';
import { AdminSettingsGeneralTab } from '../pages/Admin/AdminSettingsGeneralTab';
import {
	MINI_MEDIATOR_MIRROR_OLLAMA,
	MINI_MEDIATOR_MIRROR_OPENAI,
	MINI_MEDIATOR_MODELS_CRUD_DESCRIPTION_OLLAMA,
	MINI_MEDIATOR_MODELS_CRUD_DESCRIPTION_OPENAI,
	MINI_MEDIATOR_MODELS_CRUD_IMAGE_OLLAMA,
	MINI_MEDIATOR_MODELS_CRUD_IMAGE_OPENAI,
	MINI_MEDIATOR_MODELS_CRUD_RENAME_OLLAMA,
	MINI_MEDIATOR_MODELS_CRUD_RENAME_OPENAI,
	MINI_MEDIATOR_MODELS_CRUD_TAGS_OLLAMA,
	MINI_MEDIATOR_MODELS_CRUD_TAGS_OPENAI
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
import { WorkspaceModelsPage } from '../pages/workspace/WorkspaceModelsPage';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

['openai', 'ollama'].forEach((provider) => {
	test.describe(`Workspace Models CRUD Test - ${provider}`, () => {
		test('Create a new workspace model', async ({ page }) => {
			const model =
				provider === 'openai'
					? MINI_MEDIATOR_MODELS_CRUD_RENAME_OPENAI
					: MINI_MEDIATOR_MODELS_CRUD_RENAME_OLLAMA;
			const baseModelId = model.getFullIdWithEndpointPrefix();
			const modelName = `Workspace CRUD Test ${generateRandomString(5)}`;
			const newModelName = `Workspace CRUD Test Updated ${generateRandomString(5)}`;
			const modelId = modelName.replaceAll(' ', '-').toLowerCase();

			// Navigate to model editor
			await test.step('Navigate to model editor', async () => {
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickCreateModelButton();
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setBaseModel(baseModelId);
				await modelEditor.setId(modelId);
				await modelEditor.setName(modelName);
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Helper function to assert model name appears correctly in all locations
			const assertModelNameInAllLocations = async (
				expectedModelName: string,
				expectedModelId: string
			) => {
				await test.step('Verify model name in Workspace Models page', async () => {
					const workspaceModelsPage = new WorkspaceModelsPage(page);
					await workspaceModelsPage.assertModelExists(expectedModelId, expectedModelName, null);
				});

				await test.step('Verify model name in Admin Settings Interface tab', async () => {
					const workspaceModelsPage = new WorkspaceModelsPage(page);
					await workspaceModelsPage.clickNewChatButton();
					const chatPage = new HomePage(page);
					await chatPage.clickUserMenuButton();
					await chatPage.userMenu.clickAdminPanel();
					const adminSettings = new AdminSettingsGeneralTab(page);
					await adminSettings.clickInterfaceTabButton();
					const adminSettingsInterfaceTab = new AdminSettingsInterfaceTab(page);
					await adminSettingsInterfaceTab.assertModelOptionExists(
						provider as 'ollama' | 'openai',
						expectedModelName,
						expectedModelId
					);
				});

				await test.step('Verify model name in Admin Evaluations page (leaderboard)', async () => {
					const adminSettingsInterfaceTab = new AdminSettingsInterfaceTab(page);
					await adminSettingsInterfaceTab.clickEvaluationsPageButton();
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
			await assertModelNameInAllLocations(modelName, modelId);

			// Update model name
			await test.step('Update model name', async () => {
				// Navigate to workspace models page
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemEditButton(modelId);
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setName(newModelName);
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Assert model name appears correctly with new name (verifies stores are intact)
			await assertModelNameInAllLocations(newModelName, modelId);
		});

		test('Change model description', async ({ page }) => {
			const model =
				provider === 'openai'
					? MINI_MEDIATOR_MODELS_CRUD_DESCRIPTION_OPENAI
					: MINI_MEDIATOR_MODELS_CRUD_DESCRIPTION_OLLAMA;
			const baseModelId = model.getFullIdWithEndpointPrefix();
			const modelName = `Description Test Model ${generateRandomString(5)}`;
			const modelId = modelName.replaceAll(' ', '-').toLowerCase();
			const originalModelDescription = null; // models have no description by default

			// Create workspace model
			await test.step('Create workspace model', async () => {
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickCreateModelButton();
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setBaseModel(baseModelId);
				await modelEditor.setId(modelId);
				await modelEditor.setName(modelName);
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Change model description
			const newModelDescription = `Test Model Description ${generateRandomString(5)}`;
			await test.step('Change model description', async () => {
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemEditButton(modelId);
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
				await test.step('Verify model description in Workspace Models page', async () => {
					const homePage = new HomePage(page);
					await homePage.openSidebarIfClosed();
					await homePage.clickWorkspaceButton();
					const workspaceModelsPage = new WorkspaceModelsPage(page);
					await workspaceModelsPage.assertModelExists(modelId, modelName, expectedModelDescription);
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
				// Navigate back to workspace models page from wherever we are
				const currentUrl = page.url();
				if (!currentUrl.includes('/workspace/models')) {
					const homePage = new HomePage(page);
					await homePage.openSidebarIfClosed();
					await homePage.clickWorkspaceButton();
				}
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemEditButton(modelId);
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setDescription(originalModelDescription ?? '');
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Assert model description appears correctly with original description (verifies stores are intact)
			await assertModelDescriptionInAllLocations(originalModelDescription, modelId);

			// Clean up: delete the workspace model
			await test.step('Clean up workspace model', async () => {
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemMenuButton(modelId);
				await workspaceModelsPage.clickDeleteMenuItem(modelId);
				await workspaceModelsPage.confirmDelete();
			});
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
			const baseModelId = model.getFullIdWithEndpointPrefix();
			const modelName = `Image Test Model ${generateRandomString(5)}`;
			const modelId = modelName.replaceAll(' ', '-').toLowerCase();
			const originalModelImage = `${FRONTEND_BASE_URL}${DEFAULT_MODEL_IMAGE}`;
			const newModelImageBuffer = readFileSync(join(__dirname, '../data/newModelImage.png'));
			const secondNewModelImageBuffer = readFileSync(
				join(__dirname, '../data/secondNewModelImage.png')
			);

			// Helper function to assert model image appears correctly in all locations
			const assertModelImageInAllLocations = async (expectedImageUrl: string, modelId: string) => {
				await test.step('Verify model image in Workspace Models page', async () => {
					const homePage = new HomePage(page);
					await homePage.openSidebarIfClosed();
					await homePage.clickWorkspaceButton();
					const workspaceModelsPage = new WorkspaceModelsPage(page);
					await workspaceModelsPage.assertModelItemWithImageExists(modelId, expectedImageUrl);
				});

				await test.step('Verify model image in Admin Evaluations page (leaderboard)', async () => {
					const workspaceModelsPage = new WorkspaceModelsPage(page);
					await workspaceModelsPage.clickNewChatButton();
					const homePage = new HomePage(page);
					await homePage.clickUserMenuButton();
					await homePage.userMenu.clickAdminPanel();
					const adminSettings = new AdminSettingsGeneralTab(page);
					await adminSettings.clickEvaluationsPageButton();
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
			};

			// Create workspace model
			await test.step('Create workspace model', async () => {
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickCreateModelButton();
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setBaseModel(baseModelId);
				await modelEditor.setId(modelId);
				await modelEditor.setName(modelName);
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// First image upload
			await test.step('Upload first model image', async () => {
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemEditButton(modelId);
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
					const homePage = new HomePage(page);
					await homePage.openSidebarIfClosed();
					await homePage.clickWorkspaceButton();
					const workspaceModelsPage = new WorkspaceModelsPage(page);
					// Wait for the image URL to be a file URL (not data: or favicon)
					const imageUrl = await workspaceModelsPage.waitForModelImageToBeSaved(modelId);

					// Verify once that the saved image matches the resized original
					const resizedExpectedBuffer = await resizeImageTo250x250(page, newModelImageBuffer);
					await workspaceModelsPage.assertModelItemImageContentMatches(
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
				if (!currentUrl.includes('/workspace/models')) {
					const homePage = new HomePage(page);
					await homePage.openSidebarIfClosed();
					await homePage.clickWorkspaceButton();
				}
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemEditButton(modelId);
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
					const homePage = new HomePage(page);
					await homePage.openSidebarIfClosed();
					await homePage.clickWorkspaceButton();
					const workspaceModelsPage = new WorkspaceModelsPage(page);
					// Wait for the image URL to be a file URL (not data: or favicon or first image URL)
					const imageUrl = await workspaceModelsPage.waitForModelImageToBeSaved(
						modelId,
						firstImageUrl
					);

					// Verify once that the saved image matches the resized original
					const resizedExpectedBuffer = await resizeImageTo250x250(page, secondNewModelImageBuffer);
					await workspaceModelsPage.assertModelItemImageContentMatches(
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
				if (!currentUrl.includes('/workspace/models')) {
					const homePage = new HomePage(page);
					await homePage.openSidebarIfClosed();
					await homePage.clickWorkspaceButton();
				}
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemEditButton(modelId);
				const modelEditor = new ModelEditorPage(page);
				// Reset image to default by clicking the reset button
				await modelEditor.clickResetImageButton();
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Assert model image appears correctly with original image (verifies stores are intact)
			await assertModelImageInAllLocations(originalModelImage, modelId);

			// Clean up: delete the workspace model
			await test.step('Clean up workspace model', async () => {
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemMenuButton(modelId);
				await workspaceModelsPage.clickDeleteMenuItem(modelId);
				await workspaceModelsPage.confirmDelete();
			});
		});

		test('Disable model', async ({ page }) => {
			// not using the disable test models because the admin models CRUD test might have disabled them already!
			const model =
				provider === 'openai' ? MINI_MEDIATOR_MIRROR_OPENAI : MINI_MEDIATOR_MIRROR_OLLAMA;
			const baseModelId = model.getFullIdWithEndpointPrefix();
			const modelName = `Disable Test Model ${generateRandomString(5)}`;
			const modelId = modelName.replaceAll(' ', '-').toLowerCase();
			// We will change the image for this model too.
			// This unfortunately couples it to the change model image test a little, but it's important to differentiate between this test and the disable model test!
			const newModelImageBuffer = readFileSync(join(__dirname, '../data/newModelImage.png'));
			// same thing for description!
			const modelDescription = `Disable Test Model Description ${generateRandomString(5)}`;

			await test.step('Set up model for disable test', async () => {
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickCreateModelButton();
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setBaseModel(baseModelId);
				await modelEditor.setId(modelId);
				await modelEditor.setName(modelName);
				await modelEditor.setModelImage({
					name: 'newModelImage.png',
					mimeType: 'image/png',
					buffer: newModelImageBuffer
				});
				await modelEditor.setDescription(modelDescription);
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Wait for image to be saved, verify content once, then use URL for all assertions
			const expectedImageUrl =
				await test.step('Wait for first image to be saved and verify content', async () => {
					const homePage = new HomePage(page);
					await homePage.openSidebarIfClosed();
					await homePage.clickWorkspaceButton();
					const workspaceModelsPage = new WorkspaceModelsPage(page);
					// Wait for the image URL to be a file URL (not data: or favicon)
					const imageUrl = await workspaceModelsPage.waitForModelImageToBeSaved(modelId);

					// Verify once that the saved image matches the resized original
					const resizedExpectedBuffer = await resizeImageTo250x250(page, newModelImageBuffer);
					await workspaceModelsPage.assertModelItemImageContentMatches(
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

			// Helper function to assert model disable state appears correctly in all locations
			const assertModelDisableStateInAllLocations = async (expectedDisableState: boolean) => {
				await test.step('Verify model disable state in Workspace Models page', async () => {
					const homePage = new HomePage(page);
					await homePage.openSidebarIfClosed();
					await homePage.clickWorkspaceButton();
					const workspaceModelsPage = new WorkspaceModelsPage(page);
					await workspaceModelsPage.assertModelItemDisabledState(modelId, expectedDisableState);

					// TODO this is messy, but it stabilizes the test for now.
					await page.waitForTimeout(1000);
				});

				await test.step('Verify model appears in Admin Settings Interface tab', async () => {
					const workspaceModelsPage = new WorkspaceModelsPage(page);
					await workspaceModelsPage.clickNewChatButton();
					const homePage = new HomePage(page);
					await homePage.clickUserMenuButton();
					await homePage.userMenu.clickAdminPanel();
					const adminSettings = new AdminSettingsGeneralTab(page);
					await adminSettings.clickInterfaceTabButton();
					const adminSettingsInterfaceTab = new AdminSettingsInterfaceTab(page);
					await adminSettingsInterfaceTab.assertPresenceOfModelOption(
						provider as 'ollama' | 'openai',
						modelName,
						modelId,
						!expectedDisableState // expectedPresence = !expectedDisableState
					);
				});

				await test.step('Verify model disable state in Admin Evaluations page (leaderboard)', async () => {
					const adminSettingsInterfaceTab = new AdminSettingsInterfaceTab(page);
					await adminSettingsInterfaceTab.clickEvaluationsPageButton();
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
				if (!currentUrl.includes('/workspace/models')) {
					const homePage = new HomePage(page);
					await homePage.openSidebarIfClosed();
					await homePage.clickWorkspaceButton();
				}
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.setModelItemDisabledState(modelId, true);
			});

			// Assert model disable state appears correctly with disabled state
			await assertModelDisableStateInAllLocations(true);

			// Enable model
			await test.step('Enable model', async () => {
				const currentUrl = page.url();
				if (!currentUrl.includes('/workspace/models')) {
					const homePage = new HomePage(page);
					await homePage.openSidebarIfClosed();
					await homePage.clickWorkspaceButton();
				}
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.setModelItemDisabledState(modelId, false);
			});

			// Assert model disable state appears correctly with enabled state
			await assertModelDisableStateInAllLocations(false);

			// Clean up: delete the workspace model
			await test.step('Clean up workspace model', async () => {
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemMenuButton(modelId);
				await workspaceModelsPage.clickDeleteMenuItem(modelId);
				await workspaceModelsPage.confirmDelete();
			});
		});

		test('Change model tags', async ({ page }) => {
			const model =
				provider === 'openai'
					? MINI_MEDIATOR_MODELS_CRUD_TAGS_OPENAI
					: MINI_MEDIATOR_MODELS_CRUD_TAGS_OLLAMA;
			const baseModelId = model.getFullIdWithEndpointPrefix();
			const modelName = `Change Tags Test Model ${generateRandomString(5)}`;
			const modelId = modelName.replaceAll(' ', '-').toLowerCase();
			const newTags = ['new tag 1', 'new tag 2', generateRandomString(5)];

			const assertModelTagsInAllLocations = async (expectedTags: string[]) => {
				await test.step('Verify model tags on home page', async () => {
					const workspaceModelsPage = new WorkspaceModelsPage(page);
					// we have to click this twice for some reason...
					await workspaceModelsPage.clickNewChatButton();
					await workspaceModelsPage.clickNewChatButton();
					const homePage = new HomePage(page);
					await homePage.assertResponseNotInProgress(); // wait for page to load before asserting tags
					await homePage.modelSelector.open();
					await homePage.modelSelector.assertModelTags(modelId, expectedTags);
					await homePage.modelSelector.selectModel(modelId);
					await homePage.assertPlaceholderTags(expectedTags);
				});

				await test.step('Verify model selector tag filtering works', async () => {
					const homePage = new HomePage(page);
					await homePage.modelSelector.open();
					await homePage.modelSelector.filterByTag(expectedTags[0] ?? '');
					await homePage.modelSelector.assertModelNameExists(modelId, modelName);
				});
			};

			await test.step('Set up model for change tags test', async () => {
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickCreateModelButton();
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setBaseModel(baseModelId);
				await modelEditor.setId(modelId);
				await modelEditor.setName(modelName);
				await modelEditor.setTags(newTags);
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Assert model tags appear correctly
			await assertModelTagsInAllLocations(newTags);

			// Remove tags
			await test.step('Remove tags', async () => {
				const currentUrl = page.url();
				if (!currentUrl.includes('/workspace/models')) {
					const homePage = new HomePage(page);
					await homePage.openSidebarIfClosed();
					await homePage.clickWorkspaceButton();
				}
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemEditButton(modelId);
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setTags([]);
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Assert model tags appear correctly
			await assertModelTagsInAllLocations([]);

			// Clean up: delete the workspace model
			await test.step('Clean up workspace model', async () => {
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemMenuButton(modelId);
				await workspaceModelsPage.clickDeleteMenuItem(modelId);
				await workspaceModelsPage.confirmDelete();
			});
		});

		test('Clone model', async ({ page }) => {
			const model =
				provider === 'openai'
					? MINI_MEDIATOR_MODELS_CRUD_RENAME_OPENAI
					: MINI_MEDIATOR_MODELS_CRUD_RENAME_OLLAMA;
			const baseModelId = model.getFullIdWithEndpointPrefix();
			const modelName = `Clone Test Model ${generateRandomString(5)}`;
			const modelId = modelName.replaceAll(' ', '-').toLowerCase();
			const clonedModelId = `${modelId}-clone`;
			const clonedModelName = `${modelName} (Clone)`;

			// Create original model
			await test.step('Create original model', async () => {
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickCreateModelButton();
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setBaseModel(baseModelId);
				await modelEditor.setId(modelId);
				await modelEditor.setName(modelName);
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});
			// TODO add tags, description, image, etc. and verify they are cloned correctly

			// Clone the model
			await test.step('Clone the model', async () => {
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemMenuButton(modelId);
				await workspaceModelsPage.clickCloneMenuItem(modelId);
				// Should navigate to model editor with cloned model data
				const modelEditor = new ModelEditorPage(page);
				// Verify we're on the create page with cloned data
				await modelEditor.assertModelId(clonedModelId);
				await modelEditor.assertModelName(clonedModelName);
				// Save the cloned model
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Verify cloned model exists
			await test.step('Verify cloned model exists', async () => {
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.assertModelExists(clonedModelId, clonedModelName, null);
			});

			// Clean up: delete both models
			await test.step('Clean up cloned model', async () => {
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemMenuButton(clonedModelId);
				await workspaceModelsPage.clickDeleteMenuItem(clonedModelId);
				await workspaceModelsPage.confirmDelete();
			});

			await test.step('Clean up original model', async () => {
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemMenuButton(modelId);
				await workspaceModelsPage.clickDeleteMenuItem(modelId);
				await workspaceModelsPage.confirmDelete();
			});
		});

		test('Delete model', async ({ page }) => {
			const model =
				provider === 'openai'
					? MINI_MEDIATOR_MODELS_CRUD_RENAME_OPENAI
					: MINI_MEDIATOR_MODELS_CRUD_RENAME_OLLAMA;
			const baseModelId = model.getFullIdWithEndpointPrefix();
			const modelName = `Delete Test Model ${generateRandomString(5)}`;
			const modelId = modelName.replaceAll(' ', '-').toLowerCase();

			// Create model to delete
			await test.step('Create model to delete', async () => {
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickCreateModelButton();
				const modelEditor = new ModelEditorPage(page);
				await modelEditor.setBaseModel(baseModelId);
				await modelEditor.setId(modelId);
				await modelEditor.setName(modelName);
				await modelEditor.saveAndReturn();
				await modelEditor.toast.assertToastIsVisible('success');
			});

			// Verify model exists before deletion
			await test.step('Verify model exists before deletion', async () => {
				const homePage = new HomePage(page);
				await homePage.openSidebarIfClosed();
				await homePage.clickWorkspaceButton();
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.assertModelExists(modelId, modelName, null);
			});

			// Delete the model
			await test.step('Delete the model', async () => {
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.clickModelItemMenuButton(modelId);
				await workspaceModelsPage.clickDeleteMenuItem(modelId);
				await workspaceModelsPage.confirmDelete();
				await workspaceModelsPage.toast.assertToastIsVisible('success');
			});

			// Verify model no longer exists
			await test.step('Verify model no longer exists', async () => {
				const workspaceModelsPage = new WorkspaceModelsPage(page);
				await workspaceModelsPage.assertModelDoesNotExist(modelId);
			});
		});
	});
});

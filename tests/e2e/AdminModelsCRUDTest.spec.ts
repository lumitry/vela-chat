import { test } from '../fixtures/testUser';
import { HomePage } from '../pages/HomePage';
import { AdminSettingsGeneralTab } from '../pages/Admin/AdminSettingsGeneralTab';
import { AdminSettingsModelsTab } from '../pages/Admin/AdminSettingsModelsTab';
import {
	MINI_MEDIATOR_ANONYMOUS_OLLAMA,
	MINI_MEDIATOR_ANONYMOUS_OPENAI
} from '../data/miniMediatorModels';
import { ModelEditorPage } from '../pages/Admin/ModelEditorPage';
import { AdminSettingsInterfaceTab } from '../pages/Admin/AdminSettingsInterface';
import { AdminEvaluationsPage } from '../pages/Admin/AdminEvaluationsPage';
import { ChatPage } from '../pages/ChatPage';
import { ChatInfoModal } from '../pages/modals/ChatInfoModal';
import { generateRandomString } from '../data/random';

['openai', 'ollama'].forEach((provider) => {
	test.describe(`Admin Models CRUD Test - ${provider}`, () => {
		test('Change model name', async ({ page }) => {
			const model =
				provider === 'openai' ? MINI_MEDIATOR_ANONYMOUS_OPENAI : MINI_MEDIATOR_ANONYMOUS_OLLAMA;

			const homePage = new HomePage(page);
			await homePage.clickUserMenuButton();
			await homePage.userMenu.clickAdminPanel();
			const adminSettings = new AdminSettingsGeneralTab(page);
			await adminSettings.clickModelsTabButton();
			const adminSettingsModelsTab = new AdminSettingsModelsTab(page);
			await adminSettingsModelsTab.clickModelItemEditButton(model.getFullIdWithEndpointPrefix());
			const modelEditor = new ModelEditorPage(page);
			// this has to be unique to prevent collisions with other parallel tests
			const newModelName = `Test Model ${generateRandomString(5)}`;
			await modelEditor.setName(newModelName);
			await modelEditor.saveAndReturn();
			await modelEditor.toast.assertToastIsVisible('success');

			// verify model name changed in models tab
			await adminSettingsModelsTab.searchForModel(newModelName);
			await adminSettingsModelsTab.assertModelCount(1);
			await adminSettingsModelsTab.assertModelItemWithNameExists(
				model.getFullIdWithEndpointPrefix(),
				newModelName
			);

			// interface tab
			await adminSettingsModelsTab.clickInterfaceTabButton();
			const adminSettingsInterfaceTab = new AdminSettingsInterfaceTab(page);
			await adminSettingsInterfaceTab.assertModelOptionExists(
				provider as 'ollama' | 'openai',
				newModelName
			);

			// feedbacks page
			await adminSettingsModelsTab.clickEvaluationsPageButton();
			const adminEvaluationsPage = new AdminEvaluationsPage(page);
			await adminEvaluationsPage.assertLeaderboardModelNameExists(
				model.getFullIdWithEndpointPrefix(),
				newModelName
			);

			// home page (new chat page)
			await adminSettingsInterfaceTab.clickNewChatButton();
			await homePage.openModelSelector();
			await homePage.assertModelSelectorModelNameExists(
				model.getFullIdWithEndpointPrefix(),
				newModelName
			);
			await homePage.selectModel(model.getFullIdWithEndpointPrefix());
			await homePage.assertCurrentChatModelName(newModelName);
			await homePage.assertPlaceholderCurrentModelName(newModelName);
			const { responseMessageIds } =
				await homePage.submitMessageAndCaptureIds('Hello, how are you?');
			const responseMessageId = responseMessageIds[0];
			const chatPage = new ChatPage(page);
			await chatPage.assertResponseMessageHasModelName(responseMessageId, newModelName);
			// we are not verifying the content of the response message - just the model name!

			// Chat info modal
			const chatInfoModal = new ChatInfoModal(page);
			await chatPage.clickChatInfoButton();
			await chatInfoModal.assertUniqueModelLabelExists(newModelName);
			await chatInfoModal.close();

			// command palette

			// TODO command palette should show the right model name for model switcher
			// TODO typing "@anon" into the message input should show the model in the temp model changer results list!
			// TODO anywhere else?

			// TODO then revert the name change and do all the same assertions again to verify the name change was reverted everywhere (this should be done without reloading the page to make sure stores are intact for the most valid testing possible)

			// TODO USE TEST.STEP FOR THE ABOVE STEPS!
		});

		// TODO description change and assertions (i.e. in new chat page)

		// TODO image change and assertions

		// TODO is there a way to abstract all these assertions into a single function? it'd be a different method on each page, but we'd be calling some very SIMILAR methods on IDENTICAL sets of pages, more or less... hmm.
	});
});

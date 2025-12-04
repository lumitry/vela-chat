import {
	MINI_MEDIATOR_DETERMINISTIC_OPENAI,
	MINI_MEDIATOR_DETERMINISTIC_OLLAMA,
	MINI_MEDIATOR_MIRROR_OPENAI,
	MINI_MEDIATOR_MIRROR_OLLAMA
} from '../data/miniMediatorModels';
import {
	MINI_MEDIATOR_SCENARIO_BASIC_CHAT,
	MINI_MEDIATOR_SCENARIO_BASIC_CHAT_FOLLOW_UP,
	MINI_MEDIATOR_SCENARIO_SLOW_STREAM_PAUSE,
	type MiniMediatorScenario
} from '../data/miniMediatorScenarios';
import { expect, test } from '../fixtures/testUser';
import { ChatPage } from '../pages/ChatPage';
import { HomePage } from '../pages/HomePage';
import type { BaseChatPage, SentMessage } from '../pages/BaseChatPage';
import { getFirstUserMessageContentFromMirrorResponse } from '../utils/miniMediatorMirrorParser';

['openai', 'ollama'].forEach((provider) => {
	test.describe(`Basic Chat Test - ${provider}`, () => {
		test.beforeEach(async ({ page }) => {
			await page.goto('/', { waitUntil: 'load' });
		});

		test('Create simple chat with two message pairs', async ({ page }) => {
			const model =
				provider === 'openai'
					? MINI_MEDIATOR_DETERMINISTIC_OPENAI
					: MINI_MEDIATOR_DETERMINISTIC_OLLAMA;
			// const modelId = model.getFullIdWithEndpointPrefix();

			const homePage = new HomePage(page);
			// await homePage.clickNewChatButton();
			await homePage.modelSelector.open();
			await homePage.modelSelector.selectModel(model);

			let chatPage: ChatPage;
			const messages: SentMessage[] = [];

			// helper to send a message and assert the response, given a scenario and starting page (either home page or an existing chat page)
			// MUTATES/assigns chatPage!
			const sendAndAssertMessage = async (
				scenario: MiniMediatorScenario,
				startPage: BaseChatPage
			) => {
				const inputMessage = scenario.getInput();
				const expectedResponse = scenario.getOutput();

				messages.push(await startPage.submitMessageAndCaptureIds(inputMessage));
				const responseMessageId = messages[messages.length - 1].responseMessageIds[0];

				chatPage = new ChatPage(page);
				await chatPage.assertAssistantMessageExists(responseMessageId);
				await chatPage.assertAssistantMessageText(responseMessageId, expectedResponse);
			};

			await test.step('Send first message', async () => {
				const scenario = MINI_MEDIATOR_SCENARIO_BASIC_CHAT;
				await sendAndAssertMessage(scenario, homePage);
			});

			await test.step('Send follow-up message', async () => {
				const scenario = MINI_MEDIATOR_SCENARIO_BASIC_CHAT_FOLLOW_UP;
				await sendAndAssertMessage(scenario, chatPage);
			});
		});

		test('Messages persist after page reloads', async ({ page }) => {
			const model =
				provider === 'openai'
					? MINI_MEDIATOR_DETERMINISTIC_OPENAI
					: MINI_MEDIATOR_DETERMINISTIC_OLLAMA;

			const homePage = new HomePage(page);
			await homePage.modelSelector.open();
			await homePage.modelSelector.selectModel(model);

			let chatPage: ChatPage;
			const sentMessages: { message: SentMessage; scenario: MiniMediatorScenario }[] = [];

			const sendAndAssertMessage = async (
				scenario: MiniMediatorScenario,
				startPage: BaseChatPage
			) => {
				const inputMessage = scenario.getInput();
				const expectedResponse = scenario.getOutput();

				const sent = await startPage.submitMessageAndCaptureIds(inputMessage);
				sentMessages.push({ message: sent, scenario });

				const responseMessageId = sent.responseMessageIds[0];

				chatPage = new ChatPage(page);
				await chatPage.assertUserMessageExists(sent.userMessageId);
				await chatPage.assertUserMessageText(sent.userMessageId, inputMessage);
				await chatPage.assertAssistantMessageExists(responseMessageId);
				await chatPage.assertAssistantMessageText(responseMessageId, expectedResponse);
			};

			const assertMessagesPersist = async () => {
				// After a reload we need a fresh page object instance
				chatPage = new ChatPage(page);

				for (const { message, scenario } of sentMessages) {
					const { userMessageId, responseMessageIds } = message;
					const inputMessage = scenario.getInput();
					const expectedResponse = scenario.getOutput();

					await chatPage.assertUserMessageExists(userMessageId);
					await chatPage.assertUserMessageText(userMessageId, inputMessage);

					for (const responseMessageId of responseMessageIds) {
						await chatPage.assertAssistantMessageExists(responseMessageId);
						await chatPage.assertAssistantMessageText(responseMessageId, expectedResponse);
					}
				}
			};

			await test.step('Send first and follow-up messages', async () => {
				await sendAndAssertMessage(MINI_MEDIATOR_SCENARIO_BASIC_CHAT, homePage);
				await sendAndAssertMessage(MINI_MEDIATOR_SCENARIO_BASIC_CHAT_FOLLOW_UP, chatPage);
			});

			await test.step('Reload once (batch API) and verify messages', async () => {
				await page.reload({ waitUntil: 'load' });
				await assertMessagesPersist();
			});

			await test.step('Reload twice (IndexedDB cache) and verify messages', async () => {
				await page.reload({ waitUntil: 'load' });
				await assertMessagesPersist();
			});
		});

		test('Verify response is stopped when the stop response button is clicked', async ({
			page
		}) => {
			const model =
				provider === 'openai'
					? MINI_MEDIATOR_DETERMINISTIC_OPENAI
					: MINI_MEDIATOR_DETERMINISTIC_OLLAMA;

			const homePage = new HomePage(page);
			await homePage.modelSelector.open();
			await homePage.modelSelector.selectModel(model);

			const scenario = MINI_MEDIATOR_SCENARIO_SLOW_STREAM_PAUSE;
			const inputMessage = scenario.getInput();
			const fullResponse = scenario.getOutput();
			// this scenario pauses the stream after chunk #2, so we expect to have already received the first 2 chunks before stopping the response
			const expectedResponsePart =
				scenario.getScenarioResponseChunk(0) + scenario.getScenarioResponseChunk(1);

			let responseMessageId: string;

			await test.step('Send message and stop response', async () => {
				const { responseMessageIds } = await homePage.submitMessageAndCaptureIds(inputMessage);
				responseMessageId = responseMessageIds[0];

				const chatPage = new ChatPage(page);
				await chatPage.assertResponseInProgress();
				// Wait to make sure we get the first 2 chunks (before the pause).
				// Uses the scenario's streaming config to derive a reasonable warmup timeout.
				const warmupMs = scenario.getRecommendedWarmupMs(2);
				await page.waitForTimeout(warmupMs);
				await chatPage.clickStopResponseButton();
				await chatPage.assertResponseNotInProgress();

				// Use the pause profile from the fixture to determine how long we should wait to ensure that no additional chunks arrive after we stop the response.
				const maxPauseSeconds = scenario.getMaxPauseSeconds();
				// Add a small safety margin (0.5s) on top of the longest configured pause.
				const safetyMarginMs = 500;
				await page.waitForTimeout(maxPauseSeconds * 1000 + safetyMarginMs);

				// assert that the response is still not in progress, and that the response is only the expected chunks and not the full response
				await chatPage.assertResponseNotInProgress();
				await chatPage.assertAssistantMessageText(responseMessageId, expectedResponsePart);
				await chatPage.assertAssistantMessageNotContainsText(responseMessageId, fullResponse);
			});

			await test.step('Verify response is not in progress after page reload', async () => {
				await page.reload({ waitUntil: 'load' });
				const chatPage = new ChatPage(page);
				await chatPage.assertResponseNotInProgress();
			});

			await test.step('Verify response is not complete after page reload', async () => {
				const chatPage = new ChatPage(page);
				await chatPage.assertResponseNotInProgress();
				await chatPage.assertAssistantMessageText(responseMessageId, expectedResponsePart);
				await chatPage.assertAssistantMessageNotContainsText(responseMessageId, fullResponse);
			});
		});

		test('Verify whitespace-only messages cannot be submitted', async ({ page }) => {
			const model =
				provider === 'openai'
					? MINI_MEDIATOR_DETERMINISTIC_OPENAI
					: MINI_MEDIATOR_DETERMINISTIC_OLLAMA;

			const homePage = new HomePage(page);
			await homePage.modelSelector.open();
			await homePage.modelSelector.selectModel(model);

			const inputMessage = '   ';

			await homePage.typeMessage(inputMessage);
			await homePage.assertCannotSubmitMessage();
		});

		test('Verify whitespace is trimmed before submission', async ({ page }) => {
			const model =
				provider === 'openai' ? MINI_MEDIATOR_MIRROR_OPENAI : MINI_MEDIATOR_MIRROR_OLLAMA;

			const homePage = new HomePage(page);
			await homePage.modelSelector.open();
			await homePage.modelSelector.selectModel(model);

			const inputMessage = '   Hello, world!   ';

			const { responseMessageIds } = await homePage.submitMessageAndCaptureIds(inputMessage);
			const responseMessageId = responseMessageIds[0];

			const chatPage = new ChatPage(page);
			await chatPage.assertAssistantMessageExists(responseMessageId);
			// this just does a basic contains() check, so it should come back truthy
			await chatPage.assertAssistantMessageText(responseMessageId, 'Hello, world!');

			// but we can get fancier than that by asserting what the mirror actually saw...
			const mirrorText = await chatPage.getAssistantMessageText(responseMessageId);
			// TODO - why does the frontend not trim the whitespace at the beginning and end of the message?
			// TODO it visually trims both ends on the user message display bubble, but even follow-up messages after a refresh show that the whitespace is still there.
			// not necessarily a bug, but it's weird behavior we should be cognizant of.
			expect(getFirstUserMessageContentFromMirrorResponse(mirrorText)).toBe('   Hello, world!');
		});
	});
});

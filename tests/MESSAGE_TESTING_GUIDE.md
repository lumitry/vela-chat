# Message Testing Guide

This guide explains how to test chat messages in E2E tests using the message ID capture system.

it was written by Cursor, hopefully someone finds it useful.

## Overview

When testing chat messages, you need to identify specific messages in the DOM. Messages have dynamic UUIDs that are generated when they're sent, so you can't predict them ahead of time. The solution is to:

1. **Capture message IDs from the API request** - Intercept the POST request to `/api/chat/completions` to get both the user message ID and response message ID before the response completes.
2. **Use data-testid attributes** - Messages have `data-testid` attributes that include their IDs, making them easy to locate.

## Basic Usage

### Sending a Message and Capturing IDs

Use `submitMessageAndCaptureIds()` to send a message and get the message IDs:

```typescript
import { test, expect } from '@playwright/test';
import { ChatPage } from './pages/ChatPage';
import type { SentMessage } from './pages/BaseChatPage';

test('send message and verify it appears', async ({ page }) => {
	const chatPage = new ChatPage(page);
	await chatPage.goto();

	// Send a message and capture the IDs
	const { userMessageId, responseMessageIds } =
		await chatPage.submitMessageAndCaptureIds('Hello, how are you?');

	// Now you can use these IDs to locate and assert on messages
	await chatPage.assertUserMessageExists(userMessageId);
	await chatPage.assertUserMessageText(userMessageId, 'Hello, how are you?');

	// For single-response scenarios, responseMessageIds[0] is the response
	// Wait for response to complete, then assert
	await chatPage.assertAssistantMessageExists(responseMessageIds[0]);
});
```

### Getting Message Locators

You can get locators for specific messages using the helper methods:

```typescript
// Get a locator for a user message
const userMessage = chatPage.getUserMessageLocator(userMessageId);

// Get a locator for an assistant message
const assistantMessage = chatPage.getAssistantMessageLocator(responseMessageId);

// Get a locator for any message (works for both user and assistant)
const message = chatPage.getMessageLocator(messageId);
```

### Assertion Helpers

The `BaseChatPage` provides several assertion helpers:

```typescript
// Assert message exists and is visible
await chatPage.assertUserMessageExists(userMessageId);
await chatPage.assertAssistantMessageExists(responseMessageId);

// Assert message contains specific text
await chatPage.assertUserMessageText(userMessageId, 'Expected text');
await chatPage.assertAssistantMessageText(responseMessageId, 'Expected response');
```

## Advanced Usage

### Testing Streaming Responses

Since message IDs are captured from the API request (before the response completes), you can test streaming responses:

```typescript
test('verify streaming response', async ({ page }) => {
	const chatPage = new ChatPage(page);
	await chatPage.goto();

	const { responseMessageIds } = await chatPage.submitMessageAndCaptureIds('Tell me a story');
	const responseMessageId = responseMessageIds[0];

	// Immediately check that response is in progress
	expect(await chatPage.isResponseInProgress()).toBe(true);

	// Assert the assistant message exists (even though it's still streaming)
	await chatPage.assertAssistantMessageExists(responseMessageId);

	// Wait for response to complete
	await chatPage.page.waitForFunction((id) => {
		const element = document.querySelector(`[data-testid="Chat_Message_Assistant_${id}"]`);
		return element && !element.textContent?.includes('[RESPONSE]');
	}, responseMessageId);

	// Now assert on the final content
	await chatPage.assertAssistantMessageText(responseMessageId, 'Once upon a time');
});
```

### Testing Multi-Response Scenarios (Split View)

When multiple models are selected, you'll get multiple response message IDs:

```typescript
test('test multi-response scenario', async ({ page }) => {
	const chatPage = new ChatPage(page);
	await chatPage.goto();

	// Select multiple models (assuming you have a method to do this)
	// ... select models ...

	// Send a message - will get multiple response IDs
	const { userMessageId, responseMessageIds } =
		await chatPage.submitMessageAndCaptureIds('Compare these models');

	// Assert all responses exist
	expect(responseMessageIds.length).toBeGreaterThan(1);
	for (const responseId of responseMessageIds) {
		await chatPage.assertAssistantMessageExists(responseId);
	}

	// Or use the helper method
	await chatPage.assertAllResponseMessagesExist(userMessageId, responseMessageIds.length);
});
```

### Testing Nonlinear Conversations

For conversations with branches or multiple responses, you can track multiple messages:

```typescript
test('test conversation with branches', async ({ page }) => {
	const chatPage = new ChatPage(page);
	await chatPage.goto();

	// Send first message
	const first = await chatPage.submitMessageAndCaptureIds('First question');
	await chatPage.assertAssistantMessageExists(first.responseMessageIds[0]);

	// Send second message (creates a new branch)
	const second = await chatPage.submitMessageAndCaptureIds('Second question');
	await chatPage.assertAssistantMessageExists(second.responseMessageIds[0]);

	// Both messages should exist
	await chatPage.assertUserMessageExists(first.userMessageId);
	await chatPage.assertUserMessageExists(second.userMessageId);
	await chatPage.assertAssistantMessageExists(first.responseMessageIds[0]);
	await chatPage.assertAssistantMessageExists(second.responseMessageIds[0]);
});
```

### Custom Assertions

You can use the locators for custom assertions:

```typescript
test('custom message assertion', async ({ page }) => {
	const chatPage = new ChatPage(page);
	await chatPage.goto();

	const { userMessageId } = await chatPage.submitMessageAndCaptureIds('Test message');

	const userMessage = chatPage.getUserMessageLocator(userMessageId);

	// Custom assertions
	await expect(userMessage).toBeVisible();
	await expect(userMessage).toHaveClass(/user-message/);

	// Check for specific elements within the message
	const editButton = userMessage.locator('.edit-user-message-button');
	await expect(editButton).toBeVisible();
});
```

## How It Works

### Data Test IDs

Messages have `data-testid` attributes added to their root elements:

- **User messages**: `Chat_Message_User_{messageId}`
- **Assistant messages**: `Chat_Message_Assistant_{messageId}`
- **Generic message locator**: `Chat_Message_{messageId}` (works for both)

These are added in:

- `src/lib/components/chat/Messages/Message.svelte`
- `src/lib/components/chat/Messages/UserMessage.svelte`
- `src/lib/components/chat/Messages/ResponseMessage.svelte`

### API Request Interception

The `submitMessageAndCaptureIds()` method:

1. Sets up a route interceptor for `**/api/chat/completions`
2. Extracts the user message ID from `postData.messages[].id` (where role is 'user')
3. Extracts response message ID(s) from `postData.id` (top-level field)
4. In multi-response scenarios, captures multiple API requests (one per model)
5. Returns the user message ID and an array of response message IDs before responses complete

This gives you early access to message IDs, allowing you to:

- Test streaming responses
- Assert on messages while they're still being generated
- Handle multi-response scenarios (split view)
- Handle edge cases where you need IDs immediately

### Important Notes About Message Relationships

**The reality of message relationships is complex:**

- Messages can be edited, regenerated, saved as copies, etc.
- In multi-response scenarios, one user message can have multiple assistant responses
- The `responseMessageIds` array represents the responses captured from API requests
- For complex scenarios (edits, branches), you may need to use `getResponseMessageIdsForUserMessage()`
  to find all current response messages for a user message
- The "message pair" concept doesn't always hold - treat it as a convenience for simple cases

## Handling Complex Scenarios

### When Message Relationships Break Down

The app supports complex message operations that break simple "pair" relationships:

- **Editing messages** - User messages can be edited after sending
- **Regenerating responses** - Assistant messages can be regenerated (creates new sibling)
- **Saving as copy** - Assistant messages can be saved as copies (creates new sibling)
- **Multi-response** - One user message can have multiple assistant responses
- **Branches** - Conversations can branch in multiple directions

For these scenarios:

1. **Capture IDs when sending** - Always use `submitMessageAndCaptureIds()` to get initial IDs
2. **Use DOM-based discovery when needed** - Use `getResponseMessageIdsForUserMessage()` to find all current responses
3. **Don't assume relationships persist** - Message IDs captured at send time may not reflect the final state after edits/regenerations
4. **Test the actual state** - Assert on what's actually in the DOM, not what you captured initially

Example:

```typescript
test('handle message regeneration', async ({ page }) => {
	const chatPage = new ChatPage(page);
	await chatPage.goto();

	// Send initial message
	const { userMessageId, responseMessageIds } = await chatPage.submitMessageAndCaptureIds('Hello');
	const originalResponseId = responseMessageIds[0];

	// Regenerate the response (this creates a new response message)
	// ... trigger regeneration ...

	// Get all current response messages (may include the new one)
	const currentResponseIds = await chatPage.getResponseMessageIdsForUserMessage(userMessageId);

	// The original response might still exist, or might be replaced
	// Assert on what's actually there
	expect(currentResponseIds.length).toBeGreaterThanOrEqual(1);
});
```

## Best Practices

1. **Always capture IDs when sending messages** - Use `submitMessageAndCaptureIds()` instead of `submitMessage()` when you need to assert on specific messages.

2. **Store message data in variables** - Keep track of message IDs for later assertions:

   ```typescript
   const message1 = await chatPage.submitMessageAndCaptureIds('First');
   const message2 = await chatPage.submitMessageAndCaptureIds('Second');
   ```

3. **Use assertion helpers** - The provided assertion methods are more readable and maintainable than custom locator chains.

4. **Wait appropriately** - Remember that assistant messages may take time to appear. Use `waitFor` or Playwright's auto-waiting features when needed.

5. **Test both user and assistant messages** - Don't forget to verify both sides of the conversation.

6. **Handle multi-response scenarios** - Always check `responseMessageIds.length` and handle arrays appropriately.

7. **Be aware of message mutations** - Messages can be edited, regenerated, etc. Don't assume captured IDs reflect final state.

## Troubleshooting

### Message IDs not captured

If `submitMessageAndCaptureIds()` throws an error about failing to capture IDs:

- Check that the route interceptor is set up before calling `submitMessage()`
- Verify the API endpoint matches `**/api/chat/completions`
- Ensure the request body structure matches what's expected

### Messages not found

If assertions fail to find messages:

- Verify the message IDs are correct
- Check that messages have actually rendered (use `waitFor` if needed)
- Ensure the `data-testid` attributes are present in the DOM

### Race conditions

If you're testing streaming responses and getting race conditions:

- Use `waitFor` to wait for specific conditions
- Don't assume messages are immediately available after sending
- Consider using `page.waitForSelector()` with the test ID if needed

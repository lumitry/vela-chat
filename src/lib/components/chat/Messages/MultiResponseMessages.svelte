<script lang="ts">
	import dayjs from 'dayjs';
	import { onMount, tick, getContext } from 'svelte';
	import { createEventDispatcher } from 'svelte';

	import { mobile, settings } from '$lib/stores';

	import { generateMoACompletion } from '$lib/apis';
	import { updateChatById } from '$lib/apis/chats';
	import { createOpenAITextStream } from '$lib/apis/streaming';

	import ResponseMessage from './ResponseMessage.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Merge from '$lib/components/icons/Merge.svelte';

	import Markdown from './Markdown.svelte';
	import Name from './Name.svelte';
	import Skeleton from './Skeleton.svelte';
	import localizedFormat from 'dayjs/plugin/localizedFormat';
	const i18n = getContext('i18n');
	dayjs.extend(localizedFormat);

	export let chatId;
	export let history;
	export let messageId;

	export let isLastMessage;
	export let readOnly = false;

	export let updateChat: Function;
	export let editMessage: Function;
	export let saveMessage: Function;
	export let rateMessage: Function;
	export let actionMessage: Function;

	export let submitMessage: Function;
	export let deleteMessage: Function;

	export let continueResponse: Function;
	export let regenerateResponse: Function;
	export let mergeResponses: Function;

	export let addMessages: Function;

	export let triggerScroll: Function;
	export let searchQuery: string = '';

	const dispatch = createEventDispatcher();

	let currentMessageId;
	let parentMessage;
	let groupedMessageIds = {};
	let groupedMessageIdsIdx = {};

	// Force reactivity by tracking a version number that changes when groupedMessageIds updates
	let groupedMessageIdsVersion = 0;

	let message = JSON.parse(JSON.stringify(history.messages[messageId]));
	$: if (history.messages) {
		if (JSON.stringify(message) !== JSON.stringify(history.messages[messageId])) {
			message = JSON.parse(JSON.stringify(history.messages[messageId]));
		}
	}

	// Reactively watch for changes to parent message's childrenIds AND history.messages
	// This ensures new assistant responses in side-by-side chats are detected immediately
	// We need to watch both childrenIds changes AND when messages are actually added to history.messages
	// Force reactivity by watching history.messages object reference changes
	$: _historyMessagesKeys = history.messages ? Object.keys(history.messages).length : 0;
	$: if (history.messages && history.messages[messageId]?.parentId) {
		const currentParentId = history.messages[messageId].parentId;
		const updatedParent = history.messages[currentParentId];

		// Also check if any of the parent's children are now in history.messages (race condition fix)
		const childrenInHistory =
			updatedParent?.childrenIds?.filter((id) => history.messages[id]) || [];
		const actualChildrenCount = childrenInHistory.length;

		if (updatedParent && updatedParent.models && updatedParent.childrenIds) {
			// Get previous valid children count (messages that exist in history.messages)
			const previousValidChildren =
				parentMessage?.childrenIds?.filter((id) => history.messages[id]) || [];
			const previousValidCount = previousValidChildren.length;

			// Check if childrenIds array changed (new IDs added)
			const childrenIdsChanged =
				!parentMessage ||
				parentMessage.id !== currentParentId ||
				!parentMessage.childrenIds ||
				parentMessage.childrenIds.length !== updatedParent.childrenIds.length ||
				parentMessage.childrenIds.some((id, idx) => id !== updatedParent.childrenIds[idx]);

			// Check if we have more valid children now than before (messages were added to history.messages)
			const moreChildrenAvailable = actualChildrenCount > previousValidCount;

			// Also check if the set of valid children IDs changed (even if count is same, IDs might be different)
			const previousValidIds = new Set(previousValidChildren);
			const currentValidIds = new Set(childrenInHistory);
			const validChildrenChanged =
				previousValidIds.size !== currentValidIds.size ||
				[...previousValidIds].some((id) => !currentValidIds.has(id)) ||
				[...currentValidIds].some((id) => !previousValidIds.has(id));

			// Check if grouping is incomplete - we have children but they're not all grouped
			const totalGroupedMessages = Object.values(groupedMessageIds || {}).reduce(
				(sum, g) => sum + (g.messageIds?.length || 0),
				0
			);
			const groupingIncomplete =
				actualChildrenCount > 0 && totalGroupedMessages < actualChildrenCount;

			if (
				childrenIdsChanged ||
				moreChildrenAvailable ||
				validChildrenChanged ||
				groupingIncomplete
			) {
				// Update parentMessage reference
				parentMessage = updatedParent;

				// Re-group messages by modelIdx
				// Filter out any children that don't exist in history.messages yet (race condition)
				const validChildrenIds = parentMessage.childrenIds.filter((id) => history.messages[id]);

				groupedMessageIds = parentMessage.models.reduce((a, model, modelIdx) => {
					let modelMessageIds = validChildrenIds
						.map((id) => history.messages[id])
						.filter((m) => m && m.modelIdx === modelIdx)
						.map((m) => m.id);

					// Legacy support
					if (modelMessageIds.length === 0) {
						let modelMessages = validChildrenIds
							.map((id) => history.messages[id])
							.filter((m) => m && m.model === model);

						modelMessages.forEach((m) => {
							m.modelIdx = modelIdx;
						});

						modelMessageIds = modelMessages.map((m) => m.id);
					}

					return {
						...a,
						[modelIdx]: { messageIds: modelMessageIds }
					};
				}, {});

				// Update indices to maintain current selection if possible
				groupedMessageIdsIdx = parentMessage.models.reduce((a, model, modelIdx) => {
					const idx = groupedMessageIds[modelIdx]?.messageIds.findIndex((id) => id === messageId);
					if (idx !== -1) {
						return {
							...a,
							[modelIdx]: idx
						};
					} else {
						// Default to last message for this model
						return {
							...a,
							[modelIdx]: Math.max(0, (groupedMessageIds[modelIdx]?.messageIds.length || 1) - 1)
						};
					}
				}, {});

				// Force reactivity by incrementing version
				groupedMessageIdsVersion++;
			}
		}
	}

	const gotoMessage = async (modelIdx, messageIdx) => {
		// Clamp messageIdx to ensure it's within valid range
		groupedMessageIdsIdx[modelIdx] = Math.max(
			0,
			Math.min(messageIdx, groupedMessageIds[modelIdx].messageIds.length - 1)
		);

		// Get the messageId at the specified index
		let messageId = groupedMessageIds[modelIdx].messageIds[groupedMessageIdsIdx[modelIdx]];
		console.log(messageId);

		// Traverse the branch to find the deepest child message
		let messageChildrenIds = history.messages[messageId].childrenIds;
		while (messageChildrenIds.length !== 0) {
			messageId = messageChildrenIds.at(-1);
			messageChildrenIds = history.messages[messageId].childrenIds;
		}

		// Update the current message ID in history
		history.currentId = messageId;

		// Await UI updates
		await tick();
		await updateChat();

		// Trigger scrolling after navigation
		triggerScroll();
	};

	const showPreviousMessage = async (modelIdx) => {
		groupedMessageIdsIdx[modelIdx] = Math.max(0, groupedMessageIdsIdx[modelIdx] - 1);

		let messageId = groupedMessageIds[modelIdx].messageIds[groupedMessageIdsIdx[modelIdx]];
		console.log(messageId);

		let messageChildrenIds = history.messages[messageId].childrenIds;

		while (messageChildrenIds.length !== 0) {
			messageId = messageChildrenIds.at(-1);
			messageChildrenIds = history.messages[messageId].childrenIds;
		}

		history.currentId = messageId;

		await tick();
		await updateChat();
		triggerScroll();
	};

	const showNextMessage = async (modelIdx) => {
		groupedMessageIdsIdx[modelIdx] = Math.min(
			groupedMessageIds[modelIdx].messageIds.length - 1,
			groupedMessageIdsIdx[modelIdx] + 1
		);

		let messageId = groupedMessageIds[modelIdx].messageIds[groupedMessageIdsIdx[modelIdx]];
		console.log(messageId);

		let messageChildrenIds = history.messages[messageId].childrenIds;

		while (messageChildrenIds.length !== 0) {
			messageId = messageChildrenIds.at(-1);
			messageChildrenIds = history.messages[messageId].childrenIds;
		}

		history.currentId = messageId;

		await tick();
		await updateChat();
		triggerScroll();
	};

	const initHandler = async () => {
		await tick();

		currentMessageId = messageId;
		parentMessage = history.messages[messageId].parentId
			? history.messages[history.messages[messageId].parentId]
			: null;

		// Filter out any children that don't exist in history.messages yet (race condition)
		const validChildrenIds = parentMessage?.childrenIds?.filter((id) => history.messages[id]) || [];

		groupedMessageIds = parentMessage?.models.reduce((a, model, modelIdx) => {
			// Find all messages that are children of the parent message and have the same model
			let modelMessageIds = validChildrenIds
				.map((id) => history.messages[id])
				.filter((m) => m && m.modelIdx === modelIdx)
				.map((m) => m.id);

			// Legacy support for messages that don't have a modelIdx
			// Find all messages that are children of the parent message and have the same model
			if (modelMessageIds.length === 0) {
				let modelMessages = validChildrenIds
					.map((id) => history.messages[id])
					.filter((m) => m && m.model === model);

				modelMessages.forEach((m) => {
					m.modelIdx = modelIdx;
				});

				modelMessageIds = modelMessages.map((m) => m.id);
			}

			return {
				...a,
				[modelIdx]: { messageIds: modelMessageIds }
			};
		}, {});

		groupedMessageIdsIdx = parentMessage?.models.reduce((a, model, modelIdx) => {
			const idx = groupedMessageIds[modelIdx].messageIds.findIndex((id) => id === messageId);
			if (idx !== -1) {
				return {
					...a,
					[modelIdx]: idx
				};
			} else {
				return {
					...a,
					[modelIdx]: groupedMessageIds[modelIdx].messageIds.length - 1
				};
			}
		}, {});

		// Force reactivity
		groupedMessageIdsVersion++;

		await tick();
	};

	const mergeResponsesHandler = async () => {
		const responses = Object.keys(groupedMessageIds).map((modelIdx) => {
			const { messageIds } = groupedMessageIds[modelIdx];
			const messageId = messageIds[groupedMessageIdsIdx[modelIdx]];

			return history.messages[messageId].content;
		});
		mergeResponses(messageId, responses, chatId);
	};

	onMount(async () => {
		await initHandler();
		await tick();

		const messageElement = document.getElementById(`message-${messageId}`);
		if (messageElement) {
			messageElement.scrollIntoView({ block: 'start' });
		}
	});
</script>

{#if parentMessage}
	<div>
		<div
			class="flex snap-x snap-mandatory overflow-x-auto scrollbar-hidden"
			id="responses-container-{chatId}-{parentMessage.id}"
		>
			{#key groupedMessageIdsVersion}
				{#each Object.keys(groupedMessageIds) as modelIdx}
					{#if groupedMessageIdsIdx[modelIdx] !== undefined && groupedMessageIds[modelIdx].messageIds.length > 0}
						<!-- svelte-ignore a11y-no-static-element-interactions -->
						<!-- svelte-ignore a11y-click-events-have-key-events -->
						{@const _messageId =
							groupedMessageIds[modelIdx].messageIds[groupedMessageIdsIdx[modelIdx]]}

						<div
							class=" snap-center w-full max-w-full m-1 border {history.messages[messageId]
								?.modelIdx == modelIdx
								? `border-gray-100 dark:border-gray-850 border-[1.5px] ${
										$mobile ? 'min-w-full' : 'min-w-80'
									}`
								: `border-gray-100 dark:border-gray-850 border-dashed ${
										$mobile ? 'min-w-full' : 'min-w-80'
									}`} transition-all p-5 rounded-2xl"
							on:click={async () => {
								if (messageId != _messageId) {
									let currentMessageId = _messageId;
									let messageChildrenIds = history.messages[currentMessageId].childrenIds;
									while (messageChildrenIds.length !== 0) {
										currentMessageId = messageChildrenIds.at(-1);
										messageChildrenIds = history.messages[currentMessageId].childrenIds;
									}
									history.currentId = currentMessageId;

									await tick();
									await updateChat();
									triggerScroll();
								}
							}}
						>
							{#key history.currentId}
								{#if message}
									<ResponseMessage
										{chatId}
										{history}
										messageId={_messageId}
										isLastMessage={true}
										siblings={groupedMessageIds[modelIdx].messageIds}
										gotoMessage={(message, messageIdx) => gotoMessage(modelIdx, messageIdx)}
										showPreviousMessage={() => showPreviousMessage(modelIdx)}
										showNextMessage={() => showNextMessage(modelIdx)}
										{updateChat}
										{editMessage}
										{saveMessage}
										{rateMessage}
										{deleteMessage}
										{actionMessage}
										{submitMessage}
										{continueResponse}
										regenerateResponse={async (message) => {
											regenerateResponse(message);
											await tick();
											groupedMessageIdsIdx[modelIdx] =
												groupedMessageIds[modelIdx].messageIds.length - 1;
										}}
										{addMessages}
										{readOnly}
									/>
								{/if}
							{/key}
						</div>
					{/if}
				{/each}
			{/key}
		</div>

		{#if !readOnly}
			{#if !Object.keys(groupedMessageIds).find((modelIdx) => {
				const { messageIds } = groupedMessageIds[modelIdx];
				const _messageId = messageIds[groupedMessageIdsIdx[modelIdx]];
				return !history.messages[_messageId]?.done ?? false;
			})}
				<div class="flex justify-end">
					<div class="w-full">
						{#if history.messages[messageId]?.merged?.status}
							{@const message = history.messages[messageId]?.merged}

							<div class="w-full rounded-xl pl-5 pr-2 py-2">
								<Name>
									Merged Response

									{#if message.timestamp}
										<span
											class=" self-center invisible group-hover:visible text-gray-400 text-xs font-medium uppercase ml-0.5 -mt-0.5"
										>
											{dayjs(message.timestamp * 1000).format('LT')}
										</span>
									{/if}
								</Name>

								<div class="mt-1 markdown-prose w-full min-w-full">
									{#if (message?.content ?? '') === ''}
										<Skeleton />
									{:else}
										<Markdown id={`merged`} content={message.content ?? ''} {searchQuery} />
									{/if}
								</div>
							</div>
						{/if}
					</div>

					{#if isLastMessage}
						<div class=" shrink-0 text-gray-600 dark:text-gray-500 mt-1">
							<Tooltip content={$i18n.t('Merge Responses')} placement="bottom">
								<button
									type="button"
									id="merge-response-button"
									class="{true
										? 'visible'
										: 'invisible group-hover:visible'} p-1 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg dark:hover:text-white hover:text-black transition"
									on:click={() => {
										mergeResponsesHandler();
									}}
								>
									<Merge className=" size-5 " />
								</button>
							</Tooltip>
						</div>
					{/if}
				</div>
			{/if}
		{/if}
	</div>
{/if}

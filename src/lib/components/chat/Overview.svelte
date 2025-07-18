<script lang="ts">
	import { getContext, createEventDispatcher, onDestroy } from 'svelte';
	import { useSvelteFlow, useNodesInitialized, useStore } from '@xyflow/svelte';

	const dispatch = createEventDispatcher();
	const i18n = getContext('i18n');

	import { onMount, tick } from 'svelte';

	import { writable } from 'svelte/store';
	import { models, showOverview, theme, user } from '$lib/stores';

	import '@xyflow/svelte/dist/style.css';

	import CustomNode from './Overview/Node.svelte';
	import Flow from './Overview/Flow.svelte';
	import XMark from '../icons/XMark.svelte';
	import ArrowLeft from '../icons/ArrowLeft.svelte';

	const { width, height } = useStore();

	const { fitView, getViewport } = useSvelteFlow();
	const nodesInitialized = useNodesInitialized();

	export let history;

	let selectedMessageId = null;

	const nodes = writable([]);
	const edges = writable([]);

	const nodeTypes = {
		custom: CustomNode
	};

	$: if (history) {
		drawFlow();
	}

	$: if (history && history.currentId) {
		focusNode();
	}

	const focusNode = async () => {
		if (selectedMessageId === null) {
			await fitView({ nodes: [{ id: history.currentId }] });
		} else {
			await fitView({ nodes: [{ id: selectedMessageId }] });
		}

		selectedMessageId = null;
	};

	const drawFlow = async () => {
		const nodeList = [];
		const edgeList = [];
		const levelOffset = 150; // Vertical spacing between layers
		const siblingOffset = 250; // Horizontal spacing between nodes at the same layer

		// Map to keep track of node positions at each level
		let positionMap = new Map();

		// Helper function to truncate labels
		function createLabel(content) {
			const maxLength = 100;
			return content.length > maxLength ? content.substr(0, maxLength) + '...' : content;
		}

		// Create nodes and map children to ensure alignment in width
		let layerWidths = {}; // Track widths of each layer

		Object.keys(history.messages).forEach((id) => {
			const message = history.messages[id];
			const level = message.parentId ? (positionMap.get(message.parentId)?.level ?? -1) + 1 : 0;
			if (!layerWidths[level]) layerWidths[level] = 0;

			positionMap.set(id, {
				id: message.id,
				level,
				position: layerWidths[level]++
			});
		});

		// Adjust positions based on siblings count to centralize vertical spacing
		Object.keys(history.messages).forEach((id) => {
			const messageObj = history.messages[id];
			const rawContent = messageObj.content || '';
			const contentWithoutReasoning = rawContent
				.replace(/<details\b[^>]*\btype=["']reasoning["'][^>]*>[\s\S]*?<\/details>/g, '')
				.trim();
			const truncatedContent = createLabel(contentWithoutReasoning);
			const pos = positionMap.get(id);
			const xOffset = pos.position * siblingOffset;
			const y = pos.level * levelOffset;
			const x = xOffset;

			nodeList.push({
				id: pos.id,
				type: 'custom',
				data: {
					user: $user,
					message: { ...messageObj, content: truncatedContent },
					model: $models.find((model) => model.id === messageObj.model)
				},
				position: { x, y }
			});

			// Create edges
			const parentId = history.messages[id].parentId;
			if (parentId) {
				edgeList.push({
					id: parentId + '-' + pos.id,
					source: parentId,
					target: pos.id,
					selectable: false,
					class: ' dark:fill-gray-300 fill-gray-300',
					type: 'smoothstep',
					animated: history.currentId === id || recurseCheckChild(id, history.currentId)
				});
			}
		});

		await edges.set([...edgeList]);
		await nodes.set([...nodeList]);
	};

	const recurseCheckChild = (nodeId, currentId) => {
		const node = history.messages[nodeId];
		return (
			node.childrenIds &&
			node.childrenIds.some((id) => id === currentId || recurseCheckChild(id, currentId))
		);
	};

	onMount(() => {
		drawFlow();

		nodesInitialized.subscribe(async (initialized) => {
			if (initialized) {
				await tick();
				const res = await fitView({ nodes: [{ id: history.currentId }] });
			}
		});

		width.subscribe((value) => {
			if (value) {
				// fitView();
				fitView({ nodes: [{ id: history.currentId }] });
			}
		});

		height.subscribe((value) => {
			if (value) {
				// fitView();
				fitView({ nodes: [{ id: history.currentId }] });
			}
		});
	});

	onDestroy(() => {
		console.log('Overview destroyed');

		nodes.set([]);
		edges.set([]);
	});
</script>

<div class="w-full h-full relative">
	<div class=" absolute z-50 w-full flex justify-between dark:text-gray-100 px-4 py-3.5">
		<div class="flex items-center gap-2.5">
			<button
				class="self-center p-0.5"
				on:click={() => {
					showOverview.set(false);
				}}
			>
				<ArrowLeft className="size-3.5" />
			</button>
			<div class=" text-lg font-medium self-center font-primary">{$i18n.t('Chat Overview')}</div>
		</div>
		<button
			class="self-center p-0.5"
			on:click={() => {
				dispatch('close');
				showOverview.set(false);
			}}
		>
			<XMark className="size-3.5" />
		</button>
	</div>

	{#if $nodes.length > 0}
		<Flow
			{nodes}
			{nodeTypes}
			{edges}
			on:nodeclick={(e) => {
				console.log(e.detail.node.data);
				dispatch('nodeclick', e.detail);
				selectedMessageId = e.detail.node.data.message.id;
				fitView({ nodes: [{ id: selectedMessageId }] });
			}}
		/>
	{/if}
</div>

<script lang="ts">
	import Sortable from 'sortablejs';

	import { createEventDispatcher, getContext, onMount } from 'svelte';
	const i18n: any = getContext('i18n');

	import { models } from '$lib/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import EllipsisVertical from '$lib/components/icons/EllipsisVertical.svelte';
	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';

	export let modelIds: string[] = [];

	let sortable: any = null;
	let modelListElement: HTMLElement | null = null;

	const positionChangeHandler = () => {
		if (!modelListElement) return;

		const modelList = Array.from(modelListElement.children).map((child) =>
			child.id.replace('model-item-', '')
		);

		modelIds = modelList;
	};

	const moveToTop = (modelId: string) => {
		const currentIndex = modelIds.indexOf(modelId);
		if (currentIndex > 0) {
			modelIds = [modelId, ...modelIds.filter((id) => id !== modelId)];
		}
	};

	const moveToBottom = (modelId: string) => {
		const currentIndex = modelIds.indexOf(modelId);
		if (currentIndex < modelIds.length - 1) {
			modelIds = [...modelIds.filter((id) => id !== modelId), modelId];
		}
	};

	$: if (modelIds) {
		init();
	}

	const init = () => {
		if (sortable) {
			sortable.destroy();
		}

		if (modelListElement) {
			sortable = Sortable.create(modelListElement, {
				animation: 150,
				handle: '.item-handle',
				onUpdate: async (event: any) => {
					positionChangeHandler();
				}
			});
		}
	};
</script>

{#if modelIds.length > 0}
	<div class="flex flex-col -translate-x-1" bind:this={modelListElement}>
		{#each modelIds as modelId, modelIdx (modelId)}
			<div class=" flex gap-2 w-full justify-between items-center" id="model-item-{modelId}">
				<Tooltip content={modelId} placement="top-start">
					<div class="flex items-center gap-1 flex-1">
						<EllipsisVertical className="size-4 cursor-move item-handle" />

						<div class=" text-sm flex-1 py-1 rounded-lg">
							{#if $models.find((model) => model.id === modelId)}
								{$models.find((model) => model.id === modelId)?.name}
							{:else}
								{modelId}
							{/if}
						</div>
					</div>
				</Tooltip>

				<div class="flex items-center gap-0.5 ml-2">
					<Tooltip content="Move to top" placement="top">
						<button
							type="button"
							class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
							on:click={() => moveToTop(modelId)}
							disabled={modelIdx === 0}
							class:opacity-50={modelIdx === 0}
							class:cursor-not-allowed={modelIdx === 0}
						>
							<ChevronUp className="size-3" />
						</button>
					</Tooltip>

					<Tooltip content="Move to bottom" placement="top">
						<button
							type="button"
							class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
							on:click={() => moveToBottom(modelId)}
							disabled={modelIdx === modelIds.length - 1}
							class:opacity-50={modelIdx === modelIds.length - 1}
							class:cursor-not-allowed={modelIdx === modelIds.length - 1}
						>
							<ChevronDown className="size-3" />
						</button>
					</Tooltip>
				</div>
			</div>
		{/each}
	</div>
{:else}
	<div class="text-gray-500 text-xs text-center py-2">
		{$i18n.t('No models found')}
	</div>
{/if}

<script lang="ts">
import type { ComponentType } from 'svelte';
	import type { Command } from '$lib/utils/commandPalette/types';
	import { loadIcon } from '$lib/utils/commandPalette/iconCache';

	export let command: Command;
	export let selected = false;

	let iconComponent: ComponentType | null = null;

	$: loadCommandIcon(command.icon);

	async function loadCommandIcon(source) {
		if (!source) {
			iconComponent = null;
			return;
		}
		const loaded = await loadIcon(source);
		iconComponent = loaded;
	}
</script>

<li
	class={`flex items-center px-3 py-2 rounded-lg transition-colors ${
		selected
			? 'bg-gray-200 text-gray-900 dark:bg-gray-800 dark:text-white'
			: 'hover:bg-gray-100 dark:hover:bg-gray-850'
	}`}
>
	<div class="flex items-center gap-3 w-full">
		{#if iconComponent}
			<svelte:component
				this={iconComponent}
				class="w-4 h-4 text-gray-500 dark:text-gray-400 shrink-0"
			/>
		{/if}

		<div class="flex flex-col flex-1 text-sm text-gray-900 dark:text-gray-100">
			<span class="font-medium leading-tight">{command.label}</span>
			{#if command.description}
				<span class="text-xs text-gray-500 dark:text-gray-300 leading-tight">
					{command.description}
				</span>
			{/if}
		</div>

		{#if command.shortcut}
			<div class="text-xs font-medium text-gray-500 dark:text-gray-400">
				{command.shortcut}
			</div>
		{/if}
	</div>
</li>

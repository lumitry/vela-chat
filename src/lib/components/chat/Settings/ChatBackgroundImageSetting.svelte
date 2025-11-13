<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	export let backgroundImageUrl: any = null;
	export let filesInputElement: any = null;
	export let saveSettings: Function;
</script>

<div class="mb-3">
	<div class="py-0.5 flex w-full justify-between">
		<div class="self-center text-xs">{$i18n.t('Chat Background Image')}</div>
		<button
			class="p-1 px-3 text-xs flex rounded-sm transition"
			on:click={async () => {
				if (backgroundImageUrl !== null && backgroundImageUrl !== undefined) {
					await saveSettings({ backgroundImageUrl: null });
				} else if (filesInputElement) {
					filesInputElement.click();
				}
			}}
			type="button"
		>
			{#if backgroundImageUrl !== null && backgroundImageUrl !== undefined}
				<span class="ml-2 self-center">{$i18n.t('Reset')}</span>
			{:else}
				<span class="ml-2 self-center">{$i18n.t('Upload')}</span>
			{/if}
		</button>
	</div>
</div>


<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	export let imageCompressionSize: { width: string; height: string };
	export let saveSettings: Function;

	const handleBlur = () => {
		saveSettings({ imageCompressionSize });
	};
</script>

<div class="mb-3">
	<div class="py-0.5 flex w-full justify-between text-xs">
		<div class="self-center text-xs">{$i18n.t('Image Max Compression Size')}</div>
		<div>
			<input
				bind:value={imageCompressionSize.width}
				type="number"
				class="w-20 bg-transparent outline-hidden text-center"
				min="0"
				placeholder="Width"
				on:blur={handleBlur}
			/>x
			<input
				bind:value={imageCompressionSize.height}
				type="number"
				class="w-20 bg-transparent outline-hidden text-center"
				min="0"
				placeholder="Height"
				on:blur={handleBlur}
			/>
		</div>
	</div>
</div>


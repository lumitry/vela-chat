<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	interface Props {
		imageCompressionSize: { width: string; height: string };
		saveSettings: Function;
	}

	let { imageCompressionSize = $bindable(), saveSettings }: Props = $props();

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
				onblur={handleBlur}
			/>x
			<input
				bind:value={imageCompressionSize.height}
				type="number"
				class="w-20 bg-transparent outline-hidden text-center"
				min="0"
				placeholder="Height"
				onblur={handleBlur}
			/>
		</div>
	</div>
</div>


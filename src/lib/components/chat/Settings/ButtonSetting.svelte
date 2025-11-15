<script lang="ts">
	import { getContext, afterUpdate } from 'svelte';
	const i18n = getContext('i18n');

	export let getValue: () => any;
	export let getLabel: (value: any) => string;
	export let onClick: () => void | Promise<void>;

	let label = getLabel(getValue());
	
	// Update label after every component update to catch parent changes
	afterUpdate(() => {
		label = getLabel(getValue());
	});
	
	const handleClick = async () => {
		await onClick();
		// Force update after onClick
		label = getLabel(getValue());
	};
</script>

<button
	class="p-1 px-3 text-xs flex rounded-sm transition"
	on:click={handleClick}
	type="button"
>
	<span class="ml-2 self-center">{$i18n.t(label)}</span>
</button>


<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	interface Props {
		getValue: () => any;
		getLabel: (value: any) => string;
		onClick: () => void | Promise<void>;
	}

	let { getValue, getLabel, onClick }: Props = $props();

	let label = $state(getLabel(getValue()));

	// Update label when getValue() changes
	$effect(() => {
		label = getLabel(getValue());
	});

	const handleClick = async () => {
		await onClick();
		// Force update after onClick
		label = getLabel(getValue());
	};
</script>

<button class="p-1 px-3 text-xs flex rounded-sm transition" on:click={handleClick} type="button">
	<span class="ml-2 self-center">{$i18n.t(label)}</span>
</button>

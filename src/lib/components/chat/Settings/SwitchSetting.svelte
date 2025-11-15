<script lang="ts">
	import Switch from '$lib/components/common/Switch.svelte';
	import { onMount } from 'svelte';

	export let get: () => boolean;
	export let set: (value: boolean) => boolean | Promise<boolean>;

	let value = false;

	onMount(() => {
		value = get();
	});

	const handleChange = async (event: CustomEvent<boolean>) => {
		// The event contains the new state value
		const newValue = event.detail ?? value;

		// Update our local value to match
		value = newValue;

		// Call set with the new value
		const result = await set(newValue);

		if (result === false) {
			// Revert if set failed
			value = !newValue;
		}
	};
</script>

<Switch bind:state={value} on:change={handleChange} />

<script lang="ts">
	export let value: string;
	export let options: Array<{ value: string; label: string }>;
	export let onChange: (value: string) => void | Promise<void>;
</script>

<select
	class="px-2 py-1 text-xs bg-transparent border border-gray-200 dark:border-gray-700 rounded-sm"
	bind:value
	on:change={() => onChange(value)}
>
	{#each options as option}
		<option value={option.value}>{option.label}</option>
	{/each}
</select>


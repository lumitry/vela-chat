<script lang="ts">
	interface Props {
		value: string;
		options: Array<{ value: string; label: string }>;
		onChange: (value: string) => void | Promise<void>;
	}

	let { value = $bindable(), options, onChange }: Props = $props();
</script>

<select
	class="px-2 py-1 text-xs bg-transparent border border-gray-200 dark:border-gray-700 rounded-sm"
	bind:value
	onchange={() => onChange(value)}
>
	{#each options as option}
		<option value={option.value}>{option.label}</option>
	{/each}
</select>


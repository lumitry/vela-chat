<script lang="ts">
	interface Props {
		label: string;
		children?: import('svelte').Snippet;
	}

	let { label, children }: Props = $props();
</script>

<div class="mb-1">
	<div class="py-0.5 flex w-full justify-between">
		<div class="self-center text-xs">{label}</div>
		{@render children?.()}
	</div>
</div>

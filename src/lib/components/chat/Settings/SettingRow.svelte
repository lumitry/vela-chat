<script lang="ts">
	export let label: string;
</script>

<div class="mb-1">
	<div class="py-0.5 flex w-full justify-between">
		<div class="self-center text-xs">{label}</div>
		<slot />
	</div>
</div>

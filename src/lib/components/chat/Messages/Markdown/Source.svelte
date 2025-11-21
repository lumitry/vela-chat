<script lang="ts">
	import { run } from 'svelte/legacy';

	import { getSiteTitleFromUrl } from '$lib/utils/index';

	interface Props {
		id: any;
		token: any;
		onClick?: Function;
	}

	let { id, token, onClick = () => {} }: Props = $props();

	let attributes: Record<string, string | undefined> = $state({});

	function extractAttributes(input: string): Record<string, string> {
		const regex = /(\w+)="([^"]*)"/g;
		let match;
		let attrs: Record<string, string> = {};

		// Loop through all matches and populate the attributes object
		while ((match = regex.exec(input)) !== null) {
			attrs[match[1]] = match[2];
		}

		return attrs;
	}

	// Helper function to check if text is a URL and return the site title
	function formattedTitle(title: string): string {
		if (title.startsWith('http')) {
			return getSiteTitleFromUrl(title);
		}

		return title;
	}

	run(() => {
		attributes = extractAttributes(token.text);
	});
</script>

{#if attributes.title !== 'N/A'}
	<button
		class="text-xs font-medium w-fit translate-y-[2px] px-2 py-0.5 dark:bg-white/5 dark:text-white/60 dark:hover:text-white bg-gray-50 text-black/60 hover:text-black transition rounded-lg"
		onclick={() => {
			onClick(id, attributes.data);
		}}
	>
		<span class="line-clamp-1">
			{attributes.title ? formattedTitle(attributes.title) : ''}
		</span>
	</button>
{/if}

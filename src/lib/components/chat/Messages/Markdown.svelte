<script lang="ts">
	import { run } from 'svelte/legacy';

	import { marked } from 'marked';
	import { replaceTokens, processResponseContent, escapeSingleTildes } from '$lib/utils';
	import { user } from '$lib/stores';

	import markedExtension from '$lib/utils/marked/extension';
	import markedKatexExtension from '$lib/utils/marked/katex-extension';

	import MarkdownTokens from './Markdown/MarkdownTokens.svelte';
	import { createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher();



	interface Props {
		id?: string;
		content: any;
		model?: any;
		save?: boolean;
		sourceIds?: any;
		onSourceClick?: any;
		onTaskClick?: any;
		searchQuery?: string;
	}

	let {
		id = '',
		content,
		model = null,
		save = false,
		sourceIds = [],
		onSourceClick = () => {},
		onTaskClick = () => {},
		searchQuery = ''
	}: Props = $props();

	let tokens = $state([]);

	const options = {
		throwOnError: false
	};

	marked.use(markedKatexExtension(options));
	marked.use(markedExtension(options));

	run(() => {
		(async () => {
			if (content) {
				const processedContent = escapeSingleTildes(
					replaceTokens(processResponseContent(content), sourceIds, model?.name, $user?.name)
				);
				tokens = marked.lexer(processedContent);
			}
		})();
	});
</script>

{#key id}
	<MarkdownTokens
		{tokens}
		{id}
		{save}
		{onTaskClick}
		{onSourceClick}
		{searchQuery}
		on:update={(e) => {
			dispatch('update', e.detail);
		}}
		on:code={(e) => {
			dispatch('code', e.detail);
		}}
	/>
{/key}

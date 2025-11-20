<script>
	import { createEventDispatcher, getContext } from 'svelte';
	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	import Markdown from './Markdown.svelte';
	import { chatId, mobile, settings, showArtifacts, showControls } from '$lib/stores';

	export let id;
	export let content;
	export let model = null;
	export let sources = null;

	export let save = false;

	export let onSourceClick = () => {};
	export let onTaskClick = () => {};
	export let searchQuery = '';
</script>

<div>
	<Markdown
		{id}
		{content}
		{model}
		{save}
		{searchQuery}
		sourceIds={(sources ?? []).reduce((acc, s) => {
			let ids = [];
			s.document.forEach((document, index) => {
				if (model?.info?.meta?.capabilities?.citations == false) {
					ids.push('N/A');
					return ids;
				}

				const metadata = s.metadata?.[index];
				const id = metadata?.source ?? 'N/A';

				// Prefer site_name or name from metadata (extracted from og:site_name)
				if (metadata?.site_name) {
					ids.push(metadata.site_name);
					return ids;
				}
				if (metadata?.name) {
					ids.push(metadata.name);
					return ids;
				}

				if (id.startsWith('http://') || id.startsWith('https://')) {
					ids.push(id);
				} else {
					ids.push(s?.source?.name ?? id);
				}

				return ids;
			});

			acc = [...acc, ...ids];

			// remove duplicates
			return acc.filter((item, index) => acc.indexOf(item) === index);
		}, [])}
		{onSourceClick}
		{onTaskClick}
		on:update={(e) => {
			dispatch('update', e.detail);
		}}
		on:code={(e) => {
			const { lang, code } = e.detail;

			if (
				($settings?.detectArtifacts ?? true) &&
				(['html', 'svg'].includes(lang) || (lang === 'xml' && code.includes('svg'))) &&
				!$mobile &&
				$chatId
			) {
				showArtifacts.set(true);
				showControls.set(true);
			}
		}}
	/>
</div>

<script lang="ts">
	import MarkdownInlineTokens from './MarkdownInlineTokens.svelte';
	import DOMPurify from 'dompurify';
	import { toast } from 'svelte-sonner';

	import type { Token } from 'marked';
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { copyToClipboard, unescapeHtml } from '$lib/utils';
	import { settings } from '$lib/stores';

	import Image from '$lib/components/common/Image.svelte';
	import KatexRenderer from './KatexRenderer.svelte';
	import Source from './Source.svelte';

	interface Props {
		id: string;
		tokens: Token[];
		onSourceClick?: Function;
		searchQuery?: string;
	}

	let {
		id,
		tokens,
		onSourceClick = () => {},
		searchQuery = ''
	}: Props = $props();

	const hexColorRegex = /(#[0-9a-fA-F]{6,8})\b/g;

	// Function to highlight search text in a string
	function highlightText(text: string, query: string): string | Array<{ text: string; highlighted: boolean }> {
		if (!query || !text) return text;
		
		const lowerText = text.toLowerCase();
		const lowerQuery = query.toLowerCase();
		const parts: Array<{ text: string; highlighted: boolean }> = [];
		let lastIndex = 0;
		let index = lowerText.indexOf(lowerQuery, lastIndex);
		
		while (index !== -1) {
			// Add text before match
			if (index > lastIndex) {
				parts.push({ text: text.substring(lastIndex, index), highlighted: false });
			}
			// Add highlighted match
			parts.push({ text: text.substring(index, index + query.length), highlighted: true });
			lastIndex = index + query.length;
			index = lowerText.indexOf(lowerQuery, lastIndex);
		}
		
		// Add remaining text
		if (lastIndex < text.length) {
			parts.push({ text: text.substring(lastIndex), highlighted: false });
		}
		
		return parts.length > 0 ? parts : text;
	}
</script>

{#each tokens as token}
	{#if token.type === 'escape'}
		{unescapeHtml(token.text)}
	{:else if token.type === 'html'}
		{@const html = DOMPurify.sanitize(token.text)}
		{#if html && html.includes('<video')}
			{@html html}
		{:else if token.text.includes(`<iframe src="${WEBUI_BASE_URL}/api/v1/files/`)}
			{@html `${token.text}`}
		{:else if token.text.includes(`<source_id`)}
			<Source {id} {token} onClick={onSourceClick} />
		{:else}
			{@html html}
		{/if}
	{:else if token.type === 'link'}
		{#if token.tokens}
			<a href={token.href} target="_blank" rel="nofollow" title={token.title}>
				<MarkdownInlineTokens id={`${id}-a`} tokens={token.tokens} {onSourceClick} {searchQuery} />
			</a>
		{:else}
			<a href={token.href} target="_blank" rel="nofollow" title={token.title}>
				{#if searchQuery}
					{@const highlighted = highlightText(token.text, searchQuery)}
					{#if Array.isArray(highlighted)}
						{#each highlighted as part}
							{#if part.highlighted}
								<mark class="bg-yellow-200 dark:bg-yellow-800/50 rounded px-0.5">{part.text}</mark>
							{:else}
								{part.text}
							{/if}
						{/each}
					{:else}
						{highlighted}
					{/if}
				{:else}
					{token.text}
				{/if}
			</a>
		{/if}
	{:else if token.type === 'image'}
		<Image src={token.href} alt={token.text} />
	{:else if token.type === 'strong'}
		<strong><MarkdownInlineTokens id={`${id}-strong`} tokens={token.tokens} {onSourceClick} {searchQuery} /></strong>
	{:else if token.type === 'em'}
		<em><MarkdownInlineTokens id={`${id}-em`} tokens={token.tokens} {onSourceClick} {searchQuery} /></em>
	{:else if token.type === 'codespan'}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<code
			class="codespan cursor-pointer"
			onclick={() => {
				copyToClipboard(unescapeHtml(token.text));
				toast.success($i18n.t('Copied to clipboard'));
			}}>{unescapeHtml(token.text)}</code
		>
	{:else if token.type === 'br'}
		<br />
	{:else if token.type === 'del'}
		<del><MarkdownInlineTokens id={`${id}-del`} tokens={token.tokens} {onSourceClick} {searchQuery} /></del>
	{:else if token.type === 'inlineKatex'}
		{#if token.text}
			<KatexRenderer content={token.text} displayMode={false} />
		{/if}
	{:else if token.type === 'iframe'}
		<iframe
			src="{WEBUI_BASE_URL}/api/v1/files/{token.fileId}/content"
			title={token.fileId}
			width="100%"
			frameborder="0"
			onload={(e) => {
				const iframe = e.target as HTMLIFrameElement;
				if (iframe.contentWindow?.document?.body) {
					iframe.style.height = iframe.contentWindow.document.body.scrollHeight + 20 + 'px';
				}
			}}
		></iframe>
	{:else if token.type === 'text'}
		{#if $settings?.showHexColorSwatches ?? true}
			{#each token.raw.split(hexColorRegex) as part, i}
				{#if i % 2 === 1}
					<span class="inline-flex items-center">
						<!-- svelte-ignore a11y_click_events_have_key_events -->
						<!-- svelte-ignore a11y_no_static_element_interactions -->
						<span
							class="inline-block w-4 h-4 mr-1 border border-gray-300 dark:border-gray-600 rounded-sm cursor-pointer"
							style="background-color: {part};"
							onclick={() => {
								copyToClipboard(part);
								toast.success($i18n.t('Copied to clipboard'));
							}}
						></span>
						{#if searchQuery}
							{@const highlighted = highlightText(part, searchQuery)}
							{#if Array.isArray(highlighted)}
								{#each highlighted as highlightPart}
									{#if highlightPart.highlighted}
										<mark class="bg-yellow-200 dark:bg-yellow-800/50 rounded px-0.5">{highlightPart.text}</mark>
									{:else}
										{highlightPart.text}
									{/if}
								{/each}
							{:else}
								{highlighted}
							{/if}
						{:else}
							{part}
						{/if}
					</span>
				{:else}
					{#if searchQuery}
						{@const highlighted = highlightText(part, searchQuery)}
						{#if Array.isArray(highlighted)}
							{#each highlighted as highlightPart}
								{#if highlightPart.highlighted}
									<mark class="bg-yellow-200 dark:bg-yellow-800/50 rounded px-0.5">{highlightPart.text}</mark>
								{:else}
									{highlightPart.text}
								{/if}
							{/each}
						{:else}
							{highlighted}
						{/if}
					{:else}
						{part}
					{/if}
				{/if}
			{/each}
		{:else}
			{#if searchQuery}
				{@const highlighted = highlightText(token.raw, searchQuery)}
				{#if Array.isArray(highlighted)}
					{#each highlighted as part}
						{#if part.highlighted}
							<mark class="bg-yellow-200 dark:bg-yellow-800/50 rounded px-0.5">{part.text}</mark>
						{:else}
							{part.text}
						{/if}
					{/each}
				{:else}
					{highlighted}
				{/if}
			{:else}
				{token.raw}
			{/if}
		{/if}
	{/if}
{/each}

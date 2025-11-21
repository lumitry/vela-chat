<script lang="ts">
	import DOMPurify from 'dompurify';

	import { onDestroy } from 'svelte';
	import { marked } from 'marked';

	import tippy from 'tippy.js';
	import type { Instance } from 'tippy.js';

	interface Props {
		placement?: string;
		content?: any;
		touch?: boolean;
		className?: string;
		theme?: string;
		offset?: any;
		allowHTML?: boolean;
		tippyOptions?: any;
		children?: import('svelte').Snippet;
	}

	let {
		placement = 'top',
		content = `I'm a tooltip!`,
		touch = true,
		className = 'flex',
		theme = '',
		offset = [0, 4],
		allowHTML = true,
		tippyOptions = {},
		children
	}: Props = $props();

	let tooltipElement = $state<HTMLElement | null>(null);
	let tooltipInstance: Instance | null = null;

	$effect(() => {
		const element = tooltipElement;
		const sanitizedContent = DOMPurify.sanitize(content ?? '');

		if (!element || !sanitizedContent) {
			if (tooltipInstance) {
				tooltipInstance.destroy();
				tooltipInstance = null;
			}
			return;
		}

		if (tooltipInstance) {
			tooltipInstance.setContent(sanitizedContent);
			tooltipInstance.setProps({
				placement,
				allowHTML,
				touch,
				arrow: false,
				...(theme !== '' ? { theme } : { theme: 'dark' }),
				offset,
				...tippyOptions
			});
		} else {
			tooltipInstance = tippy(element, {
				content: sanitizedContent,
				placement,
				allowHTML,
				touch,
				...(theme !== '' ? { theme } : { theme: 'dark' }),
				arrow: false,
				offset,
				...tippyOptions
			}) as Instance;
		}
	});

	onDestroy(() => {
		if (tooltipInstance) {
			tooltipInstance.destroy();
			tooltipInstance = null;
		}
	});
</script>

<div bind:this={tooltipElement} aria-label={DOMPurify.sanitize(content)} class={className}>
	{@render children?.()}
</div>

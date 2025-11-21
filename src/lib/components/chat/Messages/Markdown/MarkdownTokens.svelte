<script lang="ts">
	import MarkdownTokens from './MarkdownTokens.svelte';
	import DOMPurify from 'dompurify';
	import { createEventDispatcher, onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	const i18n = getContext('i18n');

	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { marked, type Token } from 'marked';
	import { unescapeHtml, copyToClipboard } from '$lib/utils';

	import { WEBUI_BASE_URL } from '$lib/constants';

	import CodeBlock from '$lib/components/chat/Messages/CodeBlock.svelte';
	import MarkdownInlineTokens from '$lib/components/chat/Messages/Markdown/MarkdownInlineTokens.svelte';
	import KatexRenderer from './KatexRenderer.svelte';
	import AlertRenderer, { alertComponent } from './AlertRenderer.svelte';
	import Collapsible from '$lib/components/common/Collapsible.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';
	import Clipboard from '$lib/components/icons/Clipboard.svelte';

	import Source from './Source.svelte';
	import { settings } from '$lib/stores';

	const dispatch = createEventDispatcher();



	interface Props {
		id: string;
		tokens: Token[];
		top?: boolean;
		attributes?: any;
		save?: boolean;
		onTaskClick?: Function;
		onSourceClick?: Function;
		searchQuery?: string;
	}

	let {
		id,
		tokens,
		top = true,
		attributes = {},
		save = false,
		onTaskClick = () => {},
		onSourceClick = () => {},
		searchQuery = ''
	}: Props = $props();

	const headerComponent = (depth: number) => {
		return 'h' + depth;
	};

	const exportTableToCSVHandler = (token, tokenIdx = 0) => {
		console.log('Exporting table to CSV');

		// Extract header row text and escape for CSV.
		const header = token.header.map((headerCell) => `"${headerCell.text.replace(/"/g, '""')}"`);

		// Create an array for rows that will hold the mapped cell text.
		const rows = token.rows.map((row) =>
			row.map((cell) => {
				// Map tokens into a single text
				const cellContent = cell.tokens.map((token) => token.text).join('');
				// Escape double quotes and wrap the content in double quotes
				return `"${cellContent.replace(/"/g, '""')}"`;
			})
		);

		// Combine header and rows
		const csvData = [header, ...rows];

		// Join the rows using commas (,) as the separator and rows using newline (\n).
		const csvContent = csvData.map((row) => row.join(',')).join('\n');

		// Log rows and CSV content to ensure everything is correct.
		console.log(csvData);
		console.log(csvContent);

		// To handle Unicode characters, you need to prefix the data with a BOM:
		const bom = '\uFEFF'; // BOM for UTF-8

		// Create a new Blob prefixed with the BOM to ensure proper Unicode encoding.
		const blob = new Blob([bom + csvContent], { type: 'text/csv;charset=UTF-8' });

		// Use FileSaver.js's saveAs function to save the generated CSV file.
		saveAs(blob, `table-${id}-${tokenIdx}.csv`);
	};

	const copyTableToClipboardHandler = (token) => {
		console.log('Copying table to clipboard');

		// Extract header row text for markdown
		const headerRow = token.header.map((headerCell) => headerCell.text).join(' | ');

		// Create separator row for markdown table
		const separatorRow = token.header.map(() => '---').join(' | ');

		// Extract data rows
		const dataRows = token.rows.map((row) =>
			row
				.map((cell) => {
					// Map tokens into a single text
					return cell.tokens.map((token) => token.text).join('');
				})
				.join(' | ')
		);

		// Combine all parts to create markdown table
		const markdownTable = [
			`| ${headerRow} |`,
			`| ${separatorRow} |`,
			...dataRows.map((row) => `| ${row} |`)
		].join('\n');

		copyToClipboard(markdownTable);
		toast.success($i18n.t('Copied to clipboard'));
	};
</script>

<!-- {JSON.stringify(tokens)} -->
{#each tokens as token, tokenIdx (tokenIdx)}
	{#if token.type === 'hr'}
		<hr class=" border-gray-100 dark:border-gray-850" />
	{:else if token.type === 'heading'}
		<svelte:element this={headerComponent(token.depth)} dir="auto">
			<MarkdownInlineTokens
				id={`${id}-${tokenIdx}-h`}
				tokens={token.tokens}
				{onSourceClick}
				{searchQuery}
			/>
		</svelte:element>
	{:else if token.type === 'code'}
		{#if token.raw.includes('```')}
			<CodeBlock
				id={`${id}-${tokenIdx}`}
				collapsed={$settings?.collapseCodeBlocks ?? false}
				{token}
				lang={token?.lang ?? ''}
				code={token?.text ?? ''}
				{attributes}
				{save}
				onCode={(value) => {
					dispatch('code', value);
				}}
				onSave={(value) => {
					dispatch('update', {
						raw: token.raw,
						oldContent: token.text,
						newContent: value
					});
				}}
			/>
		{:else}
			{token.text}
		{/if}
	{:else if token.type === 'table'}
		<div class="relative w-full group">
			<div class="scrollbar-hidden relative overflow-x-auto max-w-full rounded-lg">
				<table
					class=" w-full text-sm text-left text-gray-500 dark:text-gray-400 max-w-full rounded-xl"
				>
					<thead
						class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-850 dark:text-gray-400 border-none"
					>
						<tr class="">
							{#each token.header as header, headerIdx}
								<th
									scope="col"
									class="px-3! py-1.5! cursor-pointer border border-gray-100 dark:border-gray-850"
									style={token.align[headerIdx] ? '' : `text-align: ${token.align[headerIdx]}`}
								>
									<div class="gap-1.5 text-left">
										<div class="shrink-0 break-normal">
											<MarkdownInlineTokens
												id={`${id}-${tokenIdx}-header-${headerIdx}`}
												tokens={header.tokens}
												{onSourceClick}
												{searchQuery}
											/>
										</div>
									</div>
								</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each token.rows as row, rowIdx}
							<tr class="bg-white dark:bg-gray-900 dark:border-gray-850 text-xs">
								{#each row ?? [] as cell, cellIdx}
									<td
										class="px-3! py-1.5! text-gray-900 dark:text-white w-max border border-gray-100 dark:border-gray-850"
										style={token.align[cellIdx] ? '' : `text-align: ${token.align[cellIdx]}`}
									>
										<div class="break-normal">
											<MarkdownInlineTokens
												id={`${id}-${tokenIdx}-row-${rowIdx}-${cellIdx}`}
												tokens={cell.tokens}
												{onSourceClick}
												{searchQuery}
											/>
										</div>
									</td>
								{/each}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<div class=" absolute top-1 right-1.5 z-20 invisible group-hover:visible">
				<div class="flex gap-1">
					<Tooltip content={$i18n.t('Copy table to clipboard')}>
						<button
							class="p-1 rounded-lg bg-transparent transition"
							onclick={(e) => {
								e.stopPropagation();
								copyTableToClipboardHandler(token);
							}}
						>
							<Clipboard className=" size-3.5" strokeWidth="1.5" />
						</button>
					</Tooltip>
					<Tooltip content={$i18n.t('Export to CSV')}>
						<button
							class="p-1 rounded-lg bg-transparent transition"
							onclick={(e) => {
								e.stopPropagation();
								exportTableToCSVHandler(token, tokenIdx);
							}}
						>
							<ArrowDownTray className=" size-3.5" strokeWidth="1.5" />
						</button>
					</Tooltip>
				</div>
			</div>
		</div>
	{:else if token.type === 'blockquote'}
		{@const alert = alertComponent(token)}
		{#if alert}
			<AlertRenderer {token} {alert} />
		{:else}
			<blockquote dir="auto">
				<MarkdownTokens
					id={`${id}-${tokenIdx}`}
					tokens={token.tokens}
					{onTaskClick}
					{onSourceClick}
					{searchQuery}
				/>
			</blockquote>
		{/if}
	{:else if token.type === 'list'}
		{#if token.ordered}
			<ol start={token.start || 1} dir="auto">
				{#each token.items as item, itemIdx}
					<li class="text-start">
						{#if item?.task}
							<input
								class=" translate-y-[1px] -translate-x-1"
								type="checkbox"
								checked={item.checked}
								onchange={(e) => {
									onTaskClick({
										id: id,
										token: token,
										tokenIdx: tokenIdx,
										item: item,
										itemIdx: itemIdx,
										checked: e.target.checked
									});
								}}
							/>
						{/if}

						<MarkdownTokens
							id={`${id}-${tokenIdx}-${itemIdx}`}
							tokens={item.tokens}
							top={token.loose}
							{onTaskClick}
							{onSourceClick}
							{searchQuery}
						/>
					</li>
				{/each}
			</ol>
		{:else}
			<ul dir="auto">
				{#each token.items as item, itemIdx}
					<li class="text-start">
						{#if item?.task}
							<input
								class=" translate-y-[1px] -translate-x-1"
								type="checkbox"
								checked={item.checked}
								onchange={(e) => {
									onTaskClick({
										id: id,
										token: token,
										tokenIdx: tokenIdx,
										item: item,
										itemIdx: itemIdx,
										checked: e.target.checked
									});
								}}
							/>
						{/if}

						<MarkdownTokens
							id={`${id}-${tokenIdx}-${itemIdx}`}
							tokens={item.tokens}
							top={token.loose}
							{onTaskClick}
							{onSourceClick}
							{searchQuery}
						/>
					</li>
				{/each}
			</ul>
		{/if}
	{:else if token.type === 'details'}
		<Collapsible
			title={token.summary}
			open={$settings?.expandDetails ?? false}
			attributes={token?.attributes}
			className="w-full space-y-1"
			dir="auto"
		>
			{#snippet content()}
																		<div class=" mb-1.5" >
					<MarkdownTokens
						id={`${id}-${tokenIdx}-d`}
						tokens={marked.lexer(token.text)}
						attributes={token?.attributes}
						{onTaskClick}
						{onSourceClick}
						{searchQuery}
					/>
				</div>
																	{/snippet}
		</Collapsible>
	{:else if token.type === 'html'}
		{@const html = DOMPurify.sanitize(token.text)}
		{#if html && html.includes('<video')}
			{@html html}
		{:else if token.text.includes(`<iframe src="${WEBUI_BASE_URL}/api/v1/files/`)}
			{@html `${token.text}`}
		{:else if token.text.includes(`<source_id`)}
			<Source {id} {token} onClick={onSourceClick} />
		{:else}
			{token.text}
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
	{:else if token.type === 'paragraph'}
		<p dir="auto">
			<MarkdownInlineTokens
				id={`${id}-${tokenIdx}-p`}
				tokens={token.tokens ?? []}
				{onSourceClick}
				{searchQuery}
			/>
		</p>
	{:else if token.type === 'text'}
		{#if top}
			<p>
				{#if token.tokens}
					<MarkdownInlineTokens
						id={`${id}-${tokenIdx}-t`}
						tokens={token.tokens}
						{onSourceClick}
						{searchQuery}
					/>
				{:else}
					{unescapeHtml(token.text)}
				{/if}
			</p>
		{:else if token.tokens}
			<MarkdownInlineTokens
				id={`${id}-${tokenIdx}-p`}
				tokens={token.tokens ?? []}
				{onSourceClick}
				{searchQuery}
			/>
		{:else}
			{unescapeHtml(token.text)}
		{/if}
	{:else if token.type === 'inlineKatex'}
		{#if token.text}
			<KatexRenderer content={token.text} displayMode={token?.displayMode ?? false} />
		{/if}
	{:else if token.type === 'blockKatex'}
		{#if token.text}
			<KatexRenderer content={token.text} displayMode={token?.displayMode ?? false} />
		{/if}
	{:else if token.type === 'space'}
		<div class="my-2"></div>
	{:else}
		{console.log('Unknown token', token)}
	{/if}
{/each}

<script lang="ts">
	import { run } from 'svelte/legacy';

	import { getContext } from 'svelte';
	import { get, type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import Modal from '$lib/components/common/Modal.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import { formatDate } from '$lib/utils';

	type ChatInfoSnapshot = {
		totalMessages: number;
		currentBranchMessages: number;
		branchCount: number;
		attachmentCount: number;
		totalCost: number;
		totalInputTokens: number;
		totalOutputTokens: number;
		totalReasoningTokens: number;
		uniqueModels: {
			id: string;
			label: string;
			icon?: string | null;
			messageCount: number;
		}[];
		createdAt: number | null;
		updatedAt: number | null;
	};

	interface Props {
		show?: boolean;
		stats?: ChatInfoSnapshot | null;
		chatTitle?: string;
	}

	let { show = $bindable(false), stats = null, chatTitle = '' }: Props = $props();

	const i18n: Writable<i18nType> = getContext('i18n');

	const formatNumber = (value?: number | null) => {
		if (value === undefined || value === null || Number.isNaN(value)) {
			return '0';
		}
		return value.toLocaleString();
	};

	const formatDateSafe = (value: number | null) => {
		if (!value) {
			return get(i18n).t('Not available');
		}
		return formatDate(value);
	};

	let branchCoverage =
		$derived(stats && stats.totalMessages > 0
			? Math.round((stats.currentBranchMessages / stats.totalMessages) * 100)
			: 0);

	const formatCurrency = (value?: number | null) => {
		if (!value || Number.isNaN(value)) {
			return '$0.0000';
		}
		return `$${value.toFixed(value >= 1 ? 4 : 6)}`;
	};

	let showAllModels = $state(false);

	let modelsCollapsible = $derived((stats?.uniqueModels?.length ?? 0) > 3);
	let visibleModels = $derived(stats?.uniqueModels ?? []);

	run(() => {
		if (!modelsCollapsible) {
			showAllModels = false;
		}
	});
</script>

<Modal bind:show size="sm" className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl">
	{#if stats}
		<div class="p-5 md:p-6 space-y-6">
			<div class="flex items-start justify-between gap-3">
				<div class="space-y-1 min-w-0">
					<p class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
						{$i18n.t('Chat Info')}
					</p>
					<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-50 line-clamp-2">
						{chatTitle || $i18n.t('Untitled Chat')}
					</h2>
					<p class="text-sm text-gray-500 dark:text-gray-400">
						{$i18n.t('Snapshot of this chat’s structure and activity')}
					</p>
				</div>
				<button
					class="p-1.5 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 transition"
					onclick={() => {
						show = false;
					}}
					aria-label={$i18n.t('Close')}
				>
					<XMark className="size-5" strokeWidth="2" />
				</button>
			</div>

			<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
				<div
					class="rounded-xl border border-gray-100 dark:border-gray-800 p-4 bg-gray-50/80 dark:bg-gray-850/60"
				>
					<p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
						{$i18n.t('Total messages')}
					</p>
					<p class="text-2xl font-semibold text-gray-900 dark:text-gray-50">
						{formatNumber(stats.totalMessages)}
					</p>
				</div>

				<div
					class="rounded-xl border border-gray-100 dark:border-gray-800 p-4 bg-gray-50/80 dark:bg-gray-850/60"
				>
					<p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
						{$i18n.t('Current branch')}
					</p>
					<div class="flex items-baseline gap-2">
						<p class="text-2xl font-semibold text-gray-900 dark:text-gray-50">
							{formatNumber(stats.currentBranchMessages)}
						</p>
						<span class="text-xs font-medium text-gray-500 dark:text-gray-400">
							{branchCoverage}%
						</span>
					</div>
					<p class="text-xs text-gray-500 dark:text-gray-400">
						{$i18n.t('Messages along the active path')}
					</p>
				</div>

				<div
					class="rounded-xl border border-gray-100 dark:border-gray-800 p-4 bg-gray-50/80 dark:bg-gray-850/60"
				>
					<p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
						{$i18n.t('Branches')}
					</p>
					<p class="text-2xl font-semibold text-gray-900 dark:text-gray-50">
						{formatNumber(stats.branchCount)}
					</p>
					<p class="text-xs text-gray-500 dark:text-gray-400">
						{$i18n.t('Leaf messages (ends of each path)')}
					</p>
				</div>

				<div
					class="rounded-xl border border-gray-100 dark:border-gray-800 p-4 bg-gray-50/80 dark:bg-gray-850/60"
				>
					<p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
						{$i18n.t('Attachments')}
					</p>
					<p class="text-2xl font-semibold text-gray-900 dark:text-gray-50">
						{formatNumber(stats.attachmentCount)}
					</p>
					<p class="text-xs text-gray-500 dark:text-gray-400">
						{$i18n.t('Files linked across all messages')}
					</p>
				</div>
			</div>

			<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
				<div
					class="rounded-xl border border-gray-100 dark:border-gray-800 p-4 bg-gray-50/80 dark:bg-gray-850/60"
				>
					<p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
						{$i18n.t('Total cost')}
					</p>
					<p class="text-2xl font-semibold text-gray-900 dark:text-gray-50">
						{formatCurrency(stats.totalCost)}
					</p>
				</div>

				<div
					class="rounded-xl border border-gray-100 dark:border-gray-800 p-4 bg-gray-50/80 dark:bg-gray-850/60"
				>
					<p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
						{$i18n.t('Total input tokens')}
					</p>
					<p class="text-2xl font-semibold text-gray-900 dark:text-gray-50">
						{formatNumber(stats.totalInputTokens)}
					</p>
				</div>

				<div
					class="rounded-xl border border-gray-100 dark:border-gray-800 p-4 bg-gray-50/80 dark:bg-gray-850/60"
				>
					<p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
						{$i18n.t('Total output tokens')}
					</p>
					<p class="text-2xl font-semibold text-gray-900 dark:text-gray-50">
						{formatNumber(stats.totalOutputTokens)}
					</p>
				</div>

				<div
					class="rounded-xl border border-gray-100 dark:border-gray-800 p-4 bg-gray-50/80 dark:bg-gray-850/60"
				>
					<p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
						{$i18n.t('Reasoning tokens')}
					</p>
					<p class="text-2xl font-semibold text-gray-900 dark:text-gray-50">
						{formatNumber(stats.totalReasoningTokens)}
					</p>
				</div>
			</div>

			<div class="space-y-2">
				<div class="flex items-center justify-between">
					<p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
						{$i18n.t('Unique models')}
					</p>
					<div class="flex items-center gap-2">
						<span class="text-xs font-medium text-gray-600 dark:text-gray-300">
							{formatNumber(stats.uniqueModels.length)}
							{$i18n.t('total')}
						</span>
						{#if modelsCollapsible}
							<button
								class="text-xs font-semibold text-gray-700 dark:text-gray-200 hover:text-gray-900 dark:hover:text-white transition"
								onclick={() => {
									showAllModels = !showAllModels;
								}}
							>
								{showAllModels ? $i18n.t('Show less') : $i18n.t('Show all')}
							</button>
						{/if}
					</div>
				</div>

				{#if stats.uniqueModels.length > 0}
					<div
						class={`relative flex flex-col gap-2 transition-all ${
							!showAllModels && modelsCollapsible ? 'max-h-[148px] overflow-hidden pr-1' : ''
						}`}
					>
						{#each visibleModels.sort((a, b) => b.messageCount - a.messageCount) as model (model.id)}
							<div
								class="flex items-center gap-3 px-3 py-2 rounded-2xl border border-gray-100 dark:border-gray-800 bg-white/70 dark:bg-gray-900/40"
							>
								{#if model.icon}
									<img
										src={model.icon}
										alt={`${model.label} icon`}
										class="size-8 rounded-full object-cover border border-gray-200 dark:border-gray-700"
										loading="lazy"
										decoding="async"
									/>
								{:else}
									<div
										class="size-8 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-xs font-semibold text-gray-600 dark:text-gray-200"
									>
										{(model.label || model.id || '?').slice(0, 1).toUpperCase()}
									</div>
								{/if}
								<div class="flex items-center gap-3 flex-1 min-w-0">
									<div class="flex flex-col leading-tight min-w-0">
										<span class="text-sm font-medium text-gray-900 dark:text-gray-100 line-clamp-1">
											{model.label}
										</span>
										{#if model.id && model.id !== model.label}
											<span class="text-xs text-gray-500 dark:text-gray-400 line-clamp-1">
												{model.id}
											</span>
										{/if}
									</div>
									<span
										class="text-xs font-semibold text-gray-600 dark:text-gray-300 whitespace-nowrap ml-auto text-right"
									>
										{formatNumber(model.messageCount)}
										{$i18n.t('messages')}
									</span>
								</div>
							</div>
						{/each}

						{#if !showAllModels && modelsCollapsible}
							<div
								class="pointer-events-none absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-white via-white/80 to-transparent dark:from-gray-900 dark:via-gray-900/80"
							></div>
						{/if}
					</div>
				{:else}
					<p class="text-sm text-gray-500 dark:text-gray-400">
						{$i18n.t('No models have been used in this chat yet.')}
					</p>
				{/if}
			</div>

			<div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
				<div class="space-y-1">
					<p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
						{$i18n.t('Created')}
					</p>
					<p class="font-medium text-gray-900 dark:text-gray-100">
						{formatDateSafe(stats.createdAt)}
					</p>
				</div>
				<div class="space-y-1">
					<p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
						{$i18n.t('Last updated')}
					</p>
					<p class="font-medium text-gray-900 dark:text-gray-100">
						{formatDateSafe(stats.updatedAt)}
					</p>
				</div>
			</div>
		</div>
	{:else}
		<div class="p-6 text-sm text-gray-500 dark:text-gray-400">
			{$i18n.t('Chat info is unavailable until the conversation loads.')}
		</div>
	{/if}
</Modal>

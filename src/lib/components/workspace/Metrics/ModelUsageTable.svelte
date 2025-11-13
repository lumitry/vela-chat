<script lang="ts">
	import { getContext } from 'svelte';
	import { formatSmartCurrency } from '$lib/utils/currency';
	import { models as modelsStore } from '$lib/stores';
	import Spinner from '$lib/components/common/Spinner.svelte';

	const i18n = getContext('i18n');

	export let models: Array<{
		model_id: string;
		model_name: string;
		spend: number;
		input_tokens: number;
		output_tokens: number;
		total_tokens: number;
		message_count: number;
	}> = [];
	export let loading: boolean = false;

	type SortColumn = 'model_name' | 'spend' | 'input_tokens' | 'output_tokens' | 'total_tokens' | 'message_count';
	type SortDirection = 'asc' | 'desc';

	let sortColumn: SortColumn = 'total_tokens';
	let sortDirection: SortDirection = 'desc';

	$: sortedModels = [...models].sort((a, b) => {
		let aVal: number | string;
		let bVal: number | string;

		switch (sortColumn) {
			case 'model_name':
				aVal = a.model_name.toLowerCase();
				bVal = b.model_name.toLowerCase();
				break;
			case 'spend':
				aVal = a.spend;
				bVal = b.spend;
				break;
			case 'input_tokens':
				aVal = a.input_tokens;
				bVal = b.input_tokens;
				break;
			case 'output_tokens':
				aVal = a.output_tokens;
				bVal = b.output_tokens;
				break;
			case 'total_tokens':
				aVal = a.total_tokens;
				bVal = b.total_tokens;
				break;
			case 'message_count':
				aVal = a.message_count;
				bVal = b.message_count;
				break;
		}

		if (typeof aVal === 'string' && typeof bVal === 'string') {
			return sortDirection === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
		} else {
			return sortDirection === 'asc'
				? (aVal as number) - (bVal as number)
				: (bVal as number) - (aVal as number);
		}
	});

	const handleSort = (column: SortColumn) => {
		if (sortColumn === column) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortColumn = column;
			sortDirection = 'desc';
		}
	};

	const formatNumber = (num: number): string => {
		return new Intl.NumberFormat().format(num);
	};

	const formatCurrency = (num: number): string => {
		return formatSmartCurrency(num);
	};

	// Get model icon URL from models store
	const getModelIcon = (modelId: string): string => {
		const model = $modelsStore?.find((m: any) => m.id === modelId);
		return model?.info?.meta?.profile_image_url || '/static/favicon.png';
	};
</script>

<div class="bg-white dark:bg-gray-800 rounded-xl p-4 overflow-x-auto">
	{#if loading}
		<div class="flex items-center justify-center h-64">
			<Spinner />
		</div>
	{:else}
		<table class="w-full">
			<thead>
				<tr class="border-b border-gray-200 dark:border-gray-700">
					<th
						class="text-left py-3 px-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition text-sm font-semibold"
						on:click={() => handleSort('model_name')}
					>
						<div class="flex items-center gap-1.5">
							<span>{$i18n.t('Model')}</span>
							{#if sortColumn === 'model_name'}
								<span class="text-xs opacity-70">{sortDirection === 'asc' ? '↑' : '↓'}</span>
							{/if}
						</div>
					</th>
					<th
						class="text-right py-3 px-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition text-sm font-semibold"
						on:click={() => handleSort('spend')}
					>
						<div class="flex items-center justify-end gap-1.5">
							<span>{$i18n.t('Spend')}</span>
							{#if sortColumn === 'spend'}
								<span class="text-xs opacity-70">{sortDirection === 'asc' ? '↑' : '↓'}</span>
							{/if}
						</div>
					</th>
					<th
						class="text-right py-3 px-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition text-sm font-semibold"
						on:click={() => handleSort('input_tokens')}
					>
						<div class="flex items-center justify-end gap-1.5">
							<span>{$i18n.t('Input Tokens')}</span>
							{#if sortColumn === 'input_tokens'}
								<span class="text-xs opacity-70">{sortDirection === 'asc' ? '↑' : '↓'}</span>
							{/if}
						</div>
					</th>
					<th
						class="text-right py-3 px-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition text-sm font-semibold"
						on:click={() => handleSort('output_tokens')}
					>
						<div class="flex items-center justify-end gap-1.5">
							<span>{$i18n.t('Output Tokens')}</span>
							{#if sortColumn === 'output_tokens'}
								<span class="text-xs opacity-70">{sortDirection === 'asc' ? '↑' : '↓'}</span>
							{/if}
						</div>
					</th>
					<th
						class="text-right py-3 px-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition text-sm font-semibold"
						on:click={() => handleSort('total_tokens')}
					>
						<div class="flex items-center justify-end gap-1.5">
							<span>{$i18n.t('Total Tokens')}</span>
							{#if sortColumn === 'total_tokens'}
								<span class="text-xs opacity-70">{sortDirection === 'asc' ? '↑' : '↓'}</span>
							{/if}
						</div>
					</th>
					<th
						class="text-right py-3 px-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition text-sm font-semibold"
						on:click={() => handleSort('message_count')}
					>
						<div class="flex items-center justify-end gap-1.5">
							<span>{$i18n.t('Messages')}</span>
							{#if sortColumn === 'message_count'}
								<span class="text-xs opacity-70">{sortDirection === 'asc' ? '↑' : '↓'}</span>
							{/if}
						</div>
					</th>
				</tr>
			</thead>
			<tbody>
				{#each sortedModels as model}
					<tr
						class="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition"
					>
						<td class="py-3 px-4 font-medium text-sm">
							<div class="flex items-center gap-2">
								<img
									src={getModelIcon(model.model_id)}
									alt={model.model_name}
									class="w-6 h-6 rounded-full object-cover"
								/>
								<span>{model.model_name}</span>
							</div>
						</td>
						<td class="py-3 px-4 text-right text-sm tabular-nums">{formatCurrency(model.spend)}</td>
						<td class="py-3 px-4 text-right text-sm tabular-nums"
							>{formatNumber(model.input_tokens)}</td
						>
						<td class="py-3 px-4 text-right text-sm tabular-nums"
							>{formatNumber(model.output_tokens)}</td
						>
						<td class="py-3 px-4 text-right text-sm font-semibold tabular-nums"
							>{formatNumber(model.total_tokens)}</td
						>
						<td class="py-3 px-4 text-right text-sm tabular-nums"
							>{formatNumber(model.message_count)}</td
						>
					</tr>
				{/each}
			</tbody>
		</table>
		{#if models.length === 0}
			<div class="flex flex-col items-center justify-center py-12 text-gray-500 text-sm">
				<div>No models found for this date range</div>
				<div class="text-xs mt-1 opacity-70">
					Try selecting a different time period or model type
				</div>
			</div>
		{/if}
	{/if}
</div>

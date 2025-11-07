<script lang="ts">
	import { getContext } from 'svelte';

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

	type SortColumn = 'model_name' | 'spend' | 'input_tokens' | 'output_tokens' | 'total_tokens';
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
		}

		if (typeof aVal === 'string' && typeof bVal === 'string') {
			return sortDirection === 'asc'
				? aVal.localeCompare(bVal)
				: bVal.localeCompare(aVal);
		} else {
			return sortDirection === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
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
		return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 8 }).format(num);
	};
</script>

<div class="bg-white dark:bg-gray-800 rounded-xl p-4 overflow-x-auto">
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
			</tr>
		</thead>
		<tbody>
			{#each sortedModels as model}
				<tr class="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition">
					<td class="py-3 px-4 font-medium text-sm">{model.model_name}</td>
					<td class="py-3 px-4 text-right text-sm tabular-nums">{formatCurrency(model.spend)}</td>
					<td class="py-3 px-4 text-right text-sm tabular-nums">{formatNumber(model.input_tokens)}</td>
					<td class="py-3 px-4 text-right text-sm tabular-nums">{formatNumber(model.output_tokens)}</td>
					<td class="py-3 px-4 text-right text-sm font-semibold tabular-nums">{formatNumber(model.total_tokens)}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>


<script lang="ts">
	import { getContext } from 'svelte';
	import { createEventDispatcher } from 'svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let startDate: string = '';
	export let endDate: string = '';

	type Preset = '7d' | '30d' | '90d' | 'custom';

	let selectedPreset: Preset = '30d';
	let showCustom = false;

	// Calculate default dates (last 30 days)
	$: if (!startDate || !endDate) {
		const end = new Date();
		const start = new Date();
		start.setDate(start.getDate() - 30);
		startDate = start.toISOString().split('T')[0];
		endDate = end.toISOString().split('T')[0];
		dispatch('change', { startDate, endDate });
	}

	const setPreset = (preset: Preset) => {
		selectedPreset = preset;
		showCustom = preset === 'custom';

		if (preset !== 'custom') {
			const end = new Date();
			const start = new Date();
			if (preset === '7d') {
				start.setDate(start.getDate() - 7);
			} else if (preset === '30d') {
				start.setDate(start.getDate() - 30);
			} else if (preset === '90d') {
				start.setDate(start.getDate() - 90);
			}
			startDate = start.toISOString().split('T')[0];
			endDate = end.toISOString().split('T')[0];
			dispatch('change', { startDate, endDate });
		}
	};

	const handleCustomChange = () => {
		if (showCustom && startDate && endDate) {
			// Validate dates
			if (new Date(startDate) > new Date(endDate)) {
				// Swap dates if start > end
				const temp = startDate;
				startDate = endDate;
				endDate = temp;
			}
			dispatch('change', { startDate, endDate });
		}
	};

	// Get today's date in YYYY-MM-DD format for max attribute
	const today = new Date().toISOString().split('T')[0];
</script>

<div class="flex flex-col gap-2">
	<label class="text-xs font-semibold text-gray-700 dark:text-gray-300">{$i18n.t('Date Range')}</label>
	<div class="flex items-center gap-2 flex-wrap">
		<button
			class="px-3 py-1.5 rounded-xl text-sm font-medium transition {selectedPreset === '7d'
				? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
				: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'}"
			on:click={() => setPreset('7d')}
		>
			{$i18n.t('Last 7 days')}
		</button>
		<button
			class="px-3 py-1.5 rounded-xl text-sm font-medium transition {selectedPreset === '30d'
				? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
				: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'}"
			on:click={() => setPreset('30d')}
		>
			{$i18n.t('Last 30 days')}
		</button>
		<button
			class="px-3 py-1.5 rounded-xl text-sm font-medium transition {selectedPreset === '90d'
				? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
				: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'}"
			on:click={() => setPreset('90d')}
		>
			{$i18n.t('Last 90 days')}
		</button>
		<button
			class="px-3 py-1.5 rounded-xl text-sm font-medium transition {selectedPreset === 'custom'
				? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
				: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'}"
			on:click={() => setPreset('custom')}
		>
			{$i18n.t('Custom')}
		</button>
		{#if showCustom}
			<label class="text-sm text-gray-600 dark:text-gray-400 flex items-center gap-1">
				<span>{$i18n.t('Start')}:</span>
				<input
					type="date"
					bind:value={startDate}
					max={endDate || today}
					class="px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm"
					on:change={handleCustomChange}
				/>
			</label>
			<label class="text-sm text-gray-600 dark:text-gray-400 flex items-center gap-1">
				<span>{$i18n.t('End')}:</span>
				<input
					type="date"
					bind:value={endDate}
					min={startDate}
					max={today}
					class="px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm"
					on:change={handleCustomChange}
				/>
			</label>
		{/if}
	</div>
</div>


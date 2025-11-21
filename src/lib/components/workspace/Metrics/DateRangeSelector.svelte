<script lang="ts">
	import { run } from 'svelte/legacy';

	import { getContext } from 'svelte';
	import { createEventDispatcher } from 'svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	interface Props {
		startDate?: string;
		endDate?: string;
	}

	let { startDate = $bindable(''), endDate = $bindable('') }: Props = $props();

	type Preset = '7d' | '30d' | '90d' | 'custom';

	// Local copies for the inputs (can be modified)
	let localStartDate: string = $state('');
	let localEndDate: string = $state('');
	let lastPropStartDate: string = $state('');
	let lastPropEndDate: string = $state('');

	let selectedPreset: Preset = $state('30d');
	let showCustom = $state(false);
	let userSelectedCustom = $state(false); // Track if user explicitly selected custom

	// Sync local dates with props ONLY when props actually change (not when local changes)
	run(() => {
		if (startDate !== lastPropStartDate || endDate !== lastPropEndDate) {
			// Props changed externally, update local dates
			localStartDate = startDate;
			localEndDate = endDate;
			lastPropStartDate = startDate;
			lastPropEndDate = endDate;
		}
	});

	// Detect which preset matches the current date range
	const detectPreset = (start: string, end: string): Preset => {
		if (!start || !end) return '30d';
		
		const startDate = new Date(start);
		const endDate = new Date(end);
		const today = new Date();
		today.setHours(0, 0, 0, 0);
		endDate.setHours(0, 0, 0, 0);
		startDate.setHours(0, 0, 0, 0);
		
		// Check if end date is today (or very close - within 1 day)
		const daysDiffFromToday = Math.floor((today.getTime() - endDate.getTime()) / (1000 * 60 * 60 * 24));
		if (Math.abs(daysDiffFromToday) > 1) {
			return 'custom';
		}
		
		// Calculate days between start and end
		const daysDiff = Math.floor((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
		
		// Check if it matches a preset (allow 1 day tolerance for timezone/rounding issues)
		if (daysDiff >= 6 && daysDiff <= 8) {
			return '7d';
		} else if (daysDiff >= 29 && daysDiff <= 31) {
			return '30d';
		} else if (daysDiff >= 89 && daysDiff <= 91) {
			return '90d';
		}
		
		return 'custom';
	};

	// Update preset when dates change (but don't override if user explicitly selected custom)
	run(() => {
		if (startDate && endDate && !userSelectedCustom) {
			const detectedPreset = detectPreset(startDate, endDate);
			selectedPreset = detectedPreset;
			showCustom = detectedPreset === 'custom';
		}
	});

	// Calculate default dates (last 30 days)
	run(() => {
		if (!startDate || !endDate) {
			const end = new Date();
			const start = new Date();
			start.setDate(start.getDate() - 30);
			const newStartDate = start.toISOString().split('T')[0];
			const newEndDate = end.toISOString().split('T')[0];
			startDate = newStartDate;
			endDate = newEndDate;
			// Also update local dates and tracked prop values
			localStartDate = newStartDate;
			localEndDate = newEndDate;
			lastPropStartDate = newStartDate;
			lastPropEndDate = newEndDate;
			dispatch('change', { startDate: newStartDate, endDate: newEndDate });
		}
	});

	const setPreset = (preset: Preset) => {
		selectedPreset = preset;
		showCustom = preset === 'custom';
		
		// Track if user explicitly selected custom
		userSelectedCustom = preset === 'custom';

		if (preset !== 'custom') {
			// User selected a preset, so allow auto-detection again
			userSelectedCustom = false;
			const end = new Date();
			const start = new Date();
			if (preset === '7d') {
				start.setDate(start.getDate() - 7);
			} else if (preset === '30d') {
				start.setDate(start.getDate() - 30);
			} else if (preset === '90d') {
				start.setDate(start.getDate() - 90);
			}
			const newStartDate = start.toISOString().split('T')[0];
			const newEndDate = end.toISOString().split('T')[0];
			startDate = newStartDate;
			endDate = newEndDate;
			// Also update local dates and tracked prop values
			localStartDate = newStartDate;
			localEndDate = newEndDate;
			lastPropStartDate = newStartDate;
			lastPropEndDate = newEndDate;
			dispatch('change', { startDate: newStartDate, endDate: newEndDate });
		} else {
			// When switching to custom, ensure local dates are synced
			localStartDate = startDate;
			localEndDate = endDate;
			lastPropStartDate = startDate;
			lastPropEndDate = endDate;
		}
	};

	const handleCustomChange = () => {
		if (showCustom && localStartDate && localEndDate) {
			// Validate dates
			let finalStartDate = localStartDate;
			let finalEndDate = localEndDate;
			
			if (new Date(localStartDate) > new Date(localEndDate)) {
				// Swap dates if start > end
				finalStartDate = localEndDate;
				finalEndDate = localStartDate;
				// Update local values
				localStartDate = finalStartDate;
				localEndDate = finalEndDate;
			}
			
			// Update tracked prop values so reactive statement doesn't reset
			lastPropStartDate = finalStartDate;
			lastPropEndDate = finalEndDate;
			
			dispatch('change', { startDate: finalStartDate, endDate: finalEndDate });
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
			onclick={() => setPreset('7d')}
		>
			{$i18n.t('Last 7 days')}
		</button>
		<button
			class="px-3 py-1.5 rounded-xl text-sm font-medium transition {selectedPreset === '30d'
				? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
				: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'}"
			onclick={() => setPreset('30d')}
		>
			{$i18n.t('Last 30 days')}
		</button>
		<button
			class="px-3 py-1.5 rounded-xl text-sm font-medium transition {selectedPreset === '90d'
				? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
				: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'}"
			onclick={() => setPreset('90d')}
		>
			{$i18n.t('Last 90 days')}
		</button>
		<button
			class="px-3 py-1.5 rounded-xl text-sm font-medium transition {selectedPreset === 'custom'
				? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
				: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'}"
			onclick={() => setPreset('custom')}
		>
			{$i18n.t('Custom')}
		</button>
		{#if showCustom}
			<label class="text-sm text-gray-600 dark:text-gray-400 flex items-center gap-1">
				<span>{$i18n.t('Start')}:</span>
				<input
					type="date"
					bind:value={localStartDate}
					max={localEndDate || today}
					class="px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm"
					onchange={handleCustomChange}
				/>
			</label>
			<label class="text-sm text-gray-600 dark:text-gray-400 flex items-center gap-1">
				<span>{$i18n.t('End')}:</span>
				<input
					type="date"
					bind:value={localEndDate}
					min={localStartDate}
					max={today}
					class="px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm"
					onchange={handleCustomChange}
				/>
			</label>
		{/if}
	</div>
</div>


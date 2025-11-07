<script lang="ts">
	import { getContext } from 'svelte';
	import { createEventDispatcher } from 'svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let modelType: 'local' | 'external' | 'both' = 'both';

	const setModelType = (type: 'local' | 'external' | 'both') => {
		modelType = type;
		dispatch('change', type);
	};
</script>

<div class="flex items-center gap-2">
	<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{$i18n.t('Model Type')}:</span>
	<button
		class="px-3 py-1.5 rounded-xl text-sm font-medium transition {modelType === 'local'
			? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
			: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'}"
		on:click={() => setModelType('local')}
	>
		{$i18n.t('Local')}
	</button>
	<button
		class="px-3 py-1.5 rounded-xl text-sm font-medium transition {modelType === 'external'
			? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
			: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'}"
		on:click={() => setModelType('external')}
	>
		{$i18n.t('External')}
	</button>
	<button
		class="px-3 py-1.5 rounded-xl text-sm font-medium transition {modelType === 'both'
			? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
			: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'}"
		on:click={() => setModelType('both')}
	>
		{$i18n.t('Both')}
	</button>
</div>


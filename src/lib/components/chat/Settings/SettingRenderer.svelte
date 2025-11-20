<script lang="ts">
	import SettingRow from './SettingRow.svelte';
	import SwitchSetting from './SwitchSetting.svelte';
	import SelectSetting from './SelectSetting.svelte';
	import ButtonSetting from './ButtonSetting.svelte';
	// SettingConfig type is defined inline to avoid circular dependency
	type SettingConfig =
		| {
				type: 'switch';
				id: string;
				label: string;
				labelSuffix?: string;
				keywords: string[];
				get: () => boolean;
				set: (value: boolean) => boolean | Promise<boolean>;
				requiresAdmin?: boolean;
				dependsOn?: (context: any) => boolean;
		  }
		| {
				type: 'select';
				id: string;
				label: string;
				keywords: string[];
				get: () => string;
				set: (value: string) => void | Promise<void>;
				options: Array<{ value: string; label: string }>;
				requiresAdmin?: boolean;
				dependsOn?: (context: any) => boolean;
		  }
		| {
				type: 'button';
				id: string;
				label: string;
				keywords: string[];
				getValue: () => any;
				getLabel: (value: any) => string;
				onClick: () => void | Promise<void>;
				requiresAdmin?: boolean;
				dependsOn?: (context: any) => boolean;
		  }
		| {
				type: 'custom';
				id: string;
				label?: string;
				keywords: string[];
				component: any;
				getProps?: () => Record<string, any>;
				requiresAdmin?: boolean;
				dependsOn?: (context: any) => boolean;
		  };

	export let setting: SettingConfig;
	export let i18n: any;
	export let context: any;

	// For chatBackgroundImage, track the value reactively from context to force re-render
	let bgImageKey = setting.id;
	let customProps: Record<string, any> = {};

	// Explicitly depend on context.backgroundImageUrl for chatBackgroundImage to ensure reactivity
	$: contextBackgroundImageUrl = context?.backgroundImageUrl;

	$: if (setting.type === 'custom' && setting.id === 'chatBackgroundImage') {
		// Use contextBackgroundImageUrl to make it reactive - this ensures the block re-runs when it changes
		bgImageKey = contextBackgroundImageUrl ? 'has-image' : 'no-image';
		// Update props reactively - the reactive block will re-run when contextBackgroundImageUrl changes
		if (setting.getProps) {
			customProps = setting.getProps();
		}
	} else {
		bgImageKey = setting.id;
		// Update props reactively for other custom components
		if (setting.type === 'custom' && setting.getProps) {
			customProps = setting.getProps();
		}
	}
</script>

{#if setting.type === 'switch'}
	<SettingRow
		label={setting.labelSuffix
			? `${i18n.t(setting.label)} (${i18n.t(setting.labelSuffix)})`
			: i18n.t(setting.label)}
	>
		<SwitchSetting get={setting.get} set={setting.set} />
	</SettingRow>
{:else if setting.type === 'select'}
	<SettingRow label={i18n.t(setting.label)}>
		<SelectSetting
			value={setting.get()}
			options={setting.options.map((opt) => ({ value: opt.value, label: i18n.t(opt.label) }))}
			onChange={setting.set}
		/>
	</SettingRow>
{:else if setting.type === 'button'}
	<SettingRow label={i18n.t(setting.label)}>
		<ButtonSetting
			getValue={setting.getValue}
			getLabel={setting.getLabel}
			onClick={setting.onClick}
		/>
	</SettingRow>
{:else if setting.type === 'custom'}
	{#if setting.getProps}
		<svelte:component this={setting.component} key={bgImageKey} {...customProps} />
	{:else}
		<svelte:component this={setting.component} />
	{/if}
{/if}

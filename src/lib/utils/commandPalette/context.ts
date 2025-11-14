import { derived, get, writable } from 'svelte/store';
import { page } from '$app/stores';
import { chatId, config, settings, user } from '$lib/stores';
import type { CommandContext } from './types';

type CommandContextAugmenter = (context: CommandContext) => Partial<CommandContext> | void;

const augmenters = new Set<CommandContextAugmenter>();
const contextInvalidator = writable(0);

const KNOWN_KEYS: Array<keyof CommandContext> = [
	'currentChatId',
	'currentRoute',
	'user',
	'settings',
	'config',
	'additional'
];

const commandContextInternal = derived(
	[chatId, user, settings, config, page, contextInvalidator],
	([$chatId, $user, $settings, $config, $page, _invalidate]) => {
		void _invalidate;
		const base: CommandContext = {
			currentChatId: $chatId ? $chatId : null,
			currentRoute: $page?.url?.pathname ?? '/',
			user: $user,
			settings: $settings,
			config: $config,
			additional: {}
		};

		return applyAugmenters(base);
	}
);

export const commandContextStore = derived(commandContextInternal, ($context) => $context);

export function getCommandContext(): CommandContext {
	return get(commandContextStore);
}

export function registerCommandContextAugmenter(
	augmenter: CommandContextAugmenter
): () => void {
	augmenters.add(augmenter);
	invalidateCommandContext();

	return () => {
		augmenters.delete(augmenter);
		invalidateCommandContext();
	};
}

function invalidateCommandContext() {
	contextInvalidator.update((value) => value + 1);
}

function applyAugmenters(base: CommandContext): CommandContext {
	let context = base;

	for (const augmenter of augmenters) {
		const patch = augmenter(context);
		if (!patch) continue;
		context = mergeContext(context, patch);
	}

	return context;
}

function mergeContext(target: CommandContext, patch: Partial<CommandContext>): CommandContext {
	const next: CommandContext = {
		...target,
		additional: { ...(target.additional ?? {}) }
	};

	for (const key of KNOWN_KEYS) {
		if (key in patch && patch[key] !== undefined) {
			// eslint-disable-next-line @typescript-eslint/no-explicit-any
			(next as any)[key] = patch[key];
		}
	}

	for (const [key, value] of Object.entries(patch)) {
		if (!KNOWN_KEYS.includes(key as keyof CommandContext)) {
			next.additional = {
				...(next.additional ?? {}),
				[key]: value
			};
		}
	}

	return next;
}

export function withAdditionalContext(values: Record<string, unknown>): () => void {
	return registerCommandContextAugmenter((ctx) => ({
		additional: {
			...(ctx.additional ?? {}),
			...values
		}
	}));
}


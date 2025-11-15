import type { ComponentType } from 'svelte';
import { isIconLoader, type CommandIconSource } from './types';

const iconCache = new Map<CommandIconSource, ComponentType>();

function extractComponent(value: unknown): ComponentType | null {
	if (!value) return null;

	if (typeof value === 'function') {
		return value as ComponentType;
	}

	if (
		typeof value === 'object' &&
		value !== null &&
		'default' in value
	) {
		return extractComponent((value as Record<string, unknown>).default);
	}

	return null;
}

export async function loadIcon(
	source?: CommandIconSource
): Promise<ComponentType | null> {
	if (!source) return null;

	if (iconCache.has(source)) {
		return iconCache.get(source) ?? null;
	}

	const directComponent = extractComponent(source);
	if (directComponent) {
		iconCache.set(source, directComponent);
		return directComponent;
	}

	if (isIconLoader(source)) {
		const resolved = await source();
		const component = extractComponent(resolved);
		if (component) {
			iconCache.set(source, component);
			return component;
		}
		return null;
	}

	return null;
}

export async function preloadIcons(sources: CommandIconSource[]): Promise<void> {
	for (const source of sources) {
		if (!iconCache.has(source)) {
			try {
				await loadIcon(source);
			} catch (error) {
				console.error('Failed to preload icon', error);
			}
		}
	}
}


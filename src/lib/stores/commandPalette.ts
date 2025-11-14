import type { ComponentType } from 'svelte';
import { writable } from 'svelte/store';
import type { SubmenuCommand } from '$lib/utils/commandPalette/types';

export interface CommandPaletteSubmenuState {
	id: string;
	title?: string;
	command?: SubmenuCommand;
	component?: ComponentType;
	props?: Record<string, unknown>;
}

export const isCommandPaletteOpen = writable(false);
export const commandPaletteQuery = writable('');
export const commandPaletteSubmenu = writable<CommandPaletteSubmenuState[]>([]);


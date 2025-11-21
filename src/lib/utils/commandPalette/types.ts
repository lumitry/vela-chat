import type { Component, ComponentType } from 'svelte';
import type { FuseResultMatch } from 'fuse.js';

export type CommandType = 'action' | 'navigation' | 'setting' | 'submenu';

export type CommandIconLoader = () => Promise<{
	default: ComponentType | Component<any, any, any>;
}>;
export type CommandComponentLoader = () => Promise<{
	default: ComponentType | Component<any, any, any>;
}>;

export type CommandIconSource = CommandIconLoader | ComponentType | Component<any, any, any>;
export type CommandComponentSource =
	| CommandComponentLoader
	| ComponentType
	| Component<any, any, any>;

export interface CommandContext {
	currentChatId: string | null;
	currentRoute: string;
	user?: any;
	settings?: any;
	config?: any;
	additional?: Record<string, unknown>;
}

export type CommandCondition = (context: CommandContext) => boolean;

export interface BaseCommand {
	id: string;
	label: string;
	description?: string;
	keywords?: string[];
	shortcut?: string;
	icon?: CommandIconSource;
	group?: string;
	priority?: number;
	requiresAdmin?: boolean;
	condition?: CommandCondition;
	disabled?: CommandCondition;
	metadata?: Record<string, unknown>;
}

export interface ActionCommand extends BaseCommand {
	type: 'action';
	execute: (context?: CommandContext) => void | Promise<void>;
}

export interface NavigationCommand extends BaseCommand {
	type: 'navigation';
	route: string;
	execute?: (context?: CommandContext) => void | Promise<void>;
}

export interface SettingCommand extends BaseCommand {
	type: 'setting';
	settingId: string;
	settingType: 'switch' | 'select' | 'button' | 'custom';
	execute: (context?: CommandContext) => void | Promise<void>;
	getValue?: (context?: CommandContext) => unknown;
	options?: Array<{ value: string; label: string }>;
}

export interface SubmenuItem {
	id: string;
	label: string;
	description?: string;
	icon?: CommandIconSource;
	execute: (context?: CommandContext) => void | Promise<void>;
	metadata?: Record<string, unknown>;
}

export interface SubmenuCommand extends BaseCommand {
	type: 'submenu';
	// New: get items to render as a list
	getSubmenuItems?: (
		query: string,
		context?: CommandContext
	) => Promise<SubmenuItem[]> | SubmenuItem[];
	// Legacy: get component (for complex submenus like rename)
	getSubmenuComponent?: () => CommandComponentSource | Promise<unknown>;
	getSubmenuProps?: (context?: CommandContext) => Record<string, unknown>;
	onClose?: (context?: CommandContext) => void | Promise<void>;
}

export type Command = ActionCommand | NavigationCommand | SettingCommand | SubmenuCommand;

export interface CommandSearchOptions {
	context?: CommandContext;
	limit?: number;
	includeHidden?: boolean;
	includeDisabled?: boolean;
}

export interface CommandSearchResult {
	command: Command;
	score: number | null;
	matches?: readonly FuseResultMatch[];
}

export interface CommandRegistrationOptions {
	replace?: boolean;
}

export interface CommandExecutionResult {
	command: Command;
	executed: boolean;
	error?: unknown;
}

export function isIconLoader(icon?: CommandIconSource): icon is CommandIconLoader {
	return typeof icon === 'function' && !(icon as unknown as { prototype?: unknown })?.prototype;
}

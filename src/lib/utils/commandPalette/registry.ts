import Fuse from 'fuse.js';
import { derived, get, writable } from 'svelte/store';
import { commandContextStore, getCommandContext } from './context';
import type {
	Command,
	CommandContext,
	CommandExecutionResult,
	CommandSearchOptions,
	CommandSearchResult,
	CommandRegistrationOptions
} from './types';

const commandsStore = writable<Command[]>([]);
export const commandsReadable = derived(commandsStore, ($commands) => $commands);

let fuseInstance = createFuse([]);

commandsStore.subscribe((commands) => {
	fuseInstance = createFuse(commands);
});

export function registerCommand(command: Command, options: CommandRegistrationOptions = {}): void {
	if (!command?.id) {
		throw new Error('Command must have an id.');
	}

	commandsStore.update((current) => {
		const idx = current.findIndex((item) => item.id === command.id);

		if (idx !== -1) {
			if (options.replace ?? true) {
				const next = [...current];
				next[idx] = command;
				return next;
			}
			return current;
		}

		return [...current, command];
	});
}

export function registerCommands(commands: Command[], options?: CommandRegistrationOptions): void {
	for (const command of commands) {
		registerCommand(command, options);
	}
}

export function unregisterCommand(commandId: string): void {
	commandsStore.update((current) => current.filter((command) => command.id !== commandId));
}

export function clearCommands(): void {
	commandsStore.set([]);
}

export function getCommandById(commandId: string): Command | undefined {
	return get(commandsReadable).find((command) => command.id === commandId);
}

export function getAvailableCommands(
	context: CommandContext = getCommandContext(),
	includeHidden = false,
	includeDisabled = false
): Command[] {
	const commands = get(commandsReadable);
	return filterCommands(commands, context, includeHidden, includeDisabled);
}

export function searchCommands(
	query: string,
	{ context = getCommandContext(), limit = 30, includeHidden = false, includeDisabled = false }: CommandSearchOptions = {}
): CommandSearchResult[] {
	const availableCommands = filterCommands(
		get(commandsReadable),
		context,
		includeHidden,
		includeDisabled
	);

	if (!query?.trim()) {
		const sorted = sortCommandsByPriority(availableCommands);
		return sorted.slice(0, limit).map((command) => ({
			command,
			score: null
		}));
	}

	const availableSet = new Set(availableCommands.map((command) => command.id));
	const fuseResults = fuseInstance.search(query);

	const filtered = fuseResults.filter((result) => availableSet.has(result.item.id)).slice(0, limit);

	return filtered.map((result) => ({
		command: result.item,
		score: result.score ?? null,
		matches: result.matches
	}));
}

export async function executeCommand(
	commandOrId: string | Command,
	context: CommandContext = get(commandContextStore)
): Promise<CommandExecutionResult> {
	const command = typeof commandOrId === 'string' ? getCommandById(commandOrId) : commandOrId;

	if (!command) {
		return {
			command: commandOrId as Command,
			executed: false,
			error: new Error(`Command not found: ${commandOrId}`)
		};
	}

	if (!isCommandVisible(command, context) || isCommandDisabled(command, context)) {
		return { command, executed: false };
	}

	try {
		if ('execute' in command && typeof command.execute === 'function') {
			await command.execute(context);
		}

		return { command, executed: true };
	} catch (error) {
		return { command, executed: false, error };
	}
}

function filterCommands(
	commands: Command[],
	context: CommandContext,
	includeHidden: boolean,
	includeDisabled: boolean
): Command[] {
	return commands.filter((command) => {
		if (!includeHidden && !isCommandVisible(command, context)) {
			return false;
		}

		if (!includeDisabled && isCommandDisabled(command, context)) {
			return false;
		}

		return true;
	});
}

function isCommandVisible(command: Command, context: CommandContext): boolean {
	if (command.requiresAdmin && context.user?.role !== 'admin') {
		return false;
	}

	if (typeof command.condition === 'function' && !command.condition(context)) {
		return false;
	}

	return true;
}

function isCommandDisabled(command: Command, context: CommandContext): boolean {
	if (typeof command.disabled === 'function') {
		return command.disabled(context);
	}

	return false;
}

function sortCommandsByPriority(commands: Command[]): Command[] {
	return [...commands].sort((a, b) => {
		const priorityA = a.priority ?? 0;
		const priorityB = b.priority ?? 0;

		if (priorityA === priorityB) {
			return a.label.localeCompare(b.label);
		}

		return priorityB - priorityA;
	});
}

function createFuse(commands: Command[]): Fuse<Command> {
	return new Fuse(commands, {
		keys: [
			{ name: 'label', weight: 0.6 },
			{ name: 'keywords', weight: 0.3 },
			{ name: 'description', weight: 0.1 }
		],
		includeScore: true,
		includeMatches: true,
		threshold: 0.35,
		ignoreLocation: true,
		minMatchCharLength: 2
	});
}


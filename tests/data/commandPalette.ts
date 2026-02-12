export type CommandPaletteCommand = {
	id: string;
	label: string;
};

export const CHANGE_MODEL_COMMAND: CommandPaletteCommand = {
	id: 'chat:change-model',
	label: 'Change Model'
};

export const MOVE_TO_FOLDER_COMMAND: CommandPaletteCommand = {
	id: 'chat:move-to-folder',
	label: 'Move to Folder'
};

export const EXPORT_COMMAND: CommandPaletteCommand = {
	id: 'chat:export',
	label: 'Export'
};

// TODO add more

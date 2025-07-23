import { writable } from 'svelte/store';

export interface SidebarNavigationCommand {
  type: 'navigateToChat' | 'navigateToFolder';
  target: string;      // chatId or folderId
  timestamp: number;
}

// Store for sending navigation commands to the sidebar
export const sidebarNavigationCommand = writable<SidebarNavigationCommand | null>(null);

// Helper functions to send navigation commands
export const navigateToChat = (chatId: string) => {
	sidebarNavigationCommand.set({
		type: 'navigateToChat',
		target: chatId,
		timestamp: Date.now()
	});
};

export const navigateToFolder = (folderId: string) => {
	sidebarNavigationCommand.set({
		type: 'navigateToFolder',
		target: folderId,
		timestamp: Date.now()
	});
};

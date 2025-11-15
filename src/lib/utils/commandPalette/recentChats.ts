import { writable } from 'svelte/store';

export type RecentChat = {
	id: string;
	title: string;
	timestamp: number;
};

const STORAGE_KEY = 'commandPaletteRecentChats';
const MAX_RECENTS = 5;

function loadFromStorage(): RecentChat[] {
	if (typeof localStorage === 'undefined') return [];
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (!raw) return [];
		const parsed = JSON.parse(raw);
		if (Array.isArray(parsed)) {
			return parsed as RecentChat[];
		}
		return [];
	} catch (error) {
		console.error('Failed to load recent chats', error);
		return [];
	}
}

function persist(list: RecentChat[]) {
	if (typeof localStorage === 'undefined') return;
	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
	} catch (error) {
		console.error('Failed to persist recent chats', error);
	}
}

const store = writable<RecentChat[]>([]);

export const recentChats = {
	subscribe: store.subscribe
};

let initialized = false;

function ensureInitialized() {
	if (!initialized) {
		store.set(loadFromStorage());
		initialized = true;
	}
}

if (typeof window !== 'undefined') {
	ensureInitialized();
}

export function addRecentChat(chat: { id: string; title?: string }) {
	if (!chat.id || chat.id === 'local') return;
	ensureInitialized();

	store.update((list) => {
		const filtered = list.filter((item) => item.id !== chat.id);
		const entry: RecentChat = {
			id: chat.id,
			title: chat.title?.trim() || 'Chat',
			timestamp: Date.now()
		};
		const next = [entry, ...filtered].slice(0, MAX_RECENTS);
		persist(next);
		return next;
	});
}

export function clearRecentChats() {
	store.set([]);
	persist([]);
}


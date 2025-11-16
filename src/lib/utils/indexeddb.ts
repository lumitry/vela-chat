import { openDB } from 'idb';
import type { IDBPDatabase } from 'idb';

export interface CachedMessage {
	id: string;
	chat_id: string;
	parent_id: string | null;
	role: string;
	model_id: string | null;
	position: number | null;
	content: string;
	content_json: object | null;
	status: object | null;
	usage: object | null;
	meta: object | null;
	annotation: object | null;
	feedback_id: string | null;
	selected_model_id: string | null;
	files: any[] | null;
	sources: any[] | null;
	created_at: number;
	updated_at: number;
	cache_key: string;
	cached_at: number;
	modelIdx: number | null; // Root-level property for side-by-side chats
	modelName: string | null; // Root-level property for model display name
	models: string[] | null; // Root-level property for side-by-side chat model selection
	children_ids: string[] | null; // Array of child message IDs - CRITICAL for message tree structure
}

const DB_NAME = 'vela-chat-messages';
const DB_VERSION = 1;

let dbInstance: IDBPDatabase | null = null;

/**
 * Initialize IndexedDB database for message caching
 */
export async function initMessageDB(): Promise<IDBPDatabase> {
	if (dbInstance) {
		return dbInstance;
	}

	try {
		dbInstance = await openDB(DB_NAME, DB_VERSION, {
			upgrade(db) {
				// Create messages object store
				const messageStore = db.createObjectStore('messages', {
					keyPath: 'id'
				});

				// Create index on chat_id for efficient querying
				messageStore.createIndex('chat_id', 'chat_id');

				// Create composite index on chat_id and updated_at for sync queries
				messageStore.createIndex('chat_id,updated_at', ['chat_id', 'updated_at']);
			}
		});

		return dbInstance;
	} catch (error) {
		console.error('Failed to initialize IndexedDB:', error);
		// If quota exceeded (Safari), try to clear and retry
		if (error instanceof DOMException && error.name === 'QuotaExceededError') {
			console.warn('IndexedDB quota exceeded, clearing cache...');
			try {
				await clearAllMessages();
				dbInstance = await openDB(DB_NAME, DB_VERSION);
				return dbInstance;
			} catch (retryError) {
				console.error('Failed to recover from quota error:', retryError);
				throw retryError;
			}
		}
		throw error;
	}
}

/**
 * Get all cached messages for a specific chat
 */
export async function getMessagesByChatId(chatId: string): Promise<CachedMessage[]> {
	try {
		const db = await initMessageDB();
		const tx = db.transaction('messages', 'readonly');
		const index = tx.store.index('chat_id');
		const messages = await index.getAll(chatId);
		return messages;
	} catch (error) {
		console.error(`Failed to get messages for chat ${chatId}:`, error);
		return [];
	}
}

/**
 * Get specific messages by their IDs
 */
export async function getMessagesByIds(messageIds: string[]): Promise<CachedMessage[]> {
	if (messageIds.length === 0) {
		return [];
	}

	try {
		const db = await initMessageDB();
		const tx = db.transaction('messages', 'readonly');
		const messages = await Promise.all(messageIds.map((id) => tx.store.get(id)));
		return messages.filter((msg): msg is CachedMessage => msg !== undefined);
	} catch (error) {
		console.error(`Failed to get messages by IDs:`, error);
		return [];
	}
}

/**
 * Bulk insert/update messages in IndexedDB
 */
export async function bulkPutMessages(messages: CachedMessage[]): Promise<void> {
	if (messages.length === 0) {
		return;
	}

	try {
		const db = await initMessageDB();
		const tx = db.transaction('messages', 'readwrite');

		// Add cached_at timestamp to each message
		const now = Date.now();
		const messagesWithTimestamp = messages.map((msg) => ({
			...msg,
			cached_at: now
		}));

		// Bulk put all messages in a single transaction
		await Promise.all(messagesWithTimestamp.map((msg) => tx.store.put(msg)));

		await tx.done;
	} catch (error) {
		console.error('Failed to bulk put messages:', error);
		// If quota exceeded, clear cache and retry
		if (error instanceof DOMException && error.name === 'QuotaExceededError') {
			console.warn('IndexedDB quota exceeded during bulk put, clearing cache...');
			await clearAllMessages();
			throw error; // Let caller handle retry
		}
		throw error;
	}
}

/**
 * Delete all messages for a specific chat
 */
export async function deleteMessagesByChatId(chatId: string): Promise<void> {
	try {
		const db = await initMessageDB();
		const tx = db.transaction('messages', 'readwrite');
		const index = tx.store.index('chat_id');

		// Get all message IDs for this chat
		const keys = await index.getAllKeys(chatId);

		// Delete all messages
		await Promise.all(keys.map((key) => tx.store.delete(key)));

		await tx.done;
	} catch (error) {
		console.error(`Failed to delete messages for chat ${chatId}:`, error);
		throw error;
	}
}

/**
 * Clear all cached messages (for manual wipe or error recovery)
 */
export async function clearAllMessages(): Promise<void> {
	try {
		const db = await initMessageDB();
		const tx = db.transaction('messages', 'readwrite');
		await tx.store.clear();
		await tx.done;
	} catch (error) {
		console.error('Failed to clear all messages:', error);
		throw error;
	}
}

/**
 * Get cache statistics
 */
export async function getCacheStats(): Promise<{
	totalMessages: number;
	estimatedSize: number | null;
}> {
	try {
		const db = await initMessageDB();
		const tx = db.transaction('messages', 'readonly');
		const count = await tx.store.count();

		// Estimate size by getting a sample and calculating average
		// This is approximate but better than nothing
		let estimatedSize: number | null = null;
		try {
			const sample = await tx.store.getAll();
			if (sample.length > 0) {
				const sampleSize = JSON.stringify(sample).length;
				const avgSize = sampleSize / sample.length;
				estimatedSize = Math.round(avgSize * count);
			}
		} catch (e) {
			// Size estimation failed, that's okay
			console.warn('Failed to estimate cache size:', e);
		}

		return {
			totalMessages: count,
			estimatedSize
		};
	} catch (error) {
		console.error('Failed to get cache stats:', error);
		return {
			totalMessages: 0,
			estimatedSize: null
		};
	}
}

/**
 * Check if IndexedDB is available
 */
export function isIndexedDBAvailable(): boolean {
	return typeof indexedDB !== 'undefined';
}

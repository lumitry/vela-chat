import { APP_NAME } from '$lib/constants';
import { type Writable, writable } from 'svelte/store';
import type { ModelConfig } from '$lib/apis';
import type { Banner } from '$lib/types';
import type { Socket } from 'socket.io-client';

import emojiShortCodes from '$lib/emoji-shortcodes.json';

// Backend
export const WEBUI_NAME = writable(APP_NAME);
export const config: Writable<Config | undefined> = writable(undefined);
export const user: Writable<SessionUser | undefined> = writable(undefined);

// Electron App
export const isApp = writable(false);
export const appInfo = writable(null);
export const appData = writable(null);

// Frontend
export const MODEL_DOWNLOAD_POOL = writable({});

export const mobile = writable(false);

export const socket: Writable<null | Socket> = writable(null);
export const activeUserIds: Writable<null | string[]> = writable(null);
export const USAGE_POOL: Writable<null | string[]> = writable(null);

export const theme = writable('system');

export const shortCodesToEmojis = writable(
	Object.entries(emojiShortCodes).reduce((acc, [key, value]) => {
		if (typeof value === 'string') {
			acc[value] = key;
		} else {
			for (const v of value) {
				acc[v] = key;
			}
		}

		return acc;
	}, {})
);

export const TTSWorker = writable(null);

export const chatId = writable('');
export const chatTitle = writable('');

export const channels = writable([]);
export const chats = writable(null);
export const pinnedChats = writable([]);
export const tags = writable([]);
export const folders: Writable<Record<string, any>> = writable({});

export const models: Writable<Model[]> = writable([]);

export const prompts: Writable<null | Prompt[]> = writable(null);

// Metrics cache
export const metricsCache: Writable<Map<string, any>> = writable(new Map());
export const knowledge: Writable<null | Document[]> = writable(null);
export const tools = writable(null);
export const functions = writable(null);

export const toolServers = writable([]);

export const banners: Writable<Banner[]> = writable([]);

export const settings: Writable<Settings> = writable({});

export const showSidebar = writable(false);
export const showSettings = writable(false);
export const showArchivedChats = writable(false);
export const showChangelog = writable(false);

export const showControls = writable(false);
export const showOverview = writable(false);
export const showArtifacts = writable(false);
export const showCallOverlay = writable(false);

export const temporaryChatEnabled = writable(false);
export const scrollPaginationEnabled = writable(false);
export const currentChatPage = writable(1);

// Chat list sorting - default to 'updated' (most recently modified)
export const chatListSortBy = writable(
	(localStorage.getItem('chatListSortBy') as 'updated' | 'created' | 'title') || 'updated'
);

export const isLastActiveTab = writable(true);
export const playingNotificationSound = writable(false);

// LRU Cache for chat prefetching - size-limited to prevent memory bloat
class LRUCache {
	private cache: Map<string, any> = new Map();
	private maxSize: number;

	constructor(maxSize: number = 10) {
		this.maxSize = maxSize;
	}

	has(key: string): boolean {
		return this.cache.has(key);
	}

	get(key: string): any | undefined {
		if (!this.cache.has(key)) {
			return undefined;
		}
		// Move to end (most recently used)
		const value = this.cache.get(key);
		this.cache.delete(key);
		this.cache.set(key, value);
		return value;
	}

	set(key: string, value: any): void {
		if (this.cache.has(key)) {
			// Update existing - move to end
			this.cache.delete(key);
		} else if (this.cache.size >= this.maxSize) {
			// Evict oldest (first item)
			const firstKey = this.cache.keys().next().value;
			if (firstKey !== undefined) {
				this.cache.delete(firstKey);
			}
		}
		this.cache.set(key, value);
	}

	delete(key: string): void {
		this.cache.delete(key);
	}

	clear(): void {
		this.cache.clear();
	}

	get size(): number {
		return this.cache.size;
	}
}

// Chat cache for prefetching - LRU with max 10 chats to prevent memory bloat
// You can adjust the max size if needed, but 10 should cover most hover scenarios
export const chatCache: Writable<LRUCache> = writable(new LRUCache(10));

export type Model = OpenAIModel | OllamaModel;

type BaseModel = {
	id: string;
	name: string;
	info?: ModelConfig;
	owned_by: 'ollama' | 'openai' | 'arena';
};

export interface OpenAIModel extends BaseModel {
	owned_by: 'openai';
	external: boolean;
	source?: string;
}

export interface OllamaModel extends BaseModel {
	owned_by: 'ollama';
	details: OllamaModelDetails;
	size: number;
	description: string;
	model: string;
	modified_at: string;
	digest: string;
	ollama?: {
		name?: string;
		model?: string;
		modified_at: string;
		size?: number;
		digest?: string;
		details?: {
			parent_model?: string;
			format?: string;
			family?: string;
			families?: string[];
			parameter_size?: string;
			quantization_level?: string;
		};
		urls?: number[];
	};
}

type OllamaModelDetails = {
	parent_model: string;
	format: string;
	family: string;
	families: string[] | null;
	parameter_size: string;
	quantization_level: string;
};

type Settings = {
	models?: string[];
	conversationMode?: boolean;
	speechAutoSend?: boolean;
	responseAutoPlayback?: boolean;
	audio?: AudioSettings;
	showUsername?: boolean;
	notificationEnabled?: boolean;
	title?: TitleSettings;
	splitLargeDeltas?: boolean;
	chatDirection: 'LTR' | 'RTL' | 'auto';
	ctrlEnterToSend?: boolean;
	customThemeColor?: string;

	system?: string;
	requestFormat?: string;
	keepAlive?: string;
	seed?: number;
	temperature?: string;
	repeat_penalty?: string;
	top_k?: string;
	top_p?: string;
	num_ctx?: string;
	num_batch?: string;
	num_keep?: string;
	options?: ModelOptions;
};

type ModelOptions = {
	stop?: boolean;
};

type AudioSettings = {
	STTEngine?: string;
	TTSEngine?: string;
	speaker?: string;
	model?: string;
	nonLocalVoices?: boolean;
};

type TitleSettings = {
	auto?: boolean;
	model?: string;
	modelExternal?: string;
	prompt?: string;
};

type Prompt = {
	command: string;
	user_id: string;
	title: string;
	content: string;
	timestamp: number;
};

type Document = {
	collection_name: string;
	filename: string;
	name: string;
	title: string;
};

type Config = {
	status: boolean;
	name: string;
	version: string;
	default_locale: string;
	default_models: string;
	default_prompt_suggestions: PromptSuggestion[];
	features: {
		auth: boolean;
		auth_trusted_header: boolean;
		enable_api_key: boolean;
		enable_signup: boolean;
		enable_login_form: boolean;
		enable_web_search?: boolean;
		enable_google_drive_integration: boolean;
		enable_onedrive_integration: boolean;
		enable_image_generation: boolean;
		enable_admin_export: boolean;
		enable_admin_chat_access: boolean;
		enable_community_sharing: boolean;
		enable_autocomplete_generation: boolean;
	};
	oauth: {
		providers: {
			[key: string]: string;
		};
	};
};

type PromptSuggestion = {
	content: string;
	title: [string, string];
};

type SessionUser = {
	id: string;
	email: string;
	name: string;
	role: string;
	profile_image_url: string;
};

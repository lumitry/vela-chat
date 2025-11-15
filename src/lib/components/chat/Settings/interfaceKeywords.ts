// Cache for Interface settings keywords
// This is populated by Interface.svelte and used by SettingsModal.svelte
let interfaceKeywordsCache: string[] = [];

export function setInterfaceKeywords(keywords: string[]): void {
	interfaceKeywordsCache = keywords;
}

export function getAllInterfaceKeywords(): string[] {
	return interfaceKeywordsCache;
}


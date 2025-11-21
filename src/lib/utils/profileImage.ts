import { browser } from '$app/environment';
import { WEBUI_BASE_URL } from '$lib/constants';

const ABSOLUTE_URL_PATTERN = /^[a-zA-Z][a-zA-Z\d+\-.]*:/;
const STATIC_ASSET_PREFIXES = ['/static/', '/user.png', '/favicon.png', '/doge.png'];

export const resolveProfileImageUrl = (url?: string | null): string | null => {
	if (!url) {
		return null;
	}

	const trimmedUrl = url.trim();
	if (!trimmedUrl) {
		return null;
	}

	if (
		ABSOLUTE_URL_PATTERN.test(trimmedUrl) ||
		(WEBUI_BASE_URL && trimmedUrl.startsWith(WEBUI_BASE_URL))
	) {
		return trimmedUrl;
	}

	if (!trimmedUrl.startsWith('/') || !browser) {
		return trimmedUrl;
	}

	if (STATIC_ASSET_PREFIXES.some((prefix) => trimmedUrl.startsWith(prefix))) {
		return `${window.location.origin}${trimmedUrl}`;
	}

	return `${WEBUI_BASE_URL}${trimmedUrl}`;
};

export const normalizeProfileImageFields = <T>(payload: T): T => {
	if (payload === null || payload === undefined) {
		return payload;
	}

	if (Array.isArray(payload)) {
		return payload.map((item) => normalizeProfileImageFields(item)) as unknown as T;
	}

	if (typeof payload === 'object') {
		const record = payload as Record<string, any>;

		for (const key of Object.keys(record)) {
			const value = record[key];

			if (key === 'profile_image_url') {
				record[key] = resolveProfileImageUrl(value) ?? value;
			} else if (value && (typeof value === 'object' || Array.isArray(value))) {
				record[key] = normalizeProfileImageFields(value);
			}
		}

		return payload;
	}

	return payload;
};

declare global {
	interface Window {
		__velaProfileImagePatched?: boolean;
	}
}

if (browser && typeof window !== 'undefined' && !window.__velaProfileImagePatched) {
	const originalJson = Response.prototype.json;

	Response.prototype.json = async function (...args) {
		const data = await originalJson.apply(this, args);
		return normalizeProfileImageFields(data);
	};

	window.__velaProfileImagePatched = true;
}


// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface Platform {}
	}
	
	// Vite-injected build-time constants
	const APP_VERSION: string;
	const APP_BUILD_HASH: string;
}

export {};

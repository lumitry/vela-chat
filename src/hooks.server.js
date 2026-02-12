/** @type {import('@sveltejs/kit').Handle} */
export async function handle({ event, resolve }) {
	// Handle Chrome DevTools well-known requests silently
	// Chrome DevTools automatically requests this file when debugging
	// Returning 404 here prevents SvelteKit from logging it as an error
	if (event.url.pathname === '/.well-known/appspecific/com.chrome.devtools.json') {
		return new Response(null, { status: 404 });
	}

	return resolve(event);
}

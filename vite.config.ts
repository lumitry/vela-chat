import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, loadEnv } from 'vite';
import { visualizer } from 'rollup-plugin-visualizer';

import { viteStaticCopy } from 'vite-plugin-static-copy';

/** @type {import('vite').Plugin} */
const viteServerConfig = {
	name: 'log-request-middleware',
	configureServer(server) {
		server.middlewares.use((req, res, next) => {
			res.setHeader('Access-Control-Allow-Origin', '*');
			res.setHeader('Access-Control-Allow-Methods', 'GET');
			res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
			res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp');
			next();
		});
	}
};

export default defineConfig(({ mode }) => {
	const env = loadEnv(mode, process.cwd(), '');

	const allowedHosts = env.VITE_ALLOWED_HOSTS
		? env.VITE_ALLOWED_HOSTS.split(',')
				.map((h) => h.trim())
				.filter(Boolean)
		: undefined;

	return {
		plugins: [
			sveltekit(),
			viteStaticCopy({
				targets: [
					{
						src: 'node_modules/onnxruntime-web/dist/*.jsep.*',

						dest: 'wasm'
					}
				]
			}),
			viteServerConfig,
			visualizer({
				open: true,
				filename: 'dist/stats.html',
				gzipSize: true,
				brotliSize: true,
				emitFile: false
			})
		],
		define: {
			APP_VERSION: JSON.stringify(process.env.npm_package_version),
			APP_BUILD_HASH: JSON.stringify(process.env.APP_BUILD_HASH || 'dev-build')
		},
		build: {
			sourcemap: true,
			rollupOptions: {
				output: {
					manualChunks: undefined
				}
			}
		},
		optimizeDeps: {
			include: ['bits-ui']
		},
		worker: {
			format: 'es'
		},
		server: {
			...(allowedHosts ? { allowedHosts } : {}),
			watch: {
				ignored: ['**/README.md']
			}
		}
	};
});

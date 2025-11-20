import { defineConfig } from 'cypress';

const port = process.env.PORT ?? '8080';

export default defineConfig({
	e2e: {
		baseUrl: `http://localhost:${port}`
	},
	video: true
});

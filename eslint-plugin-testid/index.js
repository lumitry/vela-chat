// Re-export from the CommonJS version
// This file exists because ESLint/VSCode may try to load index.js before checking package.json main
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
export default require('./index.cjs');


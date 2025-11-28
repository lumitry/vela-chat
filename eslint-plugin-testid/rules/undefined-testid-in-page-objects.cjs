const { getCache, isInitialized } = require('../utils/cache.cjs');
const { extractTestIdFromCall, partsToPattern } = require('../utils/testIdExtractor.cjs');
const { scanAllFiles } = require('../utils/fileScanner.cjs');
const path = require('path');

/**
 * ESLint rule to check if testIds used in page objects are defined in .svelte files
 */
module.exports = {
	meta: {
		type: 'problem',
		docs: {
			description:
				'Check if testIds used in page object classes are defined in .svelte files',
			category: 'Possible Errors',
			recommended: false
		},
		fixable: null,
		schema: []
	},
	create(context) {
		const cache = getCache();
		let filename = context.getFilename();
		
		// Normalize the filename path
		filename = path.resolve(filename).replace(/\\/g, '/');
		
		// On first file processed, scan all files to build complete cache
		if (!isInitialized()) {
			const workspaceRoot = context.getCwd ? context.getCwd() : process.cwd();
			scanAllFiles(workspaceRoot);
		}

		// Only process page object files (TypeScript files in tests/pages/)
		const isPageObjectFile =
			filename.endsWith('.ts') &&
			(filename.includes(path.join('tests', 'pages')) ||
				filename.includes('tests/pages') ||
				filename.includes('tests\\pages'));

		if (!isPageObjectFile) {
			return {};
		}

		/**
		 * Recursively find all testId() and getPageTestId() calls in the AST
		 */
		function findTestIdCalls(node) {
			if (!node) {
				return;
			}

			// Check if this is a CallExpression for testId() or getPageTestId() or getPageLocator()
			const testIdInfo = extractTestIdFromCall(node, context);
			if (testIdInfo) {
				const pattern = partsToPattern(testIdInfo.parts);
				// Store the AST node so we can report at the correct location
				cache.addPageObjectTestId(filename, pattern, { node });
			}

			// Recursively check children
			for (const key in node) {
				if (key === 'parent' || key === 'range') {
					continue;
				}
				const child = node[key];
				if (Array.isArray(child)) {
					child.forEach(findTestIdCalls);
				} else if (child && typeof child === 'object') {
					findTestIdCalls(child);
				}
			}
		}

		return {
			Program(node) {
				// Clear any existing testIds for this file to ensure fresh data
				cache.clearFileTestIds(filename);
				
				findTestIdCalls(node);
			},
			'Program:exit'(node) {
				// After processing the file, check if any testIds are undefined
				const fileTestIds = cache.pageObjectTestIds.get(filename);
				if (!fileTestIds) {
					return;
				}

				for (const [pattern, location] of fileTestIds.entries()) {
					// Skip patterns with wildcards (variables) - we can't verify those
					if (pattern.includes('*')) {
						continue;
					}
					
					// Skip incomplete patterns (likely from partial typing)
					// Patterns should have at least 2 segments
					const segments = pattern.split('_');
					if (segments.length < 2) {
						continue;
					}
					// Skip if last segment is very short (1-2 chars) - likely incomplete typing
					// This helps avoid false positives while typing
					const lastSegment = segments[segments.length - 1];
					if (lastSegment.length <= 2) {
						continue;
					}

					if (!cache.isDefinedInSvelte(pattern)) {
						// Report at the specific AST node location if available
						const reportNode = location && location.node ? location.node : node;
						
						context.report({
							node: reportNode,
							message: `testId "${pattern}" is used in page object but not defined in any .svelte file`
						});
					}
				}
			}
		};
	}
};


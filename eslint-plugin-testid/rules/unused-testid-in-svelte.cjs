const { getCache, isInitialized } = require('../utils/cache.cjs');
const { extractTestIdFromCall, partsToPattern } = require('../utils/testIdExtractor.cjs');
const { scanAllFiles } = require('../utils/fileScanner.cjs');
const { extractTestIdsFromSvelteWithLocation } = require('../utils/testIdParser.cjs');
const { traverse } = require('../utils/astTraverser.cjs');
const path = require('path');

/**
 * ESLint rule to check if testIds in .svelte files are used in page objects
 */
module.exports = {
	meta: {
		type: 'problem',
		docs: {
			description:
				'Check if data-testid attributes using testId() in .svelte files are used in page object classes',
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

		// Only process .svelte files
		if (!filename.endsWith('.svelte')) {
			return {};
		}

		// Get the Svelte AST from the parser
		const sourceCode = context.getSourceCode();
		const svelteAst = sourceCode.ast;
		
		// Also try to get it from parserServices (svelte-eslint-parser specific)
		const parserServices = context.parserServices || context.sourceCode?.parserServices;
		const svelteTemplateAST = parserServices?.svelteAST?.html;

		/**
		 * Find all testId() calls in the AST using efficient traversal
		 * This is used for the script section of Svelte files
		 */
		function findTestIdCalls(rootNode) {
			if (!rootNode) {
				return;
			}

			// Use efficient AST traversal instead of naive recursion
			traverse(rootNode, (node) => {
				// Only check CallExpression nodes
				if (node.type === 'CallExpression') {
					const testIdInfo = extractTestIdFromCall(node, context);
					if (testIdInfo) {
						const pattern = partsToPattern(testIdInfo.parts);
						// Store in cache for later checking
						cache.addSvelteTestId(filename, pattern);
					}
				}
				// Continue traversing (don't return false)
			});
		}

		/**
		 * Extract testId from Svelte template using source text parsing
		 * This is more reliable than AST traversal for Svelte templates
		 */
		function extractFromSvelteTemplate() {
			const text = sourceCode.getText();
			
			// Use centralized extraction utility with location information
			const extracted = extractTestIdsFromSvelteWithLocation(text, { includeProps: true });
			
			for (const { pattern, type, location } of extracted) {
				if (type === 'data-testid') {
					cache.addSvelteTestId(filename, pattern, location);
				} else if (type === 'prop') {
					cache.addSveltePropTestId(filename, pattern, location);
				}
			}
		}

		return {
			Program(node) {
				// Clear any existing testIds for this file to ensure fresh data
				cache.clearFileTestIds(filename);
				
				// First, try to extract from Svelte template
				extractFromSvelteTemplate();

				// Also check the script section for any testId calls
				if (svelteAst && svelteAst.instance) {
					findTestIdCalls(svelteAst.instance);
				}
				if (svelteAst && svelteAst.module) {
					findTestIdCalls(svelteAst.module);
				}
			},
			'Program:exit'(node) {
				// After processing the file, check if any testIds are unused
				const fileTestIds = cache.svelteTestIds.get(filename);
				if (!fileTestIds) {
					return;
				}

				for (const [pattern, location] of fileTestIds.entries()) {
					// Skip patterns with wildcards (variables) - we can't verify those
					if (pattern.includes('*')) {
						continue;
					}

					if (!cache.isUsedInPageObjects(pattern)) {
						// Report at the specific location if available
						if (location && location.line) {
							// Create a simple location object for reporting
							const lineText = sourceCode.getText().split('\n')[location.line - 1] || '';
							// Find the testId call on this line
							const testIdMatch = lineText.match(/data-testid\s*=\s*\{testId\s*\(/);
							if (testIdMatch) {
								const testIdIndex = testIdMatch.index || 0;
								const testIdEnd = testIdIndex + testIdMatch[0].length;
								
								context.report({
									loc: {
										start: { line: location.line, column: testIdIndex },
										end: { line: location.line, column: Math.min(testIdEnd, lineText.length) }
									},
									message: `testId "${pattern}" is defined in .svelte file but not used in any page object class`
								});
								continue;
							}
						}
						
						// Fallback: report at the start of the file
						context.report({
							node,
							message: `testId "${pattern}" is defined in .svelte file but not used in any page object class`
						});
					}
				}
			}
		};
	}
};


const { getCache, isInitialized } = require('../utils/cache.cjs');
const { extractTestIdFromCall, partsToPattern } = require('../utils/testIdExtractor.cjs');
const { scanAllFiles } = require('../utils/fileScanner.cjs');
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
		 * Recursively find all testId() calls in the AST
		 */
		function findTestIdCalls(node) {
			if (!node) {
				return;
			}

			// Check if this is a CallExpression for testId()
			const testIdInfo = extractTestIdFromCall(node, context);
			if (testIdInfo) {
				const pattern = partsToPattern(testIdInfo.parts);
				// Store in cache for later checking
				cache.addSvelteTestId(filename, pattern);
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

		/**
		 * Extract testId from Svelte template using source text parsing
		 * This is more reliable than AST traversal for Svelte templates
		 */
		function extractFromSvelteTemplate() {
			const text = sourceCode.getText();
			const lines = text.split('\n');
			
			// Find all data-testid={testId(...)} patterns
			// Match: data-testid={testId('Part1', 'Part2', ...)}
			const dataTestIdRegex = /data-testid\s*=\s*\{testId\s*\(([^}]+)\)\}/g;
			let match;
			
			while ((match = dataTestIdRegex.exec(text)) !== null) {
				const matchIndex = match.index;
				// Calculate line and column from the match position
				let line = 1;
				let column = 0;
				let currentIndex = 0;
				
				for (let i = 0; i < lines.length; i++) {
					const lineLength = lines[i].length + 1; // +1 for newline
					if (currentIndex + lineLength > matchIndex) {
						line = i + 1;
						column = matchIndex - currentIndex;
						break;
					}
					currentIndex += lineLength;
				}
				
				const argsStr = match[1];
				// Parse the arguments - they're string literals separated by commas
				// Match: 'Part1', 'Part2', model.id (variables)
				const argRegex = /['"]([^'"]+)['"]|(\w+(?:\.\w+)*)/g;
				const parts = [];
				let argMatch;
				
				while ((argMatch = argRegex.exec(argsStr)) !== null) {
					if (argMatch[1]) {
						// String literal
						parts.push(argMatch[1]);
					} else if (argMatch[2]) {
						// Variable - treat as wildcard
						parts.push('*');
					}
				}
				
				if (parts.length > 0) {
					const pattern = partsToPattern(parts);
					cache.addSvelteTestId(filename, pattern, { line, column });
				}
			}
			
			// Also find testId={testId(...)} patterns (component props)
			// Match: testId={testId('Part1', 'Part2', ...)}
			// But exclude data-testid (already handled above)
			const propTestIdRegex = /(?:^|[^a-z-])testId\s*=\s*\{testId\s*\(([^}]+)\)\}/g;
			match = null;
			
			while ((match = propTestIdRegex.exec(text)) !== null) {
				const matchIndex = match.index;
				// Calculate line and column from the match position
				let line = 1;
				let column = 0;
				let currentIndex = 0;
				
				for (let i = 0; i < lines.length; i++) {
					const lineLength = lines[i].length + 1; // +1 for newline
					if (currentIndex + lineLength > matchIndex) {
						line = i + 1;
						column = matchIndex - currentIndex;
						break;
					}
					currentIndex += lineLength;
				}
				
				const argsStr = match[1];
				// Parse the arguments
				const argRegex = /['"]([^'"]+)['"]|(\w+(?:\.\w+)*)/g;
				const parts = [];
				let argMatch;
				
				while ((argMatch = argRegex.exec(argsStr)) !== null) {
					if (argMatch[1]) {
						// String literal
						parts.push(argMatch[1]);
					} else if (argMatch[2]) {
						// Variable - treat as wildcard
						parts.push('*');
					}
				}
				
				if (parts.length > 0) {
					const pattern = partsToPattern(parts);
					// Store as prop testId (component prop, not direct data-testid)
					cache.addSveltePropTestId(filename, pattern, { line, column });
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


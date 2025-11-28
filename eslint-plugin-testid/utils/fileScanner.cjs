const fs = require('fs');
const path = require('path');
const { getCache, markInitialized } = require('./cache.cjs');
const { extractTestIdFromCall, partsToPattern } = require('./testIdExtractor.cjs');

/**
 * Normalize file paths to ensure consistent matching
 */
function normalizePath(filePath) {
	return path.resolve(filePath).replace(/\\/g, '/');
}

/**
 * Scans all relevant files to build a complete cache of testIds
 */
function scanAllFiles(workspaceRoot) {
	const cache = getCache();
	
	// Find all .svelte files in src/
	const svelteFiles = findFiles(workspaceRoot, 'src', '.svelte');
	
	// Find all page object files in tests/pages/
	const pageObjectFiles = findFiles(workspaceRoot, 'tests/pages', '.ts');
	
	// Process all .svelte files
	for (const filePath of svelteFiles) {
		extractTestIdsFromSvelteFile(filePath);
	}
	
	// Process all page object files
	for (const filePath of pageObjectFiles) {
		extractTestIdsFromPageObjectFile(filePath);
	}
	
	markInitialized();
}

/**
 * Recursively find files matching the extension in the given directory
 */
function findFiles(root, dir, ext) {
	const files = [];
	const fullDir = path.join(root, dir);
	
	if (!fs.existsSync(fullDir)) {
		return files;
	}
	
	function walk(currentDir) {
		const entries = fs.readdirSync(currentDir, { withFileTypes: true });
		
		for (const entry of entries) {
			const fullPath = path.join(currentDir, entry.name);
			
			if (entry.isDirectory()) {
				// Skip node_modules and other common ignore dirs
				if (entry.name === 'node_modules' || entry.name === '.git' || entry.name === 'dist' || entry.name === 'build') {
					continue;
				}
				walk(fullPath);
			} else if (entry.isFile() && entry.name.endsWith(ext)) {
				files.push(fullPath);
			}
		}
	}
	
	walk(fullDir);
	return files;
}

/**
 * Extract testIds from a .svelte file using regex
 */
function extractTestIdsFromSvelteFile(filePath) {
	try {
		const content = fs.readFileSync(filePath, 'utf8');
		const cache = getCache();
		
		// Find all data-testid={testId(...)} patterns
		const dataTestIdRegex = /data-testid\s*=\s*\{testId\s*\(([^}]+)\)\}/g;
		let match;
		
		while ((match = dataTestIdRegex.exec(content)) !== null) {
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
				// File scanner doesn't have location info, rules will add it when processing files
				cache.addSvelteTestId(normalizePath(filePath), pattern, null);
			}
		}
		
		// Also find testId={testId(...)} patterns (component props)
		// Match: testId={testId('Part1', 'Part2', ...)}
		// But exclude data-testid (already handled above)
		const propTestIdRegex = /(?:^|[^a-z-])testId\s*=\s*\{testId\s*\(([^}]+)\)\}/g;
		match = null;
		
		while ((match = propTestIdRegex.exec(content)) !== null) {
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
				// File scanner doesn't have location info, rules will add it when processing files
				cache.addSveltePropTestId(normalizePath(filePath), pattern, null);
			}
		}
	} catch (error) {
		// Silently ignore errors (file might not exist, permissions, etc.)
	}
}

/**
 * Extract testIds from a page object file using regex
 */
function extractTestIdsFromPageObjectFile(filePath) {
	try {
		const content = fs.readFileSync(filePath, 'utf8');
		const cache = getCache();
		
		// Find testId(...) calls, but skip ones inside method definitions
		const testIdRegex = /testId\s*\(([^)]+)\)/g;
		let match;
		
		while ((match = testIdRegex.exec(content)) !== null) {
			const argsStr = match[1];
			
			// Skip if this has rest parameters (...args) or spread operator
			if (argsStr.includes('...')) {
				continue;
			}
			
			// Skip if this call is inside a method definition
			// Check the line containing this call
			const callIndex = match.index;
			const lineStart = content.lastIndexOf('\n', callIndex) + 1;
			const lineEnd = content.indexOf('\n', callIndex);
			const line = content.substring(lineStart, lineEnd === -1 ? content.length : lineEnd);
			
			// Skip if this line is part of a method definition (contains => or : string)
			if (/=>|:\s*(?:string|Locator)/.test(line) && /(?:getPageTestId|getPageLocator)\s*=/.test(line)) {
				continue;
			}
			
			const argRegex = /['"]([^'"]+)['"]|(\w+(?:\.\w+)*)/g;
			const parts = [];
			let argMatch;
			let hasStringLiteral = false;
			
			while ((argMatch = argRegex.exec(argsStr)) !== null) {
				if (argMatch[1]) {
					parts.push(argMatch[1]);
					hasStringLiteral = true;
				} else if (argMatch[2] && argMatch[2] !== 'args') {
					// Treat variables as wildcards (but skip 'args' which is a rest parameter)
					parts.push('*');
				}
			}
			
			// Only add if we have at least one string literal (not just wildcards)
			if (parts.length > 0 && hasStringLiteral) {
				const pattern = partsToPattern(parts);
				// File scanner doesn't have location info, rules will add it when processing files
				cache.addPageObjectTestId(normalizePath(filePath), pattern, null);
			}
		}
		
		// Also find getPageTestId(...) and getPageLocator(...) calls
		// These are trickier because we need to find the prefix from the class definition
		// Match: getPageTestId = (...args) => testId('Chat', ...args)
		// or: getPageTestId = (...args) => { return testId('Chat', ...args); }
		const getPageTestIdRegex = /getPageTestId\s*=\s*\([^)]*\)\s*=>\s*(?:\{[^}]*return\s+)?testId\s*\(([^)]+)\)/g;
		let pageMatch;
		
		while ((pageMatch = getPageTestIdRegex.exec(content)) !== null) {
			const prefixStr = pageMatch[1];
			if (!prefixStr) continue;
			
			// Extract only string literals from the prefix (ignore ...args)
			const prefixArgRegex = /['"]([^'"]+)['"]/g;
			const prefixParts = [];
			let prefixArgMatch;
			
			while ((prefixArgMatch = prefixArgRegex.exec(prefixStr)) !== null) {
				prefixParts.push(prefixArgMatch[1]);
			}
			
			if (prefixParts.length === 0) {
				continue; // No prefix found, skip
			}
			
			// Now find all calls to getPageTestId or getPageLocator with this prefix
			// Find calls like: this.getPageLocator('Navbar', 'ControlsButton')
			// But skip: this.getPageTestId(...args) inside method definitions
			const callRegex = /(?:this\.)?(?:getPageTestId|getPageLocator)\s*\(([^)]+)\)/g;
			let callMatch;
			
			// Reset regex to search from beginning
			callRegex.lastIndex = 0;
			
			while ((callMatch = callRegex.exec(content)) !== null) {
				const argsStr = callMatch[1];
				
				// Skip if this has rest parameters (...args) or spread operator
				if (argsStr.includes('...') || argsStr.trim() === '') {
					continue;
				}
				
				// Skip if this call is inside a method definition
				// Check if the line contains the method definition pattern
				const callIndex = callMatch.index;
				const lineStart = content.lastIndexOf('\n', callIndex) + 1;
				const lineEnd = content.indexOf('\n', callIndex);
				const line = content.substring(lineStart, lineEnd === -1 ? content.length : lineEnd);
				
				// Skip if this line is a method definition
				if (/^\s*(?:protected|private|public)?\s*(?:getPageTestId|getPageLocator)\s*=/.test(line)) {
					continue;
				}
				
				// Extract arguments - only string literals, treat other identifiers as wildcards
				const argRegex = /['"]([^'"]+)['"]|(\w+(?:\.\w+)*)/g;
				const parts = [...prefixParts];
				let argMatch;
				let hasStringLiteral = false;
				
				while ((argMatch = argRegex.exec(argsStr)) !== null) {
					if (argMatch[1]) {
						parts.push(argMatch[1]);
						hasStringLiteral = true;
					} else if (argMatch[2] && argMatch[2] !== 'args') {
						// Treat variables as wildcards (but skip 'args' which is a rest parameter)
						parts.push('*');
					}
				}
				
				// Only add if we have at least one string literal (not just wildcards)
				if (parts.length > 0 && hasStringLiteral) {
					const pattern = partsToPattern(parts);
					// File scanner doesn't have location info, rules will add it when processing files
					cache.addPageObjectTestId(normalizePath(filePath), pattern, null);
				}
			}
		}
	} catch (error) {
		// Silently ignore errors
	}
}

module.exports = {
	scanAllFiles
};


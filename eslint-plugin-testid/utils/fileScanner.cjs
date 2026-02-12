const fs = require('fs');
const path = require('path');
const { getCache, markInitialized } = require('./cache.cjs');
const { partsToPattern } = require('./testIdExtractor.cjs');
const { extractTestIdsFromSvelteContent } = require('./testIdParser.cjs');
const {
	TESTID_CALL_REGEX,
	GET_PAGE_TESTID_DEF_REGEX,
	GET_PAGE_CALL_REGEX,
	ARGUMENT_EXTRACTOR_REGEX,
	STRING_LITERAL_REGEX
} = require('./regexPatterns.cjs');

/**
 * Normalize file paths to ensure consistent matching
 */
function normalizePath(filePath) {
	return path.resolve(filePath).replace(/\\/g, '/');
}

/**
 * Scans all relevant files to build a complete cache of testIds
 * @param {string} workspaceRoot - Root directory of the workspace
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
 * @param {string} root - Root directory
 * @param {string} dir - Subdirectory to search in
 * @param {string} ext - File extension to match (e.g., '.svelte', '.ts')
 * @returns {string[]} - Array of file paths
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
 * @param {string} filePath - Path to the .svelte file
 */
function extractTestIdsFromSvelteFile(filePath) {
	try {
		const content = fs.readFileSync(filePath, 'utf8');
		const cache = getCache();
		const normalizedPath = normalizePath(filePath);
		
		// Use centralized extraction utility
		const extracted = extractTestIdsFromSvelteContent(content, { includeProps: true });
		
		for (const { pattern, type } of extracted) {
			if (type === 'data-testid') {
				// File scanner doesn't have location info, rules will add it when processing files
				cache.addSvelteTestId(normalizedPath, pattern, null);
			} else if (type === 'prop') {
				cache.addSveltePropTestId(normalizedPath, pattern, null);
			}
		}
	} catch (error) {
		// Silently ignore errors (file might not exist, permissions, etc.)
		// This is intentional - we don't want to break ESLint if a file can't be read
		// In the future, could add optional debug logging here if needed
	}
}

/**
 * Extract testIds from a page object file using regex
 * Handles both direct testId() calls and getPageTestId()/getPageLocator() calls
 * @param {string} filePath - Path to the page object file
 */
function extractTestIdsFromPageObjectFile(filePath) {
	try {
		const content = fs.readFileSync(filePath, 'utf8');
		const cache = getCache();
		
		// Find testId(...) calls, but skip ones inside method definitions
		let match;
		
		TESTID_CALL_REGEX.lastIndex = 0;
		while ((match = TESTID_CALL_REGEX.exec(content)) !== null) {
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
			
			// Use centralized argument parser
			const parts = [];
			let hasStringLiteral = false;
			
			ARGUMENT_EXTRACTOR_REGEX.lastIndex = 0;
			let argMatch;
			while ((argMatch = ARGUMENT_EXTRACTOR_REGEX.exec(argsStr)) !== null) {
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
		let pageMatch;
		
		GET_PAGE_TESTID_DEF_REGEX.lastIndex = 0;
		while ((pageMatch = GET_PAGE_TESTID_DEF_REGEX.exec(content)) !== null) {
			const prefixStr = pageMatch[1];
			if (!prefixStr) continue;
			
			// Extract only string literals from the prefix (ignore ...args)
			const prefixParts = [];
			STRING_LITERAL_REGEX.lastIndex = 0;
			let prefixArgMatch;
			
			while ((prefixArgMatch = STRING_LITERAL_REGEX.exec(prefixStr)) !== null) {
				prefixParts.push(prefixArgMatch[1]);
			}
			
			if (prefixParts.length === 0) {
				continue; // No prefix found, skip
			}
			
			// Now find all calls to getPageTestId or getPageLocator with this prefix
			// Find calls like: this.getPageLocator('Navbar', 'ControlsButton')
			// But skip: this.getPageTestId(...args) inside method definitions
			let callMatch;
			
			// Reset regex to search from beginning
			GET_PAGE_CALL_REGEX.lastIndex = 0;
			
			while ((callMatch = GET_PAGE_CALL_REGEX.exec(content)) !== null) {
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
				const parts = [...prefixParts];
				let hasStringLiteral = false;
				
				ARGUMENT_EXTRACTOR_REGEX.lastIndex = 0;
				let argMatch;
				while ((argMatch = ARGUMENT_EXTRACTOR_REGEX.exec(argsStr)) !== null) {
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
		// Silently ignore errors (file might not exist, permissions, etc.)
		// This is intentional - we don't want to break ESLint if a file can't be read
	}
}

module.exports = {
	scanAllFiles
};


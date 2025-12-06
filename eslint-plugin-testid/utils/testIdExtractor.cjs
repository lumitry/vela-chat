/**
 * Utility functions for extracting testId patterns from AST nodes
 */

const { traverse } = require('./astTraverser.cjs');

/**
 * Extracts testId parts from a CallExpression node that calls testId() or getPageTestId() or getPageLocator()
 * @param {Object} node - The CallExpression AST node
 * @param {Object} context - ESLint context (optional, for finding class methods)
 * @returns {Object|null} - Object with { parts: string[], hasVariables: boolean } or null
 */
function extractTestIdFromCall(node, context = null) {
	if (!node || node.type !== 'CallExpression') {
		return null;
	}

	const callee = node.callee;
	if (!callee) {
		return null;
	}

	// Handle: testId(...)
	if (callee.type === 'Identifier' && callee.name === 'testId') {
		return extractPartsFromArguments(node.arguments);
	}

	// Handle: getPageTestId(...) or this.getPageTestId(...)
	if (
		(callee.type === 'Identifier' && callee.name === 'getPageTestId') ||
		(callee.type === 'MemberExpression' &&
			callee.property &&
			callee.property.type === 'Identifier' &&
			callee.property.name === 'getPageTestId')
	) {
		// Extract the prefix from the class's getPageTestId method definition
		const prefix = findGetPageTestIdPrefix(node, context);
		if (prefix) {
			const argsResult = extractPartsFromArguments(node.arguments);
			if (argsResult) {
				return {
					parts: [...prefix, ...argsResult.parts],
					hasVariables: argsResult.hasVariables
				};
			}
		}
		// If we can't find the prefix, just extract the arguments (they'll be incomplete but better than nothing)
		return extractPartsFromArguments(node.arguments);
	}

	// Handle: getPageLocator(...) or this.getPageLocator(...)
	if (
		(callee.type === 'Identifier' && callee.name === 'getPageLocator') ||
		(callee.type === 'MemberExpression' &&
			callee.property &&
			callee.property.type === 'Identifier' &&
			callee.property.name === 'getPageLocator')
	) {
		// getPageLocator calls getPageTestId internally, so find the prefix
		const prefix = findGetPageTestIdPrefix(node, context);
		if (prefix) {
			const argsResult = extractPartsFromArguments(node.arguments);
			if (argsResult) {
				return {
					parts: [...prefix, ...argsResult.parts],
					hasVariables: argsResult.hasVariables
				};
			}
		}
		// If we can't find the prefix, just extract the arguments
		return extractPartsFromArguments(node.arguments);
	}

	return null;
}

/**
 * Extracts parts from function arguments
 * @param {Array} arguments_ - Array of AST argument nodes
 * @returns {{parts: string[], hasVariables: boolean}} - Extracted parts and whether variables were found
 */
function extractPartsFromArguments(arguments_) {
	const parts = [];
	let hasVariables = false;

	for (const arg of arguments_ || []) {
		if (arg.type === 'Literal' || arg.type === 'StringLiteral') {
			parts.push(String(arg.value));
		} else if (arg.type === 'TemplateLiteral') {
			// Template literals are treated as variables (wildcards)
			hasVariables = true;
			parts.push('*');
		} else {
			// Any other expression type (Identifier, MemberExpression, etc.) is a variable
			hasVariables = true;
			parts.push('*');
		}
	}

	return { parts, hasVariables };
}

/**
 * Finds the prefix used in getPageTestId method by looking for the method definition in the AST
 * This is a heuristic that looks for patterns like: getPageTestId = (...args) => testId('Prefix', ...args)
 * @param {Object} callNode - The AST node for the getPageTestId/getPageLocator call
 * @param {Object} context - ESLint context
 * @returns {string[]|null} - Array of prefix parts or null if not found
 */
function findGetPageTestIdPrefix(callNode, context) {
	if (!context) {
		return null;
	}

	try {
		const sourceCode = context.getSourceCode();
		const ast = sourceCode.ast;
		const filename = context.getFilename();

		// Helper function to extract prefix from arrow function
		function extractPrefixFromArrowFunction(arrowFunc) {
			if (!arrowFunc || arrowFunc.type !== 'ArrowFunctionExpression') {
				return null;
			}
			
			let testIdCall = null;
			
			// Handle direct expression: => testId(...)
			if (
				arrowFunc.body &&
				arrowFunc.body.type === 'CallExpression' &&
				arrowFunc.body.callee &&
				arrowFunc.body.callee.type === 'Identifier' &&
				arrowFunc.body.callee.name === 'testId'
			) {
				testIdCall = arrowFunc.body;
			}
			// Handle block body: => { return testId(...); }
			else if (
				arrowFunc.body &&
				arrowFunc.body.type === 'BlockStatement' &&
				arrowFunc.body.body &&
				arrowFunc.body.body.length > 0
			) {
				// Look for return statement with testId call
				for (const stmt of arrowFunc.body.body) {
					if (
						stmt.type === 'ReturnStatement' &&
						stmt.argument &&
						stmt.argument.type === 'CallExpression' &&
						stmt.argument.callee &&
						stmt.argument.callee.type === 'Identifier' &&
						stmt.argument.callee.name === 'testId'
					) {
						testIdCall = stmt.argument;
						break;
					}
				}
			}
			
			if (testIdCall) {
				// Extract the first argument(s) which are the prefix
				const prefixArgs = testIdCall.arguments;
				const prefix = [];
				for (const arg of prefixArgs) {
					if (arg.type === 'Literal' || arg.type === 'StringLiteral') {
						prefix.push(String(arg.value));
					} else if (arg.type === 'SpreadElement') {
						// Skip spread elements (...args)
						break;
					} else {
						// If there's a variable in the prefix, we can't determine it statically
						return null;
					}
				}
				return prefix.length > 0 ? prefix : null;
			}
			
			return null;
		}

		// Try to find prefix in parent class file
		// This is a heuristic approach - looks for parent class file in the same directory
		// Note: This won't handle complex import scenarios, but works for common cases
		function findPrefixInParentClass(parentClassName, currentFile, context) {
			try {
				const path = require('path');
				const fs = require('fs');
				
				// Try to find the parent class file
				// Common pattern: if current file is ChatPage.ts, parent might be BaseChatPage.ts in same directory
				const currentDir = path.dirname(currentFile);
				
				// Try multiple possible locations
				const possiblePaths = [
					path.resolve(currentDir, `${parentClassName}.ts`), // Same directory
					path.resolve(currentDir, '..', `${parentClassName}.ts`), // Parent directory
					path.resolve(currentDir, '..', '..', `${parentClassName}.ts`) // Grandparent directory
				];
				
				for (const parentFile of possiblePaths) {
					if (fs.existsSync(parentFile)) {
						try {
							const content = fs.readFileSync(parentFile, 'utf8');
							
							// Look for getPageTestId definition
							// Match: getPageTestId = (...args) => { return testId('Chat', ...args); }
							// Use a simpler approach: find getPageTestId and then find testId call nearby
							const getPageTestIdIndex = content.indexOf('getPageTestId');
							if (getPageTestIdIndex !== -1) {
								// Get a chunk of text around the definition (300 chars to handle multiline)
								const chunkStart = Math.max(0, getPageTestIdIndex - 50);
								const chunkEnd = Math.min(content.length, getPageTestIdIndex + 300);
								const chunk = content.substring(chunkStart, chunkEnd);
								
								// Look for testId('Chat', ...) in this chunk
								// Try to find the first string literal argument
								const testIdMatch = chunk.match(/testId\s*\(\s*['"]([^'"]+)['"]/);
								if (testIdMatch) {
									return [testIdMatch[1]];
								}
							}
						} catch (readError) {
							// If we can't read this file, try the next one
							continue;
						}
					}
				}
			} catch (e) {
				// Silently fail - this is a heuristic, not critical
				// In the future, could add optional debug logging here
			}
			return null;
		}

		// Look for getPageTestId method definition
		// Use efficient AST traversal to find class declarations
		let foundPrefix = null;
		
		traverse(ast, (node) => {
			// Look for class declarations/expressions
			if (node.type === 'ClassDeclaration' || node.type === 'ClassExpression') {
				if (node.body && node.body.body) {
					for (const member of node.body.body) {
						// Check PropertyDefinition (TypeScript class fields)
						if (
							member.type === 'PropertyDefinition' &&
							member.key &&
							member.key.type === 'Identifier' &&
							member.key.name === 'getPageTestId'
						) {
							const init = member.value;
							if (init && init.type === 'ArrowFunctionExpression') {
								foundPrefix = extractPrefixFromArrowFunction(init);
								if (foundPrefix) {
									return false; // Stop traversing
								}
							}
						}
					}
				}
				
				// If this class extends another class and we haven't found getPageTestId,
				// try to find it in the parent class file
				if (!foundPrefix && node.superClass) {
					// Check if superClass is an Identifier (extends BaseChatPage)
					if (node.superClass.type === 'Identifier') {
						const parentClassName = node.superClass.name;
						// Try to find the parent class file and check for getPageTestId
						// This is a heuristic - look for files with the same name pattern
						const parentPrefix = findPrefixInParentClass(parentClassName, filename, context);
						if (parentPrefix) {
							foundPrefix = parentPrefix;
							return false; // Stop traversing
						}
					}
				}
			}
			// Continue traversing if we haven't found it yet
			return foundPrefix === null;
		});
		
		return foundPrefix;
	} catch (e) {
		// If we can't find it, return null
		return null;
	}
}

/**
 * Converts testId parts to a pattern string for matching
 * @param {string[]} parts - Array of testId parts
 * @returns {string} - Pattern string (e.g., "Chat_InfoModal_Title")
 */
function partsToPattern(parts) {
	return parts.filter(Boolean).join('_');
}

/**
 * Checks if a pattern matches another pattern, treating '*' as wildcard
 * @param {string} pattern1 - First pattern
 * @param {string} pattern2 - Second pattern
 * @returns {boolean} - True if patterns match
 */
function patternsMatch(pattern1, pattern2) {
	// Exact match
	if (pattern1 === pattern2) {
		return true;
	}

	// If either contains wildcards, do pattern matching
	if (pattern1.includes('*') || pattern2.includes('*')) {
		const regex1 = new RegExp('^' + pattern1.replace(/\*/g, '.*') + '$');
		const regex2 = new RegExp('^' + pattern2.replace(/\*/g, '.*') + '$');

		// Check if pattern1 matches pattern2 or vice versa
		return regex1.test(pattern2) || regex2.test(pattern1);
	}

	return false;
}

/**
 * Checks if a concrete pattern (no wildcards) could match a pattern with wildcards
 * @param {string} concretePattern - Pattern without wildcards (e.g., "Chat_InfoModal_Title")
 * @param {string} wildcardPattern - Pattern with wildcards (e.g., "Chat_InfoModal_*")
 * @returns {boolean} - True if concrete pattern matches wildcard pattern
 */
function matchesWildcardPattern(concretePattern, wildcardPattern) {
	const regex = new RegExp('^' + wildcardPattern.replace(/\*/g, '.*') + '$');
	return regex.test(concretePattern);
}

module.exports = {
	extractTestIdFromCall,
	partsToPattern,
	patternsMatch,
	matchesWildcardPattern
};

/**
 * Utility functions for extracting testId patterns from AST nodes
 */

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
 */
function findGetPageTestIdPrefix(callNode, context) {
	if (!context) {
		return null;
	}

	try {
		const sourceCode = context.getSourceCode();
		const ast = sourceCode.ast;
		const filename = context.getFilename();

		// Look for getPageTestId method definition
		// First, try to find it in class bodies
		function findInClassBody(node, currentClass = null) {
			if (!node) {
				return null;
			}
			
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
								return extractPrefixFromArrowFunction(init);
							}
						}
					}
				}
				
				// If this class extends another class and we haven't found getPageTestId,
				// try to find it in the parent class file
				if (node.superClass && !currentClass) {
					// Check if superClass is an Identifier (extends BaseChatPage)
					if (node.superClass.type === 'Identifier') {
						const parentClassName = node.superClass.name;
						// Try to find the parent class file and check for getPageTestId
						// This is a heuristic - look for files with the same name pattern
						const parentPrefix = findPrefixInParentClass(parentClassName, filename, context);
						if (parentPrefix) {
							return parentPrefix;
						}
					}
				}
			}
			
			// Recursively search children
			for (const key in node) {
				if (key === 'parent' || key === 'range') {
					continue;
				}
				const child = node[key];
				if (Array.isArray(child)) {
					for (const item of child) {
						const result = findInClassBody(item, currentClass);
						if (result) {
							return result;
						}
					}
				} else if (child && typeof child === 'object') {
					const result = findInClassBody(child, currentClass);
					if (result) {
						return result;
					}
				}
			}
			
			return null;
		}
		
		// Try to find prefix in parent class file
		function findPrefixInParentClass(parentClassName, currentFile, context) {
			try {
				const path = require('path');
				const fs = require('fs');
				
				// Try to find the parent class file
				// Common pattern: if current file is ChatPage.ts, parent might be BaseChatPage.ts in same directory
				const currentDir = path.dirname(currentFile);
				const parentFile = path.resolve(currentDir, `${parentClassName}.ts`);
				
				if (fs.existsSync(parentFile)) {
					const content = fs.readFileSync(parentFile, 'utf8');
					// Look for getPageTestId definition - handle multiline with return statement
					// Match: getPageTestId = (...args) => { return testId('Chat', ...args); }
					// Use a simpler approach: find getPageTestId and then find testId call nearby
					const getPageTestIdIndex = content.indexOf('getPageTestId');
					if (getPageTestIdIndex !== -1) {
						// Get a chunk of text around the definition (200 chars should be enough)
						const chunk = content.substring(getPageTestIdIndex, getPageTestIdIndex + 200);
						// Look for testId('Chat', ...) in this chunk
						const testIdMatch = chunk.match(/testId\s*\(\s*['"]([^'"]+)['"]/);
						if (testIdMatch) {
							return [testIdMatch[1]];
						}
					}
				}
			} catch (e) {
				// Silently fail
			}
			return null;
		}
		
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

		return findInClassBody(ast);
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

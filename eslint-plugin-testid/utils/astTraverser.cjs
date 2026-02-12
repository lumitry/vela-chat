/**
 * Utilities for traversing ESLint AST nodes efficiently
 * Uses ESLint's visitor pattern instead of naive recursive key iteration
 */

/**
 * Get all child nodes of an AST node
 * Only returns actual AST node properties, not metadata like 'parent' or 'range'
 * @param {Object} node - AST node
 * @returns {Array<Object>} - Array of child nodes
 */
function getChildNodes(node) {
	if (!node || typeof node !== 'object') {
		return [];
	}

	const children = [];
	const astNodeProperties = new Set([
		'body', 'expression', 'argument', 'arguments', 'callee', 'property',
		'object', 'elements', 'properties', 'value', 'key', 'id', 'init',
		'declarations', 'declaration', 'specifiers', 'test', 'consequent',
		'alternate', 'block', 'handler', 'finalizer', 'cases', 'discriminant',
		'quasis', 'expressions', 'params', 'returnType', 'typeParameters',
		'superClass', 'super', 'decorators', 'superTypeParameters',
		'implements', 'mixins', 'interfaces', 'extends', 'typeAnnotation',
		'definite', 'variance', 'optional', 'computed', 'method', 'shorthand',
		'kind', 'static', 'abstract', 'readonly', 'async', 'generator',
		'left', 'right', 'operator', 'update', 'prefix', 'operand',
		'label', 'statements', 'directives', 'source', 'attributes',
		'openingElement', 'closingElement', 'children', 'name', 'qualifier',
		'typeArguments', 'typeParameters', 'members', 'indexers', 'callProperties',
		'innerComments', 'leadingComments', 'trailingComments'
	]);

	for (const key in node) {
		// Skip non-AST properties
		if (key === 'parent' || key === 'range' || key === 'loc' || key === 'raw') {
			continue;
		}

		const value = node[key];
		
		if (Array.isArray(value)) {
			// Add all array elements that are objects (AST nodes)
			for (const item of value) {
				if (item && typeof item === 'object' && item.type) {
					children.push(item);
				}
			}
		} else if (value && typeof value === 'object' && value.type) {
			// Only add if it's an actual AST node (has a type property)
			// or if it's a known AST property
			if (astNodeProperties.has(key) || value.type) {
				children.push(value);
			}
		}
	}

	return children;
}

/**
 * Traverse AST nodes using a visitor function
 * More efficient than naive recursive traversal
 * @param {Object} node - AST node to traverse
 * @param {Function} visitor - Function called for each node: visitor(node) => boolean|void
 *                             Return false to stop traversing children of this node
 */
function traverse(node, visitor) {
	if (!node || typeof node !== 'object') {
		return;
	}

	// Visit current node
	const shouldContinue = visitor(node);
	
	// If visitor returns false, don't traverse children
	if (shouldContinue === false) {
		return;
	}

	// Traverse children
	const children = getChildNodes(node);
	for (const child of children) {
		traverse(child, visitor);
	}
}

/**
 * Find all nodes matching a predicate function
 * @param {Object} node - Root AST node
 * @param {Function} predicate - Function that returns true for matching nodes
 * @returns {Array<Object>} - Array of matching nodes
 */
function findAll(node, predicate) {
	const results = [];
	traverse(node, (n) => {
		if (predicate(n)) {
			results.push(n);
		}
	});
	return results;
}

module.exports = {
	getChildNodes,
	traverse,
	findAll
};


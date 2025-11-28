const unusedTestIdInSvelte = require('./rules/unused-testid-in-svelte.cjs');
const undefinedTestIdInPageObjects = require('./rules/undefined-testid-in-page-objects.cjs');

module.exports = {
	rules: {
		'unused-testid-in-svelte': unusedTestIdInSvelte,
		'undefined-testid-in-page-objects': undefinedTestIdInPageObjects
	}
};

/**
 * Centralized regex patterns for testId extraction
 * All patterns used across the plugin are defined here to ensure consistency
 */

/**
 * Matches data-testid attributes with testId() calls
 * Example: data-testid={testId('Chat', 'InfoModal', 'Title')}
 */
const DATA_TESTID_REGEX = /data-testid\s*=\s*\{testId\s*\(([^}]+)\)\}/g;

/**
 * Matches testId prop attributes (component props, not data-testid)
 * Uses negative lookbehind to exclude data-testid
 * Example: testId={testId('Chat', 'InfoModal', 'Title')}
 */
const PROP_TESTID_REGEX = /(?:^|[^a-z-])testId\s*=\s*\{testId\s*\(([^}]+)\)\}/g;

/**
 * Matches testId() function calls
 * Example: testId('Chat', 'InfoModal', 'Title')
 */
const TESTID_CALL_REGEX = /testId\s*\(([^)]+)\)/g;

/**
 * Matches getPageTestId method definitions
 * Example: getPageTestId = (...args) => testId('Chat', ...args)
 */
const GET_PAGE_TESTID_DEF_REGEX = /getPageTestId\s*=\s*\([^)]*\)\s*=>\s*(?:\{[^}]*return\s+)?testId\s*\(([^)]+)\)/g;

/**
 * Matches getPageTestId() and getPageLocator() calls
 * Example: this.getPageLocator('Navbar', 'ControlsButton')
 */
const GET_PAGE_CALL_REGEX = /(?:this\.)?(?:getPageTestId|getPageLocator)\s*\(([^)]+)\)/g;

/**
 * Extracts arguments from testId function calls
 * Matches string literals ('Part1', "Part2") or identifiers (model.id, variable)
 * Group 1: String literal content
 * Group 2: Identifier (variable)
 */
const ARGUMENT_EXTRACTOR_REGEX = /['"]([^'"]+)['"]|(\w+(?:\.\w+)*)/g;

/**
 * Extracts only string literals (for prefix extraction)
 * Used when we only want string arguments, not variables
 */
const STRING_LITERAL_REGEX = /['"]([^'"]+)['"]/g;

module.exports = {
	DATA_TESTID_REGEX,
	PROP_TESTID_REGEX,
	TESTID_CALL_REGEX,
	GET_PAGE_TESTID_DEF_REGEX,
	GET_PAGE_CALL_REGEX,
	ARGUMENT_EXTRACTOR_REGEX,
	STRING_LITERAL_REGEX
};


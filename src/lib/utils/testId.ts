/**
 * Generates a consistent test ID for automation/testing purposes.
 * Joins the provided parts with underscores.
 *
 * @example
 * testId('UserMenu', 'Settings') // returns 'UserMenu_Settings'
 * testId('UserMenu', 'AdminPanel', 'Button') // returns 'UserMenu_AdminPanel_Button'
 */
export function testId(...parts: string[]): string {
	return parts.filter(Boolean).join('_');
}

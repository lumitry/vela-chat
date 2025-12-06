/**
 * Generate a random string of the given length.
 * @param length - The length of the string to generate.
 * @returns A random string of the given length.
 */
export function generateRandomString(length: number): string {
	return Math.random()
		.toString(36)
		.substring(2, 2 + length);
}

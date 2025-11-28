/**
 * Type for a test user
 */
export type TestUser = {
	name: string;
	email: string;
	password: string;
	role: 'admin' | 'user' | 'pending';
};

/**
 * Shared test users - credentials for users that should be pre-created
 * in the test environment (either via CSV import or API).
 */
export const SHARED_USERS: Record<string, TestUser> = {
	// TODO there should be NO shared users except for the E2EManager! all tests should create their own users! unless we need an admin user pool to avoid concurrency issues with multiple tests making users from the e2emanager user at the same time?
	preExistingAdmin: {
		name: 'E2EManager',
		email: 'test@test.com',
		password: 'test',
		role: 'admin'
	},
	nonExistentUser: {
		name: 'Non Existent User',
		email: 'non.existent@test.example.com',
		password: 'non.existent.password',
		role: 'user'
	},
	admin1: {
		name: 'Admin1 User',
		email: 'admin1@test.example.com',
		password: 'admin123',
		role: 'admin'
	},
	admin2: {
		name: 'Admin2 User',
		email: 'admin2@test.example.com',
		password: 'admin123',
		role: 'admin'
	},
	admin3: {
		name: 'Admin3 User',
		email: 'admin3@test.example.com',
		password: 'admin123',
		role: 'admin'
	},
	admin4: {
		name: 'Admin4 User',
		email: 'admin4@test.example.com',
		password: 'admin123',
		role: 'admin'
	},
	admin5: {
		name: 'Admin5 User',
		email: 'admin5@test.example.com',
		password: 'admin123',
		role: 'admin'
	},
	regular1: {
		name: 'Regular1 User',
		email: 'user1@test.example.com',
		password: 'user123',
		role: 'user'
	},
	regular2: {
		name: 'Regular2 User',
		email: 'user2@test.example.com',
		password: 'user123',
		role: 'user'
	},
	regular3: {
		name: 'Regular3 User',
		email: 'user3@test.example.com',
		password: 'user123',
		role: 'user'
	},
	regular4: {
		name: 'Regular4 User',
		email: 'user4@test.example.com',
		password: 'user123',
		role: 'user'
	},
	regular5: {
		name: 'Regular5 User',
		email: 'user5@test.example.com',
		password: 'user123',
		role: 'user'
	}
} as const;

/**
 * Generate CSV content from SHARED_USERS.
 * Format: Name,Email,Password,Role
 */
export function generateUsersCSV(): string {
	const header = 'Name,Email,Password,Role\n';
	const rows = Object.values(SHARED_USERS)
		.map((user) => `${user.name},${user.email},${user.password},${user.role}`)
		.join('\n');
	return header + rows;
}

/**
 * Generate a random valid user. Mostly useful if you don't need a predictable user with a sensible name and email to be identified by.
 * @returns A random valid user
 */
export function generateRandomValidUser(): TestUser {
	const name = `Test User ${Date.now()}`;
	const email = `${name.toLowerCase().replace(/ /g, '.')}@test.example.com`;
	const password = 'Sup3rS3cur3P455w0rd'; // in case we add proper validation later
	return {
		name,
		email,
		password,
		role: 'user'
	};
}

/**
 * Sanitize a string to be safe for use in email addresses and user names.
 * Removes or replaces characters that could cause issues.
 * @param str The string to sanitize
 * @returns A sanitized string safe for use in emails/names
 */
function sanitizeForUserIdentifier(str: string): string {
	return str
		.toLowerCase()
		.replace(/[^a-z0-9\s-]/g, '') // Remove special characters except spaces and hyphens
		.replace(/\s+/g, '-') // Replace spaces with hyphens
		.replace(/-+/g, '-') // Replace multiple hyphens with single hyphen
		.replace(/^-|-$/g, '') // Remove leading/trailing hyphens
		.substring(0, 50); // Limit length to prevent overly long identifiers
}

/**
 * Generate a user with test context metadata embedded in the name and email.
 * This helps prevent collisions when tests run in parallel and makes it easier
 * to identify which test created which user.
 *
 * @param testInfo Test info object from Playwright (contains test title, suite title, etc.)
 * @param customIdentifier Optional custom identifier to append to the user name/email.
 *                         Useful when a test needs to create multiple users and track them.
 * @returns A test user with context-aware name and email
 */
export function generateUserWithTestContext(
	testInfo: { title: string; parent?: { title: string } },
	customIdentifier?: string
): TestUser {
	// Build identifier from test context
	const parts: string[] = [];

	// Add suite title if available (nested describes create a parent chain)
	let parent = testInfo.parent;
	const suiteTitles: string[] = [];
	while (parent) {
		suiteTitles.unshift(parent.title);
		parent = parent.parent;
	}
	if (suiteTitles.length > 0) {
		parts.push(...suiteTitles.map(sanitizeForUserIdentifier));
	}

	// Add test title
	parts.push(sanitizeForUserIdentifier(testInfo.title));

	// Add custom identifier if provided
	if (customIdentifier) {
		parts.push(sanitizeForUserIdentifier(customIdentifier));
	}

	// Add timestamp for additional uniqueness (in case of exact same test names)
	const timestamp = Date.now();
	const baseIdentifier = parts.length > 0 ? parts.join('-') : 'test';
	const name = `${baseIdentifier}-${timestamp}`;
	const email = `${name}@test.example.com`;
	const password = 'Sup3rS3cur3P455w0rd'; // in case we add proper validation later

	return {
		name,
		email,
		password,
		role: 'user'
	};
}

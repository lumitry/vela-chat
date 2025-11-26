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
	badEmailUser: {
		name: 'Bad Email User',
		email: 'bad.email at test dot example dot com',
		password: 'bad.email.password',
		role: 'user'
	},
	badPasswordUser: {
		name: 'Bad Password User',
		email: 'bad.password@test.example.com',
		password: '', // as of right now, the backend DOES allow empty passwords, but the frontend prevents it unless you use inspect element to remove the required attribute
		role: 'user'
	},
	// we like to have fun around here
	badNameUser: {
		name: '', // name is required
		email: 'you_give_love@bad.name',
		password: 'j0vi4l_p455w0rd',
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

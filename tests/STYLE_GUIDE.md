# Playwright E2E Testing Style Guide

## General Considerations

- Tests should be as deterministic as reasonably possible given the problem domain.
- Use the page object model pattern to represent the UI as objects that can be interacted with.

## Naming Conventions

### Methods

Page object methods fall into two categories: **low-level operations** and **high-level user actions**.

#### Low-Level Operations

These methods represent direct interactions with UI elements. They should follow verb-based naming:

- **Assertions**: All methods that compare the value of a UI element with an expected value should be named `assert*`.
- **Clickers**: All methods that perform a simple click on a UI element should be named `click*`. Use this for buttons that don't trigger complex workflows (e.g., `clickTabButton()` for switching tabs).
- **Setters**: All methods that set the value of a UI element should be named `set*`. (e.g. for text inputs)
- **Selectors**: All methods that choose an option from a dropdown should be named `select*`.
- **Uploaders**: All methods that upload a file to a UI element should be named `upload*`.
- **Getters**: All methods that get the value of a UI element should be named `get*`. The same goes for methods that store the value into a holder variable.

#### High-Level User Actions

These methods represent complete user workflows or actions that have side effects beyond a single element interaction. They should use action-oriented names that describe what the user is doing, not how it's implemented:

- **Form submissions**: Use `save()`, `saveAndReturn()`, `saveAndContinue()`, `saveAndClose()`, `submit()`, etc. These methods may click buttons, but they represent the user's intent to save/submit a form, not just clicking a button.
- **Navigation actions**: Use `signIn()`, `signUp()`, `navigateTo()`, etc. These represent complete user workflows.
- **State changes**: Use `switchMode()`, `toggle()`, etc. when the action represents a meaningful state change.

**When to use which?**

- If a method only clicks a single button with no side effects (like closing a modal), use `click*`.
- If a method represents a user workflow (like saving a form and navigating, or signing in), use an action-oriented name.
- If you find yourself writing `click*And*` or `click*Then*`, it's probably a high-level action and should be renamed.

### Variables

- All variables corresponding to pageobjects or components should be named after the object or component, e.g. `loginPage`, `userMenu`, `toast`, etc.
- All static variables shall be written in uppercase with underscores between words, e.g. `MAX_UPLOAD_SIZE_MB`, `DEFAULT_TIMEOUT_MS`, etc.
- Temporary variables (e.g. for loop counters and catch blocks) may be short and abbreviated but still must indicate what they are for. So instead of using `i`, make an effort to use `row` or `idx` or `err` at the very least.
  - Better yet, in the case of an error, use something that describes the error, e.g. `catch (noUsersFoundError) { ... }`.

### Classes

There are four main types of classes:

- **Page objects:** Represent pages and tabs/components that appear inside pages. (Sometimes component objects are referred to as subsets of page objects, as I'm doing here, and other times they're referred to as separate entities. They serve the same broad purpose, so I'm combining them in this case.)
  - Page object names must end in `Page` or `Tab`, e.g. `AdminUsersPage`, `AdminSettingsGeneralTab`.
  - Component objects must end in their component type, e.g. since `AddUserModal` is a modal, it should end in `Modal`.
- **Test classes:** Contain the actual tests. These tend to be named after the feature(s) they test, and the logic inside of them should be rather minimal; the page objects should do the heavy lifting.
  - Test classes must end in `.test.ts`.
- **Utility classes:** Contain utility functions that are used across many tests/page objects. For example, there is a utility class that stores the users used in the tests.
  - TODO: actually if we do users on a per-test basis we don't need that for anything other than a class definition
  - No particular naming convention for utility classes.
- **Fixtures:** Contain the fixtures for the tests.
  - No particular naming convention for fixture classes.

## Directory Structure

- The `tests` directory should contain the following subdirectories:
  - `e2e`: Contains the end-to-end tests. These are the files that actually "describe" the behavior exhibited in the tests.
    - TODO: there should probably be sub-directories but i've got no clue what that structure should be like!
  - `pages`: Contains the page objects, tabs, and components that only appear on one page. For example, `AddUserModal.ts` only appears on the `AdminUsersPage`, so it is underneath the `pages` directory, not the `components` directory.
    - There may be sub-directories for paths that have multiple pageobjects associated, e.g. `pages/Admin/`.
  - `components`: Contains the base components, as well as components that appear on many pages.
  - `data`: Contains the data for the tests, and/or scripts that yield data.
  - `utils`: Contains the utility functions for the tests.
  - `fixtures`: Contains the fixtures for the tests.

## Other Code Style Considerations

### Selectors

- Use the `getByTestId` method to select elements by their test ID.
- If an element does not already have a test ID, **add one to it!!** As in, modify the `.svelte` file to give it a test ID. You need not — and should not — rely on flakier DOM-based selectors unless absolutely necessary (e.g. for accessing very specific elements that would be hard to reach with a test ID alone).
- Test ID naming should be done using the `testId` helper function, and should be consistent with other test IDs on the same page and in the same part of the app.
  - Keep them concise.
  - Components of the test ID slug should generally indicate the path the element is in, e.g. `Navbar_UserMenu_Button`, `AdminSettings_Users_AddUserButton`, etc.
  - Test IDs should be unique unless there is no chance that two elements with the same test ID slug will ever appear on the same page. (e.g. some things in the navbar can be used in all three navbar components since only one navbar appears at a time.)
  - Test IDs should indicate what they are, e.g. a button, dropdown, input, etc.

### Comments

- For any non-obvious/non-trivial method, there should be a TSDoc comment (docstring/javadoc) that explains what it does.
- For any variable whose purpose is not obvious from its name, use a TSDoc comment to explain it.
  - **WHY TSDOC?** - Because it appears in IntelliSense hover tooltips! This is a major DX win, even if it bloats the LoC a bit.
- Methods that change the current page should mention that in their TSDoc comment.
- Avoid unnecessary comments. If the code is self-explanatory, don't comment it.

### Typing

- All code should be properly typed. We use TypeScript for a reason.
- Numbers should be represented as numbers for as long as possible. Don't convert to strings unless you absolutely have to.

### Assertions

- Utilize soft assertions whenever relevant (to avoid the whole test failing if one assertion fails).
- Use custom expect messages whenever it would be helpful.

### General

- Page object constructors should only take in the `page` parameter unless there is a very good reason to do otherwise (e.g. if a page needs to be given information about the context it's running in, or a reference to the information on the page like a LLM name, etc.)
- Page object methods should almost always be async.
- Fields (even private ones) should be declared above the constructor.
- Avoid overcompaction; just because something can fit in one line doesn't mean it should.
- Four spaces for indentation. Your editor probably converts tabs to 4 spaces automatically!
- Install/use the Prettier extension for your editor and configure it to format your code automatically. Same for ESLint.
- Bracing: Nobody cares how you handle this. I personally prefer same-line bracing, but if you're the type to know the names of bracing styles, I'm not going to stop you.
- Dangling conditionals: Don't do this. Please use bracing even if it's just one line.
- If you have to create multiple similar sets of variable as the params to a few different methods, consider creating a class to represent the set of variables.
- Keep test code DRY.
- Keep methods small and focused. Use helpers if needed.

### Inside Tests

- Use `test.beforeEach` and `test.afterEach` for per-test setup and teardown.
- Use `test.describe` for grouping tests into logical sets.
- Prefer `await` when calling many async methods in a row over `then` chaining.

RATIONALE:

I personally don't like the pattern of:

```typescript
await new loginPage(page)
	.login(user)
	.then(() => new HomePage(page))
	.then((homePage) => homePage.clickUserMenuButton())
	.then((homePage) => homePage.userMenu.clickAdminPanel());
// etc.
```

It's probably more powerful to use `then` chaining, but as a matter of my own personal preference, I've elected to use `await` instead. It lets the test code read more like synchronous code, which is easier to skim and reason about.

If there's a concrete reason to use `then` chaining, that's fine, but it should be rare.

## General Structure of Tests

Tests should use fixtures for setup and teardown. See [Fixtures](#fixtures) for more details.

Tests should use their own users, probably created via a fixture? **TODO** how do we do this? also what's the idiomatic way of creating users? UI or API? I don't want to do database seeding because it's slow and schema-dependent. We're trying to test e2e, so UI makes the most sense to me.

## Recommendations

- The Playwright extension for VSCode is very useful!

## General Playwright Testing Information

Playwright has great [documentation](https://playwright.dev/docs/intro), but there's so much of it that it can be overwhelming to a beginner. Below are my notes on how to use Playwright effectively.

### Test File Layout & `test.describe`

Use [`test.describe`](https://playwright.dev/docs/api/class-test#test-describe) to create groups of related tests. They share hooks (`beforeEach`/`afterEach`) and show nested sections in reports.

The minimal example:

```typescript
test.describe('two tests', () => {
	test('one', async ({ page }) => {
		// ...
	});

	test('two', async ({ page }) => {
		// ...
	});
});
```

You can integrate `test.use` here to apply common settings to multiple tests. In this example, they do so without passing a name (an anonymous group):

```typescript
test.describe(() => {
	test.use({ colorScheme: 'dark' });
	// ...
});
```

Also, [test tags](https://playwright.dev/docs/test-annotations#tag-tests) can be applied:

```typescript
import { test, expect } from '@playwright/test';

test.describe(
	'two tagged tests',
	{
		tag: '@smoke'
	},
	() => {
		test('one', async ({ page }) => {
			// ...
		});

		test('two', async ({ page }) => {
			// ...
		});
	}
);
```

As well as [test annotations](https://playwright.dev/docs/test-annotations):

```typescript
import { test, expect } from '@playwright/test';

test.describe(
	'two annotated tests',
	{
		annotation: {
			type: 'issue',
			description: 'https://github.com/microsoft/playwright/issues/23180'
		}
	},
	() => {
		test('one', async ({ page }) => {
			// ...
		});

		test('two', async ({ page }) => {
			// ...
		});
	}
);
```

Finally, you can add a `callback` function that is run immediately when calling `test.describe()`. Any tests declared in that callback will belong to the group.

#### `test.describe.configure()`

Configures the enclosing scope. Can be executed either on the top level _or_ inside a describe!

For example, if you want to run all tests in the file in parallel:

```typescript
// Run all the tests in the file concurrently using parallel workers.
test.describe.configure({ mode: 'parallel' });
test('runs in parallel 1', async ({ page }) => {});
test('runs in parallel 2', async ({ page }) => {});
```

Or configure retries/timeout:

```typescript
// Each test in the file will be retried twice and have a timeout of 20 seconds.
test.describe.configure({ retries: 2, timeout: 20_000 });
test('runs first', async ({ page }) => {});
test('runs second', async ({ page }) => {});
```

You can even get fancy with it:

```typescript
test.describe.configure({ mode: 'parallel' });

test.describe('A, runs in parallel with B', () => {
	test.describe.configure({ mode: 'default' });
	test('in order A1', async ({ page }) => {});
	test('in order A2', async ({ page }) => {});
});

test.describe('B, runs in parallel with A', () => {
	test.describe.configure({ mode: 'default' });
	test('in order B1', async ({ page }) => {});
	test('in order B2', async ({ page }) => {});
});
```

### `test.use`

**TODO** write a bit about test.use!

`test.use({ ... })` configures per-test options like viewport and storage state. See [test.use docs](https://playwright.dev/docs/test-use-options) for more details.

### Fixtures

[Fixtures](https://playwright.dev/docs/test-fixtures#introduction) are reusable setup objects, used to establish the environment for each test, giving the test everything it needs and nothing else.

By default, Playwright ships with `page`, `context`, `browser`, `browserName`, and `request`.

Fixtures are recommended over before/after hooks because they:

- Encapsulate setup/teardown in the same place
- Are reusable in different tests (like helpers)
- Are composable!
- Are flexible. Tests can use combinations of fixtures to precisely tailor their environment to their needs. And, since fixtures include teardown, they can do so without affecting other tests.
- Simplify grouping, since you can use fixtures to group tests by their meaning rather than by wrapping them in `describe`s that set up their environment (remember, `describe`s share hooks!)

Example from the docs:

```typescript
import { test as base } from '@playwright/test';
import { TodoPage } from './todo-page';

// Extend basic test by providing a "todoPage" fixture.
const test = base.extend<{ todoPage: TodoPage }>({
	todoPage: async ({ page }, use) => {
		const todoPage = new TodoPage(page);
		await todoPage.goto();
		await todoPage.addToDo('item1');
		await todoPage.addToDo('item2');
		await use(todoPage); // this is where the tests run!
		await todoPage.removeAll(); // this is teardown
	}
});

test('should add an item', async ({ todoPage }) => {
	await todoPage.addToDo('my item');
	// ...
});

test('should remove an item', async ({ todoPage }) => {
	await todoPage.remove('item1');
	// ...
});
```

Here, they extend the `test` to provide a `todoPage` fixture that defines setup, an entrypoint for the tests to run at (`await use(todoPage)`), and teardown.

Of course, fixtures need not be defined in the same file that the tests are defined in. In fact, it's better that they are not!

### Other Notes

- Re-use locators whenever possible to avoid unnecessary querying.
- You can use `expect(locator).toHaveScreenshot()` to make the test give you a screenshot.

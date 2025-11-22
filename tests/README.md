# VelaChat E2E Tests

This directory contains the end-to-end tests for VelaChat.

## Running the tests

To run the tests, use the following command:

```bash
npm run test:e2e
```

or:

```bash
npx playwright test
```

## Writing tests

We use Playwright for our E2E tests. The tests themselves are in the `tests/e2e` directory, and the page objects are in the `tests/pages` directory. Page objects are used to represent the various pages and components in the application, and are used to interact with the application. (We use the page object model pattern for this.)

## TODOs

- [ ] STYLE GUIDE FOR TESTS/PAGE OBJECTS!
  - page object names must end in `Page` or `Tab`, e.g. `AdminUsersPage`, `AdminSettingsGeneralTab`.
  - component objects must end in their component type, e.g. since `AddUserModal` is a modal, it should end in `Modal`.
  - page object methods should be named after the verb/action they perform, e.g. `clickAddUserButton`, `clickSaveButton`, etc.
  - page object methods should be async and return void.
  - location of fields should be above the constructor (i don't follow this one yet i don't think, so i should also fix that!)
- [ ] DIRECTORY STRUCTURE EXPLANATION
- [ ] TEST/CLASS NAMING CONVENTIONS
- [ ] actually write a bunch of tests!
- [ ] add to mini-mediator (streaming support, etc.) (could also mock the API in Playwright maybe, but I'd prefer to use real backend API connections!)
- [ ] Write a script to automate the initial database setup (create pre-existing user `dev@example.com`, add model connections, etc.)
- [ ] Figure out how the tests will run on other people's machines (e.g. CI/CD, etc.)
- [ ] how will the user pool work?
- [ ] how will the precedence of test cases work? i.e. how will we specify the order they run in, if necessary?

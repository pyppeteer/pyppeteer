# Contribution guidelines

Contributions are welcome as long as they follow core rule of the project:

The API of pyppeteer should [__match the API of puppeteer__](https://github.com/puppeteer/puppeteer) as closely as possible without sacrificing python too much.
ie keep public API keywords such as method names, arguments, class names etc. as they are in puppeteer version.

Other than that the contributions should remain as pythonic as possible and pass linting and code tests.

Changes worthy of a changelog entry should get one - simply follow the existing format in CHANGELOG.md

## Maintainers - creating a release

 - Make sure all relevant changes have been recorded in the changelog
 - Ensure that code is properly tested
 - Bump the version in `pyproject.toml`, then tag the release in git
 - Run `poetry build`
 - Run `poetry publish`

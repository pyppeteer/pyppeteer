python_version := "3.10"
codeartifact_domain := "hungryroot"
codeartifact_domain_owner := "533267136032"
codeartifact_pip_repository := "hungryroot"
codeartifact_twine_repository := "private-py"
aws_sso_login_status := `aws sts get-caller-identity &> /dev/null; echo $?`

ensure-aws-login:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ {{aws_sso_login_status}} -ne 0 ] ; then just aws-login ; fi

aws-login:
    #!/usr/bin/env bash
    set -euo pipefail
    aws sso login
    result=$?
    if [ $result -eq 0 ] ; then echo '☁️ Logged into AWS' ; else echo '💀 AWS login failed' ; exit $result; fi
    just do-codeartifact-login

@codeartifact-login: ensure-aws-login
    just do-codeartifact-login

do-codeartifact-login:
    #!/usr/bin/env bash
    set -euo pipefail
    aws codeartifact login --tool pip --domain {{ codeartifact_domain }} --domain-owner {{ codeartifact_domain_owner }} --repository {{ codeartifact_pip_repository }}
    result=$?
    if [ $result -eq 0 ] ; then echo '🐍 Logged into CodeArtifact' ; else echo '💀 CodeArtifact login failed' ; exit $result; fi

@pip-install: codeartifact-login
    just do-pip-install

@do-pip-install:
    pip install -e ".[dev]"

@setup: pip-install

lint:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -f ".git/hooks/pre-commit" ]; then
        pre-commit install
    fi
    pre-commit run -a

# Download Chromium browser for tests
@install-browser:
    pyppeteer-install

@test *args: install-browser
    pytest -n 6 {{ args }}

@test-coverage: install-browser
    pytest -n 6 --cov=pyppeteer --cov-report=html

@publish: pip-install
    just do-publish

do-publish:
    #!/usr/bin/env bash
    set -e
    python -m build
    TWINE_USERNAME=aws \
    TWINE_PASSWORD=`aws codeartifact get-authorization-token --domain {{ codeartifact_domain }} --domain-owner {{ codeartifact_domain_owner}} --query authorizationToken --output text` \
    TWINE_REPOSITORY_URL=`aws codeartifact get-repository-endpoint --domain {{ codeartifact_domain }} --domain-owner {{ codeartifact_domain_owner }} --repository {{ codeartifact_twine_repository}} --format pypi --query repositoryEndpoint --output text` \
    twine upload --repository codeartifact dist/*

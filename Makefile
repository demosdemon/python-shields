ifeq ($(VIRTUAL_ENV), )
VIRTUAL_ENV := $(shell pipenv --venv 2>/dev/null)
endif

ifeq ($(VIRTUAL_ENV), )
VIRTUAL_ENV := $(CURDIR)/.venv
endif

ifeq ($(PLATFORM_APP_DIR), )
PYTHON ?= $(VIRTUAL_ENV)/bin/python
else
PYTHON ?= $(shell command -v python)
endif

python_code := shields tests scripts

help:
	@echo 'Usage: make <target>'
	@echo '  Where <target> is one of:'
	@echo '    all         Execute all build operations.'
	@echo '    clean       Delete the generated output.'
	@echo '    debug-make  Print all of the `make` variables for debugging.'
	@echo '    format      Execute black and isort formatters on python code.'
	@echo '    help        Show this message and exit.'
	@echo '    lock        Regenerate the lockfile.'
	@echo '    platform    Executes the tasts require for a Platform.sh build.'
	@echo '    sync        Synchronize the virtual environment with the lockfile.'
	@echo '    test        Executes py.test unit tests.'

debug-make:
	@echo "CURDIR      := $(CURDIR)"
	@echo "VIRTUAL_ENV := $(VIRTUAL_ENV)"
	@echo "PYTHON      := $(PYTHON)"
	@echo "python_code := $(python_code)"

Pipfile.lock: Pipfile
	pipenv lock --pre

all: lock sync format test

clean:
	git clean -xdf -e .env -e .venv

format requirements.txt: $(PYTHON)
	$(PYTHON) "$(CURDIR)/scripts/sync-requirements.py" -r "$(CURDIR)/requirements.txt" -p "$(CURDIR)/Pipfile"
	$(PYTHON) -m isort --recursive $(python_code)
	$(PYTHON) -m black $(python_code)

lock: Pipfile.lock

platform: make-debug
	pipenv install --deploy --system

sync $(PYTHON): Pipfile.lock
	pipenv sync --dev
	pipenv clean
	@touch $(PYTHON)

test: $(PYTHON)
	$(PYTHON) -m pytest $(python_code)

.PHONY: all clean debug-make format help lock platform sync test

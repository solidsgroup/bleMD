PYTHON ?= python3
BLENDER ?= /opt/blender-4.2.2-linux-x64/blender
BLEND ?=

.PHONY: help build test install reinstall run dev uninstall clean
.DEFAULT_GOAL := help

help:
	@echo 'make dev        Test, install, and open Blender with the updated add-on'
	@echo 'make test       Build and smoke-test in an isolated Blender profile'
	@echo 'make install    Build, install, and enable in your Blender preferences'
	@echo 'make run        Open Blender (optionally BLEND=/path/to/scene.blend)'
	@echo 'make build      Create bleMD.zip'
	@echo 'make uninstall  Remove bleMD from your Blender preferences'
	@echo 'Override Blender with BLENDER=/path/to/blender'

build:
	$(PYTHON) scripts/workflow.py build

test:
	$(PYTHON) scripts/workflow.py --blender "$(BLENDER)" test

install reinstall:
	$(PYTHON) scripts/workflow.py --blender "$(BLENDER)" install

run:
	$(PYTHON) scripts/workflow.py --blender "$(BLENDER)" run $(if $(BLEND),--blend "$(BLEND)")

dev:
	$(PYTHON) scripts/workflow.py --blender "$(BLENDER)" dev $(if $(BLEND),--blend "$(BLEND)")

uninstall:
	$(PYTHON) scripts/workflow.py --blender "$(BLENDER)" uninstall

clean:
	$(PYTHON) -c 'from pathlib import Path; Path("bleMD.zip").unlink(missing_ok=True)'

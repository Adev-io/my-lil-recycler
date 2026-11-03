RACK_DIR ?= ../..
FLAGS += -Icore
SOURCES += $(wildcard src/*.cpp)
DISTRIBUTABLES += res LICENSE
include $(RACK_DIR)/plugin.mk

test:
	$(MAKE) -C tests
title-test:
	$(MAKE) -C tests title
.PHONY: test title-test

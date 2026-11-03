CXX ?= g++
# the plugin's own flags (Rack's compile.mk), with its -march per CPU so the tests also run on Apple Silicon
MARCH := $(if $(filter x86_64 amd64,$(shell uname -m)),-march=nehalem,-march=armv8-a+fp+simd)
CXXFLAGS ?= -std=c++11 -O3 -funsafe-math-optimizations $(MARCH) -Wall -Wextra -I../core
BIN := ../build/tests.exe

all: run

$(BIN): test.cpp $(wildcard *.h) $(wildcard ../core/*.h)
	@mkdir -p ../build
	$(CXX) $(CXXFLAGS) test.cpp -o $(BIN)

run: $(BIN)
	$(BIN)

# title.cpp needs jansson: Rack's, through the SDK's import library (Windows), run with Rack's folder on PATH
RACK_APP ?= /c/Program Files/VCV/Rack2Free
../build/title.exe: title.cpp ../src/Title.hpp check.h
	@mkdir -p ../build
	$(CXX) -std=c++11 -O2 -Wall -Wextra -I$(RACK_DIR)/dep/include title.cpp -L$(RACK_DIR) -lRack -o $@

title: ../build/title.exe
	PATH="$(RACK_APP):$$PATH" ../build/title.exe

.PHONY: all run title

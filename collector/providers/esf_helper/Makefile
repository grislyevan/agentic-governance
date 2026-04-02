# Makefile for esf_helper (macOS Endpoint Security Framework helper)
# Requires macOS 10.15+ and root for execution.

CC = clang
CFLAGS = -O2 -Wall -Wextra
LDFLAGS = -framework Foundation -framework CoreFoundation -lEndpointSecurity -lbsm
TARGET = esf_helper
SRC = esf_helper.m

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
    # macOS: build
    $(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC) $(LDFLAGS)
else
    $(TARGET):
	@echo "Warning: esf_helper requires macOS (Darwin). Skipping build."
endif

PREFIX ?= /usr/local

.PHONY: clean install sign universal sign-universal

clean:
	rm -f $(TARGET)

install: $(TARGET)
	@if [ -f $(TARGET) ]; then \
		install -d $(DESTDIR)$(PREFIX)/bin 2>/dev/null || true; \
		install -m 755 $(TARGET) $(DESTDIR)$(PREFIX)/bin/$(TARGET); \
	fi

sign: $(TARGET)
	@if [ -z "$(CODESIGN_IDENTITY)" ]; then \
		echo "CODESIGN_IDENTITY not set — skipping code signing"; \
		exit 0; \
	fi
	codesign --entitlements esf_helper.entitlements --sign "$(CODESIGN_IDENTITY)" --timestamp --options runtime esf_helper

# universal: build fat binary for CI matrix (arm64 + x86_64).
# Local builds should use the default target.
universal:
	$(CC) $(CFLAGS) -arch arm64  -o esf_helper_arm64  $(SRC) $(LDFLAGS)
	$(CC) $(CFLAGS) -arch x86_64 -o esf_helper_x86_64 $(SRC) $(LDFLAGS)
	lipo -create -output esf_helper esf_helper_arm64 esf_helper_x86_64
	rm -f esf_helper_arm64 esf_helper_x86_64

sign-universal: universal sign

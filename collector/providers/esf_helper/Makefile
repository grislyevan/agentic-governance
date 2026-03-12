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

.PHONY: clean install

clean:
	rm -f $(TARGET)

install: $(TARGET)
	@if [ -f $(TARGET) ]; then \
		install -d $(DESTDIR)$(PREFIX)/bin 2>/dev/null || true; \
		install -m 755 $(TARGET) $(DESTDIR)$(PREFIX)/bin/$(TARGET); \
	fi

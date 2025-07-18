#!/usr/bin/env bash

# Build, install shebang, link globally and refresh shell
echo "Building project..."
npm run build

echo "Linking CLI globally..."
npm link

# Refresh shell hash for zsh/bash
echo "Refreshing shell..."
hash -r || true

echo "Setup complete. You can now run 'bernerspace' commands."
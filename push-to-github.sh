#!/bin/bash
# This script will help push your changes to GitHub
# Run this in VS Code's integrated terminal

cd /home/aryan/Desktop/sargamAi/sargambackend

# Check git status
echo "=== Git Status ==="
git status

# Push to GitHub
echo ""
echo "=== Pushing to GitHub ==="
git push origin main

echo ""
echo "=== Done ==="
#!/bin/bash
# Creates the public GitHub Pages site for Google's Branding page.
set -e
GH=~/.local/bin/gh; U=krishnaaadvisory-coder; R=$U.github.io
cd ~/Desktop/server/clipper/site
$GH repo create $R --public --description "Homepage and privacy policy for Clipper"
$GH auth setup-git
git remote add origin https://github.com/$U/$R.git 2>/dev/null || true
git push -u origin main
$GH api -X POST repos/$U/$R/pages -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 || true
echo; echo "Site: https://$R  (live in 1-2 min)"

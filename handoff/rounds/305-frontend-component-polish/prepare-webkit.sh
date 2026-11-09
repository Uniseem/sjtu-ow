#!/usr/bin/env bash
set -euo pipefail
tool=/srv/build/sjtu-ow/305-webkit-1.63.0
mkdir -p "$tool"
if [ ! -f "$tool/package.json" ]; then
  printf '%s\n' '{"private":true,"name":"sjtuow-305-browser-tool","version":"1.0.0"}' > "$tool/package.json"
fi
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --prefix "$tool" --ignore-scripts --no-audit --no-fund --save-exact playwright@1.63.0
node -e 'const p=require(process.argv[1]); if(p.version!=="1.63.0" || p.license!=="Apache-2.0") process.exit(1); console.log("TEST-TOOL",p.version,p.license)' "$tool/node_modules/playwright/package.json"
docker pull mcr.microsoft.com/playwright:v1.63.0-noble
docker image inspect mcr.microsoft.com/playwright:v1.63.0-noble --format '{{json .RepoDigests}}'

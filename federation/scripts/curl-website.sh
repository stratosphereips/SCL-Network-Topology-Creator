#!/bin/bash
# curl-website.sh - Fetch a website and its images only (no deep crawling)
# Usage: ./curl-website.sh <url>

URL="$1"

if [[ -z "$URL" ]]; then
    echo "Usage: $0 <url>"
    exit 1
fi

# Fetch the main page with browser-like user-agent
curl -s -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" "$URL" > /dev/null 2>&1

# Extract image URLs and fetch them (shallow - just images, no CSS/JS/links)
curl -s -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" "$URL" | \
    grep -oP 'src=["'"'"']\K[^"'"'"']+\.(jpg|jpeg|png|gif|svg|webp)' | \
    while read -r img_url; do
        # Handle relative vs absolute URLs
        if [[ "$img_url" == http* ]]; then
            FULL_URL="$img_url"
        elif [[ "$img_url" == //* ]]; then
            FULL_URL="https:${img_url}"
        else
            BASE_URL=$(echo "$URL" | sed 's|/[^/]*$||')
            FULL_URL="${BASE_URL}/${img_url}"
        fi
        curl -s -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" "$FULL_URL" > /dev/null 2>&1 &
    done

wait
exit 0

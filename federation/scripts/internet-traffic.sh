#!/bin/bash
# internet-traffic.sh - Simulate casual user internet traffic
# Usage: ./internet-traffic.sh <type>
# Types: google, wikipedia, reddit

TYPE="${1:-google}"

case "$TYPE" in
    google)
        # Fetch Google homepage
        curl -s -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
            "https://www.google.com/" > /dev/null 2>&1

        # Fetch some images/CSS/JS that Google loads
        curl -s -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" \
            "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png" > /dev/null 2>&1
        ;;
    reddit)
        # Open the Reddit main page, wait 30 seconds, then "reload" it —
        # mimics a user reading their feed for half a minute.
        UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        curl -s -A "$UA" -L "https://www.reddit.com/" > /dev/null 2>&1
        sleep 30
        curl -s -A "$UA" -L "https://www.reddit.com/" > /dev/null 2>&1
        ;;
    wikipedia)
        # Fetch Wikipedia main page
        curl -s -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
            "https://en.wikipedia.org/wiki/Special:Random" > /dev/null 2>&1

        # Extract and fetch a few images from the page
        curl -s -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" \
            "https://en.wikipedia.org/wiki/Main_Page" | \
            grep -oP 'src=["'"'"']\K[^"'"'"']+\.(jpg|jpeg|png|gif|svg|webp)' | head -3 | \
            while read -r img_url; do
                if [[ "$img_url" == //* ]]; then
                    FULL_URL="https:${img_url}"
                elif [[ "$img_url" == http* ]]; then
                    FULL_URL="$img_url"
                else
                    FULL_URL="https://upload.wikimedia.org/${img_url}"
                fi
                curl -s -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" "$FULL_URL" > /dev/null 2>&1 &
            done
        ;;
    *)
        echo "Unknown type: $TYPE"
        exit 1
        ;;
esac

wait
exit 0

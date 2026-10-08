#!/bin/bash
# internet-traffic.sh - Simulate casual user internet traffic
# Usage: ./internet-traffic.sh <type>
# Types: google, wikipedia, reddit, images, github, news

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
    images)
        # Content-heavy image browsing: a random Wikimedia file page plus a
        # few images linked from Wikipedia's front page.
        UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        curl -s -A "$UA" -L "https://commons.wikimedia.org/wiki/Special:Random/File" > /dev/null 2>&1
        curl -s -A "$UA" "https://en.wikipedia.org/wiki/Main_Page" | \
            grep -oE 'src="[^"]+\.(jpg|jpeg|png|svg|webp)"' | sed 's/src="//;s/"//' | head -3 | \
            while read -r img; do
                case "$img" in //*) U="https:$img";; http*) U="$img";; *) U="https://en.wikipedia.org$img";; esac
                curl -s -A "$UA" "$U" > /dev/null 2>&1 &
            done
        ;;
    github)
        # A developer browsing GitHub: homepage, trending, then a few of the
        # trending repositories (lots of HTML + assets).
        UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        curl -s -A "$UA" -L "https://github.com/" > /dev/null 2>&1
        curl -s -A "$UA" -L "https://github.com/trending" | \
            grep -oE 'href="/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"' | sed 's/href="//;s/"//' | \
            sort -u | head -3 | \
            while read -r repo; do
                curl -s -A "$UA" -L "https://github.com${repo}" > /dev/null 2>&1 &
            done
        ;;
    news)
        # Reading the news: BBC front page, then a few linked articles.
        UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        curl -s -A "$UA" -L "https://www.bbc.com/news" > /dev/null 2>&1
        curl -s -A "$UA" -L "https://www.bbc.com/news" | \
            grep -oE '/news/[a-z0-9-]+' | sort -u | head -3 | \
            while read -r path; do
                curl -s -A "$UA" -L "https://www.bbc.com${path}" > /dev/null 2>&1 &
            done
        ;;
    *)
        echo "Unknown type: $TYPE"
        exit 1
        ;;
esac

wait
exit 0

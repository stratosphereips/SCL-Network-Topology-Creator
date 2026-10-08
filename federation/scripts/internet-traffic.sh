#!/bin/bash
# internet-traffic.sh - Simulate casual user internet traffic.
# Usage: ./internet-traffic.sh <type>
# Types: google, wikipedia, reddit, images, github, news
#
# The multi-page types (wikipedia, github, news, images) open pages one at a
# time with randomized pauses in between, like a bored person scrolling,
# rather than hammering every URL at once.

TYPE="${1:-google}"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Human-ish pause between page loads: jitter MIN RANGE -> MIN..MIN+RANGE-1 s.
jitter() { sleep $(( RANDOM % ${2:-10} + ${1:-3} )); }

# Fetch a URL (follow redirects), silently.
visit() { curl -s -A "$UA" -L "$1" > /dev/null 2>&1; }

case "$TYPE" in
    google)
        visit "https://www.google.com/"
        jitter 2 6
        visit "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png"
        ;;
    reddit)
        # Open the feed, read for ~30s, reload - a user skimming their feed.
        visit "https://www.reddit.com/"
        sleep 30
        visit "https://www.reddit.com/"
        ;;
    wikipedia)
        # A few random articles, pausing between each like someone reading.
        for _ in 1 2 3 4; do
            visit "https://en.wikipedia.org/wiki/Special:Random"
            jitter 4 12
        done
        ;;
    github)
        # Homepage, trending, then open a few trending repos one at a time.
        visit "https://github.com/"
        jitter 3 8
        repos=$(curl -s -A "$UA" -L "https://github.com/trending" \
            | grep -oE 'href="/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"' \
            | sed 's/href="//;s/"//' | sort -u | head -4)
        jitter 3 10
        for repo in $repos; do
            visit "https://github.com${repo}"
            jitter 5 15
        done
        ;;
    news)
        # BBC front page, then a few articles one at a time with reading pauses.
        visit "https://www.bbc.com/news"
        jitter 4 10
        arts=$(curl -s -A "$UA" -L "https://www.bbc.com/news" \
            | grep -oE '/news/(articles/[a-z0-9]+|[a-z][a-z0-9-]*[a-z0-9])' | sort -u | head -4)
        for path in $arts; do
            visit "https://www.bbc.com${path}"
            jitter 6 18
        done
        ;;
    images)
        # A random Wikimedia file, then a few Wikipedia images, one at a time.
        visit "https://commons.wikimedia.org/wiki/Special:Random/File"
        jitter 3 8
        imgs=$(curl -s -A "$UA" "https://en.wikipedia.org/wiki/Main_Page" \
            | grep -oE 'src="[^"]+\.(jpg|jpeg|png|svg|webp)"' \
            | sed 's/src="//;s/"//' | head -4)
        for img in $imgs; do
            case "$img" in
                //*)   U="https:$img" ;;
                http*) U="$img" ;;
                *)     U="https://en.wikipedia.org$img" ;;
            esac
            visit "$U"
            jitter 4 10
        done
        ;;
    *)
        echo "Unknown type: $TYPE"
        exit 1
        ;;
esac

exit 0
